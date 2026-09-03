"""Read-only IB Gateway session -- the only module that imports ``ibapi``.

Wraps the official ``EClient``/``EWrapper`` with a threaded run loop and blocking
helpers for the three allowed request types (current time, contract details, historical
bars). It references only allowed API methods; order/account/portfolio methods are never
called. ``managedAccounts`` account identifiers are received by the callback but never
stored or logged.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


def _decimalMaxString(val):
    """Convert a Decimal/float to string without scientific notation.

    Replaces the removed ``decimalMaxString`` from older ibapi versions.
    """
    if val is None:
        return None
    try:
        if isinstance(val, float):
            if val == float('inf') or val == float('-inf') or val != val:
                return None
        # Format without scientific notation, strip trailing zeros
        s = f"{val:f}"
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s if s else '0'
    except (TypeError, ValueError):
        return str(val)

from .cohort import CONTRACT_SPEC, HistoricalRequestSpec
from .errors import is_disconnect, is_request_ending
from .models import ApiDiagnostic, BarRecord, ContractCandidate


def _candidate_from(details) -> ContractCandidate:
    c = details.contract
    return ContractCandidate(
        con_id=int(getattr(c, "conId", 0) or 0),
        symbol=str(getattr(c, "symbol", "") or ""),
        local_symbol=str(getattr(c, "localSymbol", "") or ""),
        sec_type=str(getattr(c, "secType", "") or ""),
        currency=str(getattr(c, "currency", "") or ""),
        exchange=str(getattr(c, "exchange", "") or ""),
        primary_exchange=str(getattr(c, "primaryExchange", "") or ""),
        trading_class=str(getattr(c, "tradingClass", "") or ""),
        long_name=str(getattr(details, "longName", "") or ""),
        time_zone_id=str(getattr(details, "timeZoneId", "") or ""),
        trading_hours=str(getattr(details, "tradingHours", "") or ""),
        liquid_hours=str(getattr(details, "liquidHours", "") or ""),
        valid_exchanges=str(getattr(details, "validExchanges", "") or ""),
    )


def _epoch_to_utc_iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_stock_contract(symbol: str) -> Contract:
    """Outcome-blind STK/SMART/USD contract for a contract-details request."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = CONTRACT_SPEC["secType"]
    contract.exchange = CONTRACT_SPEC["exchange"]
    contract.currency = CONTRACT_SPEC["currency"]
    return contract


def make_conid_contract(con_id: int, symbol: str) -> Contract:
    """Exact resolved contract (by conId) for a historical request."""
    contract = Contract()
    contract.conId = con_id
    contract.symbol = symbol
    contract.secType = CONTRACT_SPEC["secType"]
    contract.exchange = CONTRACT_SPEC["exchange"]
    contract.currency = CONTRACT_SPEC["currency"]
    return contract


