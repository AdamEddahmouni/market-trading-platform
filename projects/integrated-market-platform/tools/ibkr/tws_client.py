"""Narrow, read-only adapter for the local IBKR desktop Gateway."""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from .capture import ObservationCapture
from .client import EndpointNotAllowed, LiveGateDisabled
from .config import IbkrConfig


class TwsDependencyError(RuntimeError):
    """Raised when the optional TWS client dependency is unavailable."""


class TwsCapabilityUnavailable(RuntimeError):
    """Raised when the Gateway cannot provide a requested observation."""


_OBSERVATION_PATHS = frozenset(
    {
        "/iserver/auth/status",
        "/iserver/secdef/search",
        "/iserver/marketdata/snapshot",
        "/hmds/history",
        "/trsrv/secdef",
        "/iserver/scanner/params",
        "/portfolio/accounts",
    }
)
_DURATION_BY_PERIOD = {"1d": "1 D", "5d": "5 D", "1w": "1 W"}
_BAR_SIZE_BY_BAR = {"1h": "1 hour", "1d": "1 day", "5m": "5 mins"}
BrokerFactory = Callable[[IbkrConfig], Any]
ContractFactory = Callable[[str], object]


def _default_broker_factory(config: IbkrConfig) -> Any:
    try:
        from ib_insync import IB
    except ImportError as exc:
        raise TwsDependencyError(
            "optional ib_insync dependency is required for IMP_IBKR_TRANSPORT=tws"
        ) from exc
    return IB()


def _default_contract_factory(symbol: str) -> object:
    try:
        from ib_insync import Stock
    except ImportError as exc:
        raise TwsDependencyError(
            "optional ib_insync dependency is required for IMP_IBKR_TRANSPORT=tws"
        ) from exc
    return Stock(symbol, "SMART", "USD")


def _simple_contract(symbol: str) -> object:
    return SimpleNamespace(symbol=symbol, secType="STK", exchange="SMART", currency="USD")


