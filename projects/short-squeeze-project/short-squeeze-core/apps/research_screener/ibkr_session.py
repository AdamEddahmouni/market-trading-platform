"""The application's read-only IB Gateway session.

Extends the Batch 05 research session (`tools.ibkr_historical_export.session.IbkrSession`)
with the two additional read-only surfaces the operational screener needs — the market
scanner and streaming/snapshot market data — without touching the research exporter. The
exporter keeps its narrow guard, which continues to forbid these methods there; the wider
allowance is scoped to this application and enforced by :mod:`apps.research_screener.guard`.

Permitted here: ``reqCurrentTime``, ``reqContractDetails``, ``reqHistoricalData``,
``cancelHistoricalData``, ``reqScannerParameters``, ``reqScannerSubscription``,
``cancelScannerSubscription``, ``reqMarketDataType``, ``reqMktData``, ``cancelMktData``.

Never referenced anywhere in this application: any order, account, position, execution,
PnL or portfolio method, and any order object.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .paths import repository_root

#: Reserved client IDs for the application. Deliberately disjoint from the Batch 05
#: research exporter's 27185-27188 range so the two can never collide.
APP_CLIENT_ID_SEQUENCE: tuple[int, ...] = (27201, 27202, 27203, 27204)

#: Generic tick list requested for every quote.
#: 236 = shortability. Permission-scoped fundamentals (258/411) are deliberately
#: excluded because their rejection can prevent the base quote from completing.
#: Halted status arrives as callback tick type 49; 49 is not a legal request value.
#: Nothing here is an account, order or position request.
GENERIC_TICK_LIST = "236"

#: Provider market-data type codes, exactly as the official API defines them.
MARKET_DATA_TYPE_LABELS: dict[int, str] = {
    1: "REALTIME",
    2: "FROZEN",
    3: "DELAYED",
    4: "DELAYED_FROZEN",
}

#: Tick ids we read. Delayed ids carry the same meaning as their realtime counterparts;
#: the LIVE / DELAYED distinction is taken from the provider's ``marketDataType``
#: callback, never inferred from which tick id arrived.
_PRICE_TICKS: dict[int, str] = {
    1: "bid", 2: "ask", 4: "last", 6: "high", 7: "low", 9: "previous_close", 14: "open",
    66: "bid", 67: "ask", 68: "last", 72: "high", 73: "low", 75: "previous_close", 76: "open",
}
_SIZE_TICKS: dict[int, str] = {
    0: "bid_size", 3: "ask_size", 5: "last_size", 8: "volume", 74: "volume",
    89: "shortable_shares",
}
_GENERIC_TICKS: dict[int, str] = {
    46: "shortable_indicator",
    49: "halted",
}
_STRING_TICKS: dict[int, str] = {
    45: "last_timestamp_epoch", 88: "last_timestamp_epoch",
    47: "fundamental_ratios", 48: "fundamentals",
}


def ensure_tools_importable() -> None:
    """``tools/`` sits at the repository root and is not an installed package."""
    root = str(repository_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class ScannerRow:
    """One row exactly as the provider's scanner returned it."""

    rank: int
    con_id: int
    symbol: str
    sec_type: str
    currency: str
    primary_exchange: str
    long_name: str


@dataclass(slots=True)
class QuoteTicks:
    """Raw ticks for one symbol, plus the provider's own market-data type."""

    symbol: str
    con_id: int
    prices: dict[str, float] = field(default_factory=dict)
    sizes: dict[str, float] = field(default_factory=dict)
    generics: dict[str, float] = field(default_factory=dict)
    strings: dict[str, str] = field(default_factory=dict)
    market_data_type: int | None = None
    received_at: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    fundamentals: dict[str, str] = field(default_factory=dict)

    @property
    def market_data_type_label(self) -> str:
        if self.market_data_type is None:
            return "UNKNOWN"
        return MARKET_DATA_TYPE_LABELS.get(self.market_data_type, "UNKNOWN")


