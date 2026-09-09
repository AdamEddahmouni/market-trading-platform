"""Streaming observational IBKR transport (G8).

Implements the canonical ``IbkrTransport`` protocol for
``IbkrObservationalAdapter``. Uses ib_insync when available; tests inject a
fake broker. Read-only: no order/account/execution methods exist on this
surface.

Dependency direction:
    tools/ibkr (this module)
        ↓
    src/providers/ibkr_observational (adapter protocol)
"""

from __future__ import annotations

import math
import threading
from types import SimpleNamespace
from typing import Any, Callable, Protocol

from .client import LiveGateDisabled
from .config import IbkrConfig

BrokerFactory = Callable[[IbkrConfig], Any]


class TwsDependencyError(RuntimeError):
    """Raised when optional ib_insync is unavailable."""


def _default_broker_factory(config: IbkrConfig) -> Any:
    try:
        from ib_insync import IB
    except ImportError as exc:
        raise TwsDependencyError(
            "optional ib_insync dependency is required for IMP_IBKR_TRANSPORT=tws"
        ) from exc
    return IB()


def _unset(value: float) -> bool:
    try:
        from ib_insync.util import UNSET_DOUBLE
    except ImportError:
        return math.isnan(value)
    return value == UNSET_DOUBLE or (isinstance(value, float) and math.isnan(value))