def _finite(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _serializable_timestamp(value: object) -> object:
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else value


class TwsIbkrClient:
    """Expose only fixed observational operations through an IBKR TWS session."""

    transport = "tws"
    provider = "IBKR_TWS_GATEWAY"

    def __init__(
        self,
        config: IbkrConfig,
        *,
        broker_factory: BrokerFactory | None = None,
        contract_factory: ContractFactory | None = None,
        capture: ObservationCapture | None = None,
    ) -> None:
        if not config.live_enabled:
            raise LiveGateDisabled("IMP_IBKR_LIVE is not enabled")
        if config.transport != "tws":
            raise ValueError("TwsIbkrClient requires IMP_IBKR_TRANSPORT=tws")
        self.config = config
        self._broker = (
            broker_factory(config)
            if broker_factory is not None
            else _default_broker_factory(config)
        )
        self._contract_factory = (
            contract_factory
            if contract_factory is not None
            else (_simple_contract if broker_factory is not None else _default_contract_factory)
        )
        self._capture = capture or ObservationCapture(
            config.capture_root / "tws-observations.jsonl"
        )
        self._contracts: dict[int, object] = {}
        self._closed = False
        self._broker.connect(
            config.tws_host,
            config.tws_port,
            clientId=config.tws_client_id,
            timeout=config.timeout_seconds,
            readonly=True,
        )

    def _capture_result(self, method: str, path: str, params: Mapping[str, object] | None, payload: object) -> object:
        self._capture.record(
            method=method,
            path=path,
            params=params,
            request_body=None,
            status=200,
            headers={},
            response_payload=payload,
            provider=self.provider,
        )
        return payload

    def _contract(self, conid: int) -> object:
        try:
            return self._contracts[conid]
        except KeyError as exc:
            raise ValueError("contract must be resolved before requesting this capability") from exc

    def _search(self, params: Mapping[str, object]) -> list[dict[str, object]]:
        symbol = str(params.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        rows: list[dict[str, object]] = []
        for sample in self._broker.reqMatchingSymbols(symbol):
            contract = getattr(sample, "contract", sample)
            conid = getattr(contract, "conId", getattr(contract, "conid", None))
            if not isinstance(conid, int) or isinstance(conid, bool) or conid <= 0:
                continue
            if str(getattr(contract, "secType", "STK")) == "STK" and not getattr(
                contract, "exchange", ""
            ):
                setattr(contract, "exchange", "SMART")
            self._contracts[conid] = contract
            rows.append(
                {
                    "symbol": str(getattr(contract, "symbol", symbol)),
                    "conid": conid,
                    "secType": str(getattr(contract, "secType", "STK")),
                    "primaryExchange": str(
                        getattr(contract, "primaryExchange", "")
                    ),
                }
            )
        return rows

    def _snapshot(self, params: Mapping[str, object]) -> list[dict[str, object]]:
        raw_conids = str(params.get("conids") or "")
        conids = [int(value) for value in raw_conids.split(",") if value.strip().isdigit()]
        rows: list[dict[str, object]] = []
        set_market_data_type = getattr(self._broker, "reqMarketDataType", None)
        if callable(set_market_data_type):
            set_market_data_type(3)
        for conid in conids:
            contract = self._contract(conid)
            ticker = self._broker.reqMktData(
                contract,
                "",
                snapshot=True,
                regulatorySnapshot=False,
                mktDataOptions=[],
            )
            sleep = getattr(self._broker, "sleep", None)
            if callable(sleep):
                sleep(min(0.5, self.config.timeout_seconds))
            row: dict[str, object] = {"conid": conid}
            for output_key, attribute in (
                ("31", "last"),
                ("84", "bid"),
                ("86", "ask"),
                ("87", "volume"),
                ("88", "bidSize"),
            ):
                value = _finite(getattr(ticker, attribute, None))
                if value is not None:
                    row[output_key] = value
            rows.append(row)
        return rows

    def _history(self, params: Mapping[str, object]) -> dict[str, object]:
        conid = int(str(params.get("conid") or "0"))
        contract = self._contract(conid)
        period = str(params.get("period") or "1d").lower()
        bar = str(params.get("bar") or "1h").lower()
        try:
            duration = _DURATION_BY_PERIOD[period]
            bar_size = _BAR_SIZE_BY_BAR[bar]
        except KeyError as exc:
            raise ValueError("unsupported historical period or bar size") from exc
        bars = self._broker.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
            timeout=self.config.timeout_seconds,
        )
        if not bars:
            raise TwsCapabilityUnavailable("historical data unavailable")
        data: list[dict[str, object]] = []
        for item in bars:
            data.append(
                {
                    "t": _serializable_timestamp(getattr(item, "date", None)),
                    "o": getattr(item, "open", None),
                    "h": getattr(item, "high", None),
                    "l": getattr(item, "low", None),
                    "c": getattr(item, "close", None),
                    "v": getattr(item, "volume", None),
                }
            )
        return {"symbol": str(getattr(contract, "symbol", "")), "data": data}

    def _options(self, params: Mapping[str, object]) -> list[dict[str, object]]:
        symbol = str(params.get("symbols") or "").strip().upper()
        conid = int(str(params.get("conid") or next(iter(self._contracts), 0)))
        rows: list[dict[str, object]] = []
        for item in self._broker.reqSecDefOptParams(symbol, "", "STK", conid):
            rows.append(
                {
                    "exchange": str(getattr(item, "exchange", "")),
                    "tradingClass": str(getattr(item, "tradingClass", symbol)),
                    "expirations": sorted(str(value) for value in getattr(item, "expirations", [])),
                    "strikes": sorted(float(value) for value in getattr(item, "strikes", [])),
                }
            )
        return rows

    def _scanner(self) -> dict[str, object]:
        payload = self._broker.reqScannerParameters()
        return {"available": payload is not None}

    def _portfolio(self) -> list[dict[str, object]]:
        summary = self._broker.accountSummary()
        return [{"available": True, "item_count": len(summary)}]

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> object:
        if method.upper().strip() != "GET" or path not in _OBSERVATION_PATHS or body is not None:
            raise EndpointNotAllowed("endpoint is outside the TWS observational allowlist")
        if path == "/iserver/auth/status":
            payload = {
                "connected": bool(self._broker.isConnected()),
                "authenticated": bool(self._broker.isConnected()),
            }
        elif path == "/iserver/secdef/search":
            payload = self._search(params or {})
        elif path == "/iserver/marketdata/snapshot":
            payload = self._snapshot(params or {})
        elif path == "/hmds/history":
            payload = self._history(params or {})
        elif path == "/trsrv/secdef":
            payload = self._options(params or {})
        elif path == "/iserver/scanner/params":
            payload = self._scanner()
        else:
            payload = self._portfolio()
        return self._capture_result(method.upper(), path, params, payload)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._broker.disconnect()


__all__ = ["TwsCapabilityUnavailable", "TwsDependencyError", "TwsIbkrClient"]