def build_session_class():
    """Build the session class lazily, so importing this module never needs ``ibapi``."""
    ensure_tools_importable()
    from tools.ibkr_historical_export.errors import is_request_ending
    from tools.ibkr_historical_export.session import IbkrSession

    class AppIbkrSession(IbkrSession):
        """Read-only session with scanner and market-data support added."""

        def __init__(self) -> None:
            super().__init__()
            self._scanner_rows: dict[int, list[ScannerRow]] = {}
            self._scanner_done: dict[int, threading.Event] = {}
            self._scanner_parameters: str | None = None
            self._scanner_parameters_evt = threading.Event()
            self._ticks: dict[int, QuoteTicks] = {}
            self._tick_done: dict[int, threading.Event] = {}
            self._market_data_type: dict[int, int] = {}

        # ------------------------------------------------------------ scanner

        def scannerParameters(self, xml: str) -> None:  # noqa: N802
            self._scanner_parameters = str(xml)
            self._scanner_parameters_evt.set()

        def scannerData(  # noqa: N802
            self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr,  # noqa: N803
        ) -> None:
            contract = getattr(contractDetails, "contract", None)
            if contract is None:
                return
            row = ScannerRow(
                rank=int(rank),
                con_id=int(getattr(contract, "conId", 0) or 0),
                symbol=str(getattr(contract, "symbol", "") or ""),
                sec_type=str(getattr(contract, "secType", "") or ""),
                currency=str(getattr(contract, "currency", "") or ""),
                primary_exchange=str(getattr(contract, "primaryExchange", "") or ""),
                long_name=str(getattr(contractDetails, "longName", "") or ""),
            )
            with self._lock:
                self._scanner_rows.setdefault(int(reqId), []).append(row)

        def scannerDataEnd(self, reqId: int) -> None:  # noqa: N802,N803
            evt = self._scanner_done.get(int(reqId))
            if evt is not None:
                evt.set()

        # -------------------------------------------------------- market data

        def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802,N803
            with self._lock:
                self._market_data_type[int(reqId)] = int(marketDataType)
                ticks = self._ticks.get(int(reqId))
                if ticks is not None:
                    ticks.market_data_type = int(marketDataType)

        def _tick_slot(self, req_id: int) -> QuoteTicks | None:
            return self._ticks.get(int(req_id))

        def tickPrice(self, reqId, tickType, price, attrib) -> None:  # noqa: N802,N803
            name = _PRICE_TICKS.get(int(tickType))
            if name is None:
                return
            try:
                value = float(price)
            except (TypeError, ValueError):
                return
            # The provider sends -1 for "no value"; that is missing, never a price.
            if value < 0:
                return
            with self._lock:
                slot = self._tick_slot(reqId)
                if slot is not None:
                    slot.prices[name] = value

        def tickSize(self, reqId, tickType, size) -> None:  # noqa: N802,N803
            name = _SIZE_TICKS.get(int(tickType))
            if name is None:
                return
            try:
                value = float(str(size))
            except (TypeError, ValueError):
                return
            if value < 0:
                return
            with self._lock:
                slot = self._tick_slot(reqId)
                if slot is not None:
                    slot.sizes[name] = value

        def tickGeneric(self, reqId, tickType, value) -> None:  # noqa: N802,N803
            name = _GENERIC_TICKS.get(int(tickType))
            if name is None:
                return
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return
            with self._lock:
                slot = self._tick_slot(reqId)
                if slot is not None:
                    slot.generics[name] = numeric

        def tickString(self, reqId, tickType, value) -> None:  # noqa: N802,N803
            name = _STRING_TICKS.get(int(tickType))
            if name is None:
                return
            with self._lock:
                slot = self._tick_slot(reqId)
                if slot is not None:
                    slot.strings[name] = str(value)
                    if name in ("fundamental_ratios", "fundamentals"):
                        slot.fundamentals[name] = str(value)

        def tickSnapshotEnd(self, reqId: int) -> None:  # noqa: N802,N803
            evt = self._tick_done.get(int(reqId))
            if evt is not None:
                evt.set()

        # ------------------------------------------------------------- errors

        def error(  # noqa: N802,N803
            self,
            reqId,
            errorTime=0,
            errorCode=0,
            errorString="",
            advancedOrderRejectJson="",
            *args,
        ):
            # New API: (reqId, errorTime, errorCode, errorString, ...)
            # Old API: (reqId, errorCode, errorString, advancedOrderRejectJson)
            # Defaults alone do not fix old positional arity — normalize first.
            if isinstance(errorTime, int) and isinstance(errorCode, str):
                errorTime, errorCode, errorString, advancedOrderRejectJson = (
                    0,
                    errorTime,
                    errorCode,
                    errorString,
                )
            try:
                super().error(
                    reqId, errorTime, errorCode, errorString, advancedOrderRejectJson
                )
            except TypeError:
                try:
                    super().error(
                        reqId, errorCode, errorString, advancedOrderRejectJson
                    )
                except TypeError:
                    super().error(reqId, errorCode, errorString)
            try:
                code = int(errorCode)
            except (TypeError, ValueError):
                code = -1
            key = int(reqId) if reqId is not None else -1
            with self._lock:
                slot = self._ticks.get(key)
                if slot is not None:
                    slot.errors.append({"code": code, "message": str(errorString)})
            if is_request_ending(code):
                for registry in (self._scanner_done, self._tick_done):
                    evt = registry.get(key)
                    if evt is not None:
                        evt.set()

        # --------------------------------------------------------- operations

        def fetch_scanner_parameters(self, timeout: float) -> str | None:
            """The provider's own scanner-parameter document (capability discovery)."""
            self._scanner_parameters_evt.clear()
            self.reqScannerParameters()
            if self._scanner_parameters_evt.wait(timeout=timeout):
                return self._scanner_parameters
            return None

        def run_scanner(
            self, req_id: int, subscription, timeout: float
        ) -> tuple[list[ScannerRow], list[tuple[int, str, int]], bool]:
            """One scanner subscription, cancelled as soon as its first result set lands."""
            done = threading.Event()
            self._scanner_done[req_id] = done
            self._scanner_rows.setdefault(req_id, [])
            self.reqScannerSubscription(req_id, subscription, [], [])
            completed = done.wait(timeout=timeout)
            try:
                self.cancelScannerSubscription(req_id)
            except Exception:  # noqa: BLE001 - cancelling a dead request must not raise
                pass
            with self._lock:
                rows = sorted(self._scanner_rows.get(req_id, []), key=lambda row: row.rank)
                errors = list(self._errors.get(req_id, []))
            return rows, errors, completed

        def request_market_data_type(self, market_data_type: int) -> None:
            """Ask for a data type. What the provider actually grants is reported back."""
            self.reqMarketDataType(int(market_data_type))

        def fetch_quote(
            self, req_id: int, contract, symbol: str, timeout: float,
            *, snapshot: bool = False, settle_seconds: float = 2.5,
            generic_ticks: str | None = None,
        ) -> QuoteTicks:
            """One bounded quote read. Always cancelled; never left streaming.

            Streaming (``snapshot=False``) is the default because a snapshot request needs
            a separate entitlement that many accounts do not carry — the provider rejects
            it with error 321. A streaming request is opened, allowed to settle for a
            couple of seconds, and then explicitly cancelled. Nothing is left subscribed.
            """
            slot = QuoteTicks(symbol=symbol, con_id=int(getattr(contract, "conId", 0) or 0))
            done = threading.Event()
            with self._lock:
                self._ticks[req_id] = slot
            self._tick_done[req_id] = done
            tick_list = generic_ticks if generic_ticks is not None else GENERIC_TICK_LIST
            self.reqMktData(req_id, contract, tick_list, snapshot, False, [])
            if snapshot:
                done.wait(timeout=timeout)
            else:
                # Poll until a price tick lands, then let it settle briefly so bid/ask and
                # the market-data type arrive too. Bounded by ``timeout`` either way.
                deadline = _now().timestamp() + timeout
                first_seen: float | None = None
                while _now().timestamp() < deadline and not done.is_set():
                    with self._lock:
                        have_price = bool(slot.prices)
                    if have_price:
                        if first_seen is None:
                            first_seen = _now().timestamp()
                        elif _now().timestamp() - first_seen >= settle_seconds:
                            break
                    done.wait(timeout=0.2)
            try:
                self.cancelMktData(req_id)
            except Exception:  # noqa: BLE001
                pass
            with self._lock:
                slot.received_at = _now().isoformat().replace("+00:00", "Z")
                if slot.market_data_type is None:
                    slot.market_data_type = self._market_data_type.get(req_id)
            return slot

    return AppIbkrSession


__all__ = [
    "APP_CLIENT_ID_SEQUENCE",
    "GENERIC_TICK_LIST",
    "MARKET_DATA_TYPE_LABELS",
    "QuoteTicks",
    "ScannerRow",
    "build_session_class",
    "ensure_tools_importable",
]