class IbkrSession(EWrapper, EClient):
    """Threaded, read-only IB Gateway client for contract + historical requests."""

    def __init__(self) -> None:
        EClient.__init__(self, self)
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

        self._contract_candidates: dict[int, list[ContractCandidate]] = {}
        self._contract_done: dict[int, threading.Event] = {}
        self._bars: dict[int, list[BarRecord]] = {}
        self._hist_done: dict[int, threading.Event] = {}
        self._req_context: dict[int, tuple[str, str, int]] = {}
        self._errors: dict[int, list[tuple[int, str, int]]] = {}
        self._diagnostics: list[ApiDiagnostic] = []

        self._current_time: int | None = None
        self._current_time_evt = threading.Event()

        self._endpoint: tuple[str, int, int] | None = None
        self._connection_closed = threading.Event()

    def record_endpoint(self, host: str, port: int, client_id: int) -> None:
        """Remember the socket that succeeded so reconnect can reuse it."""
        self._endpoint = (host, port, client_id)
        self._connection_closed.clear()

    def connectionClosed(self) -> None:  # noqa: N802 (ibapi naming)
        self._ready.clear()
        self._connection_closed.set()

    def is_live(self) -> bool:
        """True when the API socket is connected and has not reported closure."""
        try:
            return bool(self.isConnected()) and not self._connection_closed.is_set()
        except Exception:  # noqa: BLE001
            return False

    def ping(self, timeout: float) -> bool:
        """Lightweight liveness check via ``reqCurrentTime``."""
        if not self.is_live():
            return False
        return self.fetch_current_time(timeout) is not None

    def _reset_request_state(self) -> None:
        with self._lock:
            self._contract_candidates.clear()
            self._contract_done.clear()
            self._bars.clear()
            self._hist_done.clear()
            self._req_context.clear()
            self._errors.clear()
            self._diagnostics.clear()
        self._current_time = None
        self._current_time_evt.clear()
        self._ready.clear()
        self._connection_closed.clear()

    def reconnect(self, timeout: float) -> bool:
        """Reconnect using the last recorded endpoint after the socket drops."""
        if self._endpoint is None:
            return False
        host, port, client_id = self._endpoint
        try:
            if self.isConnected():
                self.disconnect()
        except Exception:  # noqa: BLE001
            pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._reset_request_state()
        self.connect(host, port, client_id)
        self.start_run_loop()
        if not self.wait_ready(timeout):
            return False
        return self.is_live()

    # -- connection callbacks --------------------------------------------------
    def connectAck(self) -> None:  # noqa: N802 (ibapi naming)
        pass

    def nextValidId(self, orderId: int) -> None:  # noqa: N802,N803
        self._ready.set()

    def managedAccounts(self, accountsList: str) -> None:  # noqa: N802,N803
        # Account identifiers are intentionally NOT stored or logged.
        self._ready.set()

    # -- diagnostics -----------------------------------------------------------
    def error(  # noqa: N802
        self, reqId, errorTime=0, errorCode=0, errorString="", advancedOrderRejectJson="",
    ) -> None:
        # New API: (reqId, errorTime, errorCode, errorString, ...)
        # Old API: (reqId, errorCode, errorString, advancedOrderRejectJson)
        if isinstance(errorTime, int) and isinstance(errorCode, str):
            errorTime, errorCode, errorString, advancedOrderRejectJson = (
                0,
                errorTime,
                errorCode,
                errorString,
            )
        try:
            code = int(errorCode)
        except (TypeError, ValueError):
            code = -1
        diag = ApiDiagnostic(
            request_id=int(reqId) if reqId is not None else -1,
            error_code=code,
            error_message=str(errorString),
            error_time=0,
        )
        with self._lock:
            self._diagnostics.append(diag)
            self._errors.setdefault(diag.request_id, []).append(
                (code, str(errorString), diag.error_time)
            )
        if is_disconnect(code):
            self._ready.clear()
            self._connection_closed.set()
        if is_request_ending(code):
            evt = self._contract_done.get(diag.request_id)
            if evt is not None:
                evt.set()
            evt = self._hist_done.get(diag.request_id)
            if evt is not None:
                evt.set()

    # -- contract details ------------------------------------------------------
    def contractDetails(self, reqId: int, contractDetails) -> None:  # noqa: N802,N803
        with self._lock:
            self._contract_candidates.setdefault(reqId, []).append(
                _candidate_from(contractDetails)
            )

    def contractDetailsEnd(self, reqId: int) -> None:  # noqa: N802,N803
        evt = self._contract_done.get(reqId)
        if evt is not None:
            evt.set()

    # -- historical data -------------------------------------------------------
    def historicalData(self, reqId: int, bar) -> None:  # noqa: N802,N803
        context = self._req_context.get(reqId, ("", "", 0))
        request_name, symbol, con_id = context
        try:
            epoch = int(str(bar.date).strip())
        except (TypeError, ValueError):
            epoch = 0
        volume = _decimalMaxString(bar.volume) or None
        wap = _decimalMaxString(getattr(bar, "wap", None)) or None
        record = BarRecord(
            request_id=int(reqId),
            request_name=request_name,
            requested_symbol=symbol,
            resolved_con_id=con_id,
            timestamp_epoch=epoch,
            timestamp_utc=_epoch_to_utc_iso(epoch),
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=volume,
            wap=wap,
            bar_count=int(getattr(bar, "barCount", 0) or 0),
        )
        with self._lock:
            self._bars.setdefault(reqId, []).append(record)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802,N803
        evt = self._hist_done.get(reqId)
        if evt is not None:
            evt.set()

    def currentTime(self, time: int) -> None:  # noqa: N802
        self._current_time = int(time)
        self._current_time_evt.set()

    # -- lifecycle -------------------------------------------------------------
    def start_run_loop(self) -> None:
        self._thread = threading.Thread(target=self.run, name="ibkr-run", daemon=True)
        self._thread.start()

    def wait_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout=timeout)

    def get_server_version(self) -> int | None:
        try:
            return int(self.serverVersion())
        except Exception:  # noqa: BLE001 - defensive; serverVersion pre-connect can raise
            return None

    # -- request helpers -------------------------------------------------------
    def fetch_current_time(self, timeout: float) -> int | None:
        self._current_time_evt.clear()
        self.reqCurrentTime()
        if self._current_time_evt.wait(timeout=timeout):
            return self._current_time
        return None

    def request_contract_details(
        self, req_id: int, symbol: str, timeout: float
    ) -> tuple[list[ContractCandidate], list[tuple[int, str, int]]]:
        done = threading.Event()
        self._contract_done[req_id] = done
        self._contract_candidates.setdefault(req_id, [])
        self.reqContractDetails(req_id, make_stock_contract(symbol))
        done.wait(timeout=timeout)
        with self._lock:
            candidates = list(self._contract_candidates.get(req_id, []))
            errors = list(self._errors.get(req_id, []))
        return candidates, errors

    def request_historical(
        self, req_id: int, spec: HistoricalRequestSpec, symbol: str, con_id: int,
        contract, timeout: float,
    ) -> tuple[list[BarRecord], list[tuple[int, str, int]], bool]:
        done = threading.Event()
        self._hist_done[req_id] = done
        self._bars.setdefault(req_id, [])
        self._req_context[req_id] = (spec.request_name, symbol, con_id)
        self.reqHistoricalData(
            req_id, contract, spec.end_datetime, spec.duration_str,
            spec.bar_size_setting, spec.what_to_show, spec.use_rth,
            spec.format_date, spec.keep_up_to_date, spec.chart_options,
        )
        completed = done.wait(timeout=timeout)
        with self._lock:
            bars = list(self._bars.get(req_id, []))
            errors = list(self._errors.get(req_id, []))
        return bars, errors, completed

    def all_diagnostics(self) -> list[ApiDiagnostic]:
        with self._lock:
            return list(self._diagnostics)

    def shutdown(self) -> None:
        try:
            if self.isConnected():
                self.disconnect()
        finally:
            self._connection_closed.set()
            if self._thread is not None:
                self._thread.join(timeout=5)
                self._thread = None


__all__ = [
    "IbkrSession",
    "make_stock_contract",
    "make_conid_contract",
]