class _AdapterBridge(Protocol):
    def on_tick_price(
        self, req_id: int, field: int, price: float | None, *, received_ns: int | None = None, source_time_ns: int | None = None
    ) -> Any: ...

    def on_tick_size(
        self, req_id: int, field: int, size: float | None, *, received_ns: int | None = None, source_time_ns: int | None = None
    ) -> Any: ...

    def on_tick_by_tick_all_last(
        self,
        req_id: int,
        tick_type: int,
        price: float | None,
        size: float | None,
        *,
        source_time_ns: int | None = None,
        received_ns: int | None = None,
        exchange: str | None = None,
        special_conditions: str | None = None,
        past_limit: bool | None = None,
        unreported: bool | None = None,
    ) -> Any: ...

    def on_mkt_depth(
        self,
        req_id: int,
        position: int,
        operation: int,
        side: int,
        price: float | None,
        size: float | None,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> Any: ...

    def on_mkt_depth_l2(
        self,
        req_id: int,
        position: int,
        market_maker: str,
        operation: int,
        side: int,
        price: float | None,
        size: float | None,
        is_smart_depth: bool,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> Any: ...

    def on_error(
        self, req_id: int | None, code: int | None, message: str, *, received_ns: int | None = None
    ) -> Any: ...

    def on_connection_state(self, state: Any, *, reason: str | None = None) -> None: ...


class IbkrObservationalTransport:
    """Observational-only TWS socket transport with callback bridge."""

    def __init__(
        self,
        config: IbkrConfig,
        *,
        adapter: _AdapterBridge | None = None,
        broker_factory: BrokerFactory | None = None,
    ) -> None:
        if not config.live_enabled:
            raise LiveGateDisabled("IMP_IBKR_LIVE is not enabled")
        if config.transport != "tws":
            raise ValueError("IbkrObservationalTransport requires IMP_IBKR_TRANSPORT=tws")
        self.config = config
        self._adapter = adapter
        self._broker = (
            broker_factory(config) if broker_factory is not None else _default_broker_factory(config)
        )
        self._connected = False
        self._readonly = True
        self._req_ids: set[int] = set()
        self._depth_req_ids: set[int] = set()
        self._trade_req_ids: set[int] = set()
        self._contracts: dict[int, Any] = {}
        self._lock = threading.RLock()
        self._wire_callbacks()

    def attach_adapter(self, adapter: _AdapterBridge) -> None:
        self._adapter = adapter

    def _wire_callbacks(self) -> None:
        broker = self._broker
        if hasattr(broker, "errorEvent"):
            broker.errorEvent += self._on_error_event
        if hasattr(broker, "disconnectedEvent"):
            broker.disconnectedEvent += self._on_disconnected

    def _on_error_event(self, req_id: int, code: int, message: str, contract: Any) -> None:
        if self._adapter is None:
            return
        self._adapter.on_error(req_id if req_id >= 0 else None, code, str(message))

    def _on_disconnected(self) -> None:
        self._connected = False

    def connect(self, *, host: str, port: int, client_id: int, readonly: bool = True) -> None:
        if not self.config.live_enabled:
            raise LiveGateDisabled("IMP_IBKR_LIVE is not enabled")
        self._readonly = bool(readonly)
        with self._lock:
            self._broker.connect(host, port, clientId=client_id, readonly=self._readonly)
            self._connected = True

    def disconnect(self) -> None:
        with self._lock:
            if self._connected:
                self._broker.disconnect()
            self._connected = False
            self._req_ids.clear()
            self._depth_req_ids.clear()
            self._trade_req_ids.clear()
            self._contracts.clear()

    def is_connected(self) -> bool:
        connected = self._connected
        is_connected = getattr(self._broker, "isConnected", None)
        if callable(is_connected):
            connected = bool(is_connected())
        return connected

    def _contract_from_descriptor(self, contract: Any) -> Any:
        if isinstance(contract, dict):
            con_id = contract.get("conId")
            if con_id is not None:
                cached = self._contracts.get(int(con_id))
                if cached is not None:
                    return cached
                try:
                    from ib_insync import Contract
                except ImportError:
                    return SimpleNamespace(conId=int(con_id))
                return Contract(conId=int(con_id))
            symbol = str(contract.get("symbol") or "").strip().upper()
            if not symbol:
                raise ValueError("contract descriptor requires conId or symbol")
            try:
                from ib_insync import Stock
            except ImportError:
                return SimpleNamespace(symbol=symbol, secType="STK", exchange="SMART", currency="USD")
            return Stock(symbol, "SMART", "USD")
        return contract

    def _ensure_unique_req_id(self, req_id: int) -> None:
        if req_id in self._req_ids or req_id in self._depth_req_ids or req_id in self._trade_req_ids:
            raise ValueError(f"duplicate req_id {req_id}")

    def req_mkt_data(
        self, req_id: int, contract: Any, *, generic_ticks: str = "", snapshot: bool = False
    ) -> None:
        self._ensure_unique_req_id(req_id)
        resolved = self._contract_from_descriptor(contract)
        with self._lock:
            self._req_ids.add(req_id)
            self._contracts[req_id] = resolved
            ticker = self._broker.reqMktData(
                resolved,
                generic_ticks,
                snapshot=snapshot,
                regulatorySnapshot=False,
            )
            if hasattr(ticker, "updateEvent"):
                ticker.updateEvent += lambda t, rid=req_id: self._forward_ticker(rid, t)
            self._patch_wrapper_callbacks(req_id)

    def _patch_wrapper_callbacks(self, req_id: int) -> None:
        wrapper = getattr(self._broker, "wrapper", None)
        if wrapper is None:
            return
        original_price = getattr(wrapper, "tickPrice", None)
        original_size = getattr(wrapper, "tickSize", None)
        original_depth = getattr(wrapper, "updateMktDepth", None)
        original_depth_l2 = getattr(wrapper, "updateMktDepthL2", None)
        original_tbt = getattr(wrapper, "tickByTickAllLast", None)

        if original_price is not None and not getattr(wrapper, "_g8_price_patched", False):
            def tick_price(req_id_: int, tick_type: int, price: float, attrib: Any) -> None:
                original_price(req_id_, tick_type, price, attrib)
                if self._adapter is not None and req_id_ in self._req_ids:
                    value = None if _unset(price) else float(price)
                    self._adapter.on_tick_price(req_id_, tick_type, value)

            wrapper.tickPrice = tick_price
            wrapper._g8_price_patched = True

        if original_size is not None and not getattr(wrapper, "_g8_size_patched", False):
            def tick_size(req_id_: int, tick_type: int, size: float) -> None:
                original_size(req_id_, tick_type, size)
                if self._adapter is not None and req_id_ in self._req_ids:
                    value = None if _unset(size) else float(size)
                    self._adapter.on_tick_size(req_id_, tick_type, value)

            wrapper.tickSize = tick_size
            wrapper._g8_size_patched = True

        if original_depth is not None and not getattr(wrapper, "_g8_depth_patched", False):
            def update_mkt_depth(
                req_id_: int, position: int, operation: int, side: int, price: float, size: float
            ) -> None:
                original_depth(req_id_, position, operation, side, price, size)
                if self._adapter is not None and req_id_ in self._depth_req_ids:
                    p = None if _unset(price) else float(price)
                    s = None if _unset(size) else float(size)
                    self._adapter.on_mkt_depth(req_id_, position, operation, side, p, s)

            wrapper.updateMktDepth = update_mkt_depth
            wrapper._g8_depth_patched = True

        if original_depth_l2 is not None and not getattr(wrapper, "_g8_depth_l2_patched", False):
            def update_mkt_depth_l2(
                req_id_: int,
                position: int,
                market_maker: str,
                operation: int,
                side: int,
                price: float,
                size: float,
                is_smart_depth: bool,
            ) -> None:
                original_depth_l2(
                    req_id_, position, market_maker, operation, side, price, size, is_smart_depth
                )
                if self._adapter is not None and req_id_ in self._depth_req_ids:
                    p = None if _unset(price) else float(price)
                    s = None if _unset(size) else float(size)
                    self._adapter.on_mkt_depth_l2(
                        req_id_, position, market_maker, operation, side, p, s, is_smart_depth
                    )

            wrapper.updateMktDepthL2 = update_mkt_depth_l2
            wrapper._g8_depth_l2_patched = True

        if original_tbt is not None and not getattr(wrapper, "_g9_tbt_patched", False):
            def tick_by_tick_all_last(
                req_id_: int,
                tick_type: int,
                time_: int,
                price: float,
                size: float,
                tick_attrib_last: Any,
                exchange: str,
                special_conditions: str,
            ) -> None:
                original_tbt(
                    req_id_,
                    tick_type,
                    time_,
                    price,
                    size,
                    tick_attrib_last,
                    exchange,
                    special_conditions,
                )
                if self._adapter is not None and req_id_ in self._trade_req_ids:
                    source_ns = None
                    if isinstance(time_, int) and time_ > 0:
                        source_ns = int(time_) * 1_000_000_000
                    past_limit = getattr(tick_attrib_last, "pastLimit", None)
                    unreported = getattr(tick_attrib_last, "unreported", None)
                    p = None if _unset(price) else float(price)
                    s = None if _unset(size) else float(size)
                    self._adapter.on_tick_by_tick_all_last(
                        req_id_,
                        tick_type,
                        p,
                        s,
                        source_time_ns=source_ns,
                        exchange=str(exchange or "") or None,
                        special_conditions=str(special_conditions or "") or None,
                        past_limit=past_limit,
                        unreported=unreported,
                    )

            wrapper.tickByTickAllLast = tick_by_tick_all_last
            wrapper._g9_tbt_patched = True

    def _forward_ticker(self, req_id: int, ticker: Any) -> None:
        if self._adapter is None:
            return
        TICK_BID = 1
        TICK_ASK = 2
        TICK_LAST = 4
        TICK_BID_SIZE = 0
        TICK_ASK_SIZE = 3
        TICK_LAST_SIZE = 5
        mapping = (
            (TICK_BID, getattr(ticker, "bid", None), "price"),
            (TICK_ASK, getattr(ticker, "ask", None), "price"),
            (TICK_LAST, getattr(ticker, "last", None), "price"),
            (TICK_BID_SIZE, getattr(ticker, "bidSize", None), "size"),
            (TICK_ASK_SIZE, getattr(ticker, "askSize", None), "size"),
            (TICK_LAST_SIZE, getattr(ticker, "lastSize", None), "size"),
        )
        for field, value, kind in mapping:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            if kind == "price":
                self._adapter.on_tick_price(req_id, field, float(value))
            else:
                self._adapter.on_tick_size(req_id, field, float(value))

    def cancel_mkt_data(self, req_id: int) -> None:
        with self._lock:
            self._req_ids.discard(req_id)
            self._contracts.pop(req_id, None)
            client = getattr(self._broker, "client", None)
            if client is not None and hasattr(client, "cancelMktData"):
                client.cancelMktData(req_id)

    def req_mkt_depth(
        self, req_id: int, contract: Any, *, num_rows: int, is_smart_depth: bool = False
    ) -> None:
        self._ensure_unique_req_id(req_id)
        resolved = self._contract_from_descriptor(contract)
        with self._lock:
            self._depth_req_ids.add(req_id)
            self._contracts[req_id] = resolved
            client = getattr(self._broker, "client", None)
            if client is not None and hasattr(client, "reqMktDepth"):
                client.reqMktDepth(req_id, resolved, num_rows, is_smart_depth, [])
            else:
                self._broker.reqMktDepth(resolved, numRows=num_rows, isSmartDepth=is_smart_depth)
            self._patch_wrapper_callbacks(req_id)

    def cancel_mkt_depth(self, req_id: int, *, is_smart_depth: bool = False) -> None:
        with self._lock:
            self._depth_req_ids.discard(req_id)
            self._contracts.pop(req_id, None)
            client = getattr(self._broker, "client", None)
            if client is not None and hasattr(client, "cancelMktDepth"):
                client.cancelMktDepth(req_id, is_smart_depth)

    def req_tick_by_tick_data(
        self,
        req_id: int,
        contract: Any,
        *,
        tick_type: str = "AllLast",
        number_of_ticks: int = 0,
        ignore_size: bool = False,
    ) -> None:
        self._ensure_unique_req_id(req_id)
        resolved = self._contract_from_descriptor(contract)
        with self._lock:
            self._trade_req_ids.add(req_id)
            self._contracts[req_id] = resolved
            client = getattr(self._broker, "client", None)
            if client is not None and hasattr(client, "reqTickByTickData"):
                client.reqTickByTickData(req_id, resolved, tick_type, number_of_ticks, ignore_size)
            elif hasattr(self._broker, "reqTickByTickData"):
                self._broker.reqTickByTickData(resolved, tickType=tick_type)
            self._patch_wrapper_callbacks(req_id)

    def cancel_tick_by_tick_data(self, req_id: int) -> None:
        with self._lock:
            self._trade_req_ids.discard(req_id)
            self._contracts.pop(req_id, None)
            client = getattr(self._broker, "client", None)
            if client is not None and hasattr(client, "cancelTickByTickData"):
                client.cancelTickByTickData(req_id)


__all__ = ["IbkrObservationalTransport", "TwsDependencyError"]
