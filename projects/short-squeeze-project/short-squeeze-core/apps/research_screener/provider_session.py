"""One shared, bounded, read-only provider session.

A single gateway conversation is reused for every request. Nothing here opens a socket per
field, and the reserved client-ID sequence is disjoint from the Batch 05 research
exporter's, so the two can never collide.

Every call is wrapped so that a provider fault becomes a *status*, never an exception that
reaches the interface. A partial outage produces partial evidence.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from . import discovery as discovery_module
from .ibkr_session import (
    APP_CLIENT_ID_SEQUENCE,
    QuoteTicks,
    ScannerRow,
    build_session_class,
    ensure_tools_importable,
)

#: Read-only request shape for the current trailing window.
CURRENT_DURATION = "1 D"
CURRENT_BAR_SIZE = "1 min"
CURRENT_WHAT_TO_SHOW = "TRADES"
CURRENT_USE_RTH = 0
CURRENT_FORMAT_DATE = 2

CONTRACT_TIMEOUT_S = 8.0
HISTORICAL_TIMEOUT_S = 12.0
QUOTE_TIMEOUT_S = 5.0

#: Provider pacing. IBKR documents a hard limit of no more than 60 historical-data
#: requests within any rolling 10-minute period. The application enforces that as a real
#: budget: when the budget is exhausted the request is **refused and reported**, and the
#: previous snapshot is retained as STALE. It is never quietly exceeded.
HISTORICAL_PACING_WINDOW_S = 600
HISTORICAL_PACING_MAX = 60

#: Small gap between consecutive requests, well inside the ~50 messages/second guidance.
INTER_REQUEST_DELAY_S = 0.35

#: Requested market-data type. ``3`` = DELAYED, which the provider silently upgrades to
#: REALTIME when the account is entitled. What is actually granted is read back from the
#: provider's own ``marketDataType`` callback and never inferred.
REQUESTED_MARKET_DATA_TYPE = 3


class ProviderCallState(StrEnum):
    OK = "OK"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    #: No provider exists for this surface at all.
    NOT_CONFIGURED = "NOT CONFIGURED"
    #: A provider exists but this surface has not been exercised yet in this session.
    #: Distinct from NOT CONFIGURED: it is an absence of attempts, not of capability.
    NOT_ATTEMPTED = "NOT ATTEMPTED"
    PERMISSION_UNAVAILABLE = "PERMISSION_UNAVAILABLE"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class CallStatus:
    """The structured outcome of one provider surface. Never an exception, never silent."""

    name: str
    state: ProviderCallState = ProviderCallState.NOT_ATTEMPTED
    detail: str = "Not exercised yet in this session."
    last_success_at: str | None = None
    last_attempt_at: str | None = None
    last_error: str | None = None

    def succeeded(self, detail: str = "") -> None:
        self.state = ProviderCallState.OK
        self.detail = detail
        self.last_success_at = _iso(_now())
        self.last_attempt_at = self.last_success_at
        self.last_error = None

    def failed(self, message: str, state: ProviderCallState = ProviderCallState.FAILED) -> None:
        self.state = state
        self.detail = message
        self.last_attempt_at = _iso(_now())
        self.last_error = message

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": str(self.state),
            "detail": self.detail,
            "last_success_at": self.last_success_at,
            "last_attempt_at": self.last_attempt_at,
            "last_error": self.last_error,
        }


@dataclass(frozen=True, slots=True)
class CurrentBar:
    """One completed provider bar, exactly as received."""

    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(slots=True)
class SymbolCollection:
    """Everything one read-only pass gathered for a single symbol."""

    symbol: str
    resolved: bool = False
    con_id: int | None = None
    long_name: str = ""
    primary_exchange: str = ""
    currency: str = ""
    bars: list[CurrentBar] = field(default_factory=list)
    quote: QuoteTicks | None = None
    borrow_fee_pct: float | None = None
    retrieved_at: str = ""
    reason: str | None = None
    provider_errors: list[dict[str, Any]] = field(default_factory=list)


class ProviderUnavailable(RuntimeError):
    """The gateway could not be reached, or ``ibapi`` is not installed."""


@dataclass(frozen=True, slots=True)
class IbkrEndpoint:
    """Explicit IB Gateway socket target (cloud sidecar or remote host)."""

    host: str
    port: int
    client_id_sequence: tuple[int, ...] = APP_CLIENT_ID_SEQUENCE


def ibkr_endpoint_from_config(ibkr) -> IbkrEndpoint | None:
    if not ibkr.enabled:
        return None
    sequence = tuple(
        dict.fromkeys((ibkr.client_id, *APP_CLIENT_ID_SEQUENCE))
    )
    return IbkrEndpoint(host=ibkr.host, port=ibkr.port, client_id_sequence=sequence)


def _is_loopback_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost"}


class LiveProvider:
    """A lazily connected, reconnectable, single-conversation read-only provider."""

    def __init__(
        self,
        *,
        ibkr_endpoint: IbkrEndpoint | None = None,
        session_factory=None,
    ) -> None:
        self._lock = threading.RLock()
        self._session: Any = None
        self._connection: Any = None
        self._session_factory = session_factory
        self._ibkr_endpoint = ibkr_endpoint
        self._req_id = 1000
        self.connection_status = CallStatus("IB Gateway")
        self.scanner_status = CallStatus("Scanner")
        self.quote_status = CallStatus("Quotes")
        self.historical_status = CallStatus("Historical Bars")
        self.borrow_status = CallStatus("Borrow / Shortability")
        self.news_status = CallStatus("News")
        self.short_interest_status = CallStatus("Short Interest")
        self.float_status = CallStatus("Float")
        self.sec_status = CallStatus("SEC EDGAR")
        self.halts_status = CallStatus("Trading Halts")
        self.pacing_status = CallStatus("Pacing budget")
        # SEC EDGAR is public and always available
        self.sec_status.succeeded("Public SEC EDGAR API available (no API key required).")
        self._market_data_type_granted: int | None = None
        self._historical_request_times: list[float] = []

    # ------------------------------------------------------------ connection

    def _next_req_id(self) -> int:
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _build_session(self):
        if self._session_factory is not None:
            return self._session_factory()
        return build_session_class()()

    def ensure_connected(self) -> None:
        """Connect if not already connected. Reconnects transparently after a restart."""
        with self._lock:
            try:
                from tools.ibkr_historical_export.collector import _session_is_live
            except ImportError:
                _session_is_live = None  # type: ignore[assignment,misc]
            if self._session is not None:
                try:
                    live = (
                        _session_is_live(self._session)
                        if _session_is_live is not None
                        else self._session.isConnected()
                    )
                    if live:
                        return
                except Exception:  # noqa: BLE001 - a dead session is simply replaced
                    pass
                self.close()
            try:
                ensure_tools_importable()
                from tools.ibkr_historical_export import policy as ibkr_policy
                from tools.ibkr_historical_export.collector import (
                    connect_configured,
                    probe_and_connect,
                    reconnect_using_result,
                )
            except ImportError as exc:
                self.connection_status.failed(
                    "The official IBKR API package is not importable in this environment, "
                    "so current-data mode is unavailable. Frozen Research mode is unaffected.",
                    ProviderCallState.UNAVAILABLE,
                )
                raise ProviderUnavailable(self.connection_status.detail) from exc

            from .ibkr_session import APP_CLIENT_ID_SEQUENCE

            original = ibkr_policy.CLIENT_ID_SEQUENCE
            try:
                ibkr_policy.CLIENT_ID_SEQUENCE = APP_CLIENT_ID_SEQUENCE
                endpoint = self._ibkr_endpoint
                if self._connection is not None:
                    session, result = reconnect_using_result(
                        self._build_session,
                        self._connection,
                        host=endpoint.host if endpoint is not None else ibkr_policy.HOST,
                    )
                elif endpoint is not None and not _is_loopback_host(endpoint.host):
                    session, result = connect_configured(
                        self._build_session,
                        endpoint.host,
                        endpoint.port,
                        endpoint.client_id_sequence,
                    )
                else:
                    session, result = probe_and_connect(self._build_session)
            except Exception as exc:  # noqa: BLE001
                self.connection_status.failed(f"{type(exc).__name__}: {exc}")
                raise ProviderUnavailable(str(exc)) from exc
            finally:
                ibkr_policy.CLIENT_ID_SEQUENCE = original

            if session is None:
                self.connection_status.failed(
                    "No IB Gateway / TWS API socket accepted a read-only connection. "
                    "Verify IBKR_HOST, IBKR_PORT, and IBKR_CLIENT_ID, or use Frozen Research mode.",
                    ProviderCallState.UNAVAILABLE,
                )
                raise ProviderUnavailable(self.connection_status.detail)

            self._session = session
            self._connection = result
            observed_host = (
                self._ibkr_endpoint.host if self._ibkr_endpoint is not None else "127.0.0.1"
            )
            self.connection_status.succeeded(
                f"Connected read-only on {observed_host}:{getattr(result, 'observed_port', '?')}"
            )
            try:
                session.request_market_data_type(REQUESTED_MARKET_DATA_TYPE)
            except Exception:  # noqa: BLE001 - entitlement is reported, never assumed
                pass

    def close(self) -> None:
        with self._lock:
            if self._session is not None:
                try:
                    self._session.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            self._session = None
            self._connection = None

    def connection_info(self) -> dict[str, Any]:
        result = self._connection
        if result is None:
            return {"status": "DISCONNECTED", "port": None, "server_version": None,
                    "provider_current_time": None}
        epoch = getattr(result, "current_time_epoch", None)
        return {
            "status": str(getattr(result, "status", "UNKNOWN")),
            "port": getattr(result, "observed_port", None),
            "client_id": getattr(result, "client_id", None),
            "server_version": getattr(result, "server_version", None),
            "provider_current_time": (
                _iso(datetime.fromtimestamp(epoch, tz=UTC)) if epoch else None
            ),
        }

    @property
    def connected(self) -> bool:
        session = self._session
        if session is None:
            return False
        try:
            from tools.ibkr_historical_export.collector import _session_is_live
            return _session_is_live(session)
        except Exception:  # noqa: BLE001
            return False

    @property
    def market_data_type_granted(self) -> int | None:
        return self._market_data_type_granted

    # -------------------------------------------------------------- discovery

    def run_discovery(
        self, profile: discovery_module.DiscoveryProfile, *, limit: int | None = None
    ) -> list[discovery_module.CurrentDiscoveryCandidate]:
        """Run one scanner subscription. A scanner failure returns [] and a status."""
        if profile.scanner is None:
            self.scanner_status.failed(
                "This profile does not use the provider scanner.",
                ProviderCallState.NOT_CONFIGURED,
            )
            return []
        try:
            self.ensure_connected()
        except ProviderUnavailable as exc:
            self.scanner_status.failed(str(exc), ProviderCallState.UNAVAILABLE)
            return []
        with self._lock:
            session = self._session
            if session is None:
                self.scanner_status.failed("No provider session.", ProviderCallState.UNAVAILABLE)
                return []
            try:
                subscription = profile.scanner.to_subscription()
                rows, errors, completed = session.run_scanner(
                    self._next_req_id(), subscription, discovery_module.SCANNER_TIMEOUT_S
                )
            except Exception as exc:  # noqa: BLE001 - a scanner fault must not crash the app
                self.scanner_status.failed(f"{type(exc).__name__}: {exc}")
                return []
        if not rows:
            message = "; ".join(f"{code}: {msg}" for code, msg, _ in errors) or (
                "The provider scanner returned no rows for this configuration."
                if completed
                else "The provider scanner did not respond before the timeout."
            )
            state = (
                ProviderCallState.PERMISSION_UNAVAILABLE
                if any(code in (10197, 354, 162) for code, _m, _t in errors)
                else ProviderCallState.FAILED
            )
            self.scanner_status.failed(message, state)
            return []
        self.scanner_status.succeeded(
            f"{len(rows)} row(s) from scan class {profile.scanner.scan_code}"
        )
        return discovery_module.candidates_from_scanner(
            rows, profile.profile_id,
            limit=limit or profile.scanner.number_of_rows,
        )

    def scanner_parameters_available(self) -> bool:
        """Capability probe: does this gateway serve the scanner-parameter document?"""
        try:
            self.ensure_connected()
        except ProviderUnavailable:
            return False
        with self._lock:
            session = self._session
            if session is None:
                return False
            try:
                return bool(session.fetch_scanner_parameters(discovery_module.SCANNER_TIMEOUT_S))
            except Exception:  # noqa: BLE001
                return False

    # ------------------------------------------------------------- pacing

    def _prune_pacing(self) -> None:
        cutoff = _now().timestamp() - HISTORICAL_PACING_WINDOW_S
        self._historical_request_times = [
            item for item in self._historical_request_times if item >= cutoff
        ]

    def historical_budget_remaining(self) -> int:
        with self._lock:
            self._prune_pacing()
            return max(0, HISTORICAL_PACING_MAX - len(self._historical_request_times))

    def pacing_state(self) -> dict[str, Any]:
        remaining = self.historical_budget_remaining()
        return {
            "remaining": remaining,
            "limit": HISTORICAL_PACING_MAX,
            "window_seconds": HISTORICAL_PACING_WINDOW_S,
            "detail": (
                f"{remaining} of {HISTORICAL_PACING_MAX} historical requests remain in the "
                f"rolling {HISTORICAL_PACING_WINDOW_S // 60}-minute provider pacing window."
            ),
        }

    # ----------------------------------------------------------- symbol pass

    def collect_symbol(self, symbol: str, *, want_quote: bool = True) -> SymbolCollection:
        """Resolve the contract, pull the trailing window, and take one quote snapshot."""
        collection = SymbolCollection(symbol=symbol)
        if self.historical_budget_remaining() <= 0:
            state = self.pacing_state()
            collection.reason = (
                "Refused by the provider pacing budget: "
                + state["detail"]
                + " The previous snapshot is retained and marked STALE rather than "
                "exceeding the provider's documented request limit."
            )
            self.pacing_status.failed(collection.reason, ProviderCallState.UNAVAILABLE)
            return collection
        try:
            self.ensure_connected()
        except ProviderUnavailable as exc:
            collection.reason = str(exc)
            return collection

        with self._lock:
            session = self._session
            if session is None:
                collection.reason = "No provider session."
                return collection

            try:
                candidates, contract_errors = session.request_contract_details(
                    self._next_req_id(), symbol, CONTRACT_TIMEOUT_S
                )
            except Exception as exc:  # noqa: BLE001
                collection.reason = f"Contract resolution failed: {type(exc).__name__}: {exc}"
                return collection
            if not candidates:
                collection.reason = (
                    f"The provider returned no US equity contract for {symbol!r}. Nothing "
                    "was assumed and no value was substituted."
                )
                collection.provider_errors = [
                    {"code": code, "message": message}
                    for _rid, message, code in contract_errors
                ]
                return collection

            chosen = candidates[0]
            collection.resolved = True
            collection.con_id = chosen.con_id
            collection.long_name = chosen.long_name
            collection.primary_exchange = chosen.primary_exchange
            collection.currency = chosen.currency

            from tools.ibkr_historical_export.session import make_conid_contract

            contract = make_conid_contract(chosen.con_id, symbol)

            # -- historical bars ------------------------------------------------
            try:
                spec = self._request_spec()
                self._prune_pacing()
                self._historical_request_times.append(_now().timestamp())
                self.pacing_status.succeeded(self.pacing_state()["detail"])
                bars, bar_errors, _completed = session.request_historical(
                    self._next_req_id(), spec, symbol, chosen.con_id, contract,
                    HISTORICAL_TIMEOUT_S,
                )
                collection.bars = [
                    CurrentBar(
                        timestamp_utc=bar.timestamp_utc,
                        open=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        close=float(bar.close),
                        volume=None if bar.volume is None else _safe_float(bar.volume),
                    )
                    for bar in bars
                ]
                collection.provider_errors.extend(
                    {"code": code, "message": message} for _rid, message, code in bar_errors
                )
                if collection.bars:
                    self.historical_status.succeeded(
                        f"{len(collection.bars)} bar(s) for {symbol}"
                    )
                else:
                    self.historical_status.failed(
                        f"No completed bars returned for {symbol}."
                    )
            except Exception as exc:  # noqa: BLE001
                self.historical_status.failed(f"{type(exc).__name__}: {exc}")

            # -- quote ----------------------------------------------------------
            if want_quote:
                try:
                    quote = session.fetch_quote(
                        self._next_req_id(), contract, symbol, QUOTE_TIMEOUT_S
                    )
                    collection.quote = quote
                    self._market_data_type_granted = quote.market_data_type
                    if quote.prices or quote.sizes:
                        self.quote_status.succeeded(
                            f"{quote.market_data_type_label} quote for {symbol}"
                        )
                    else:
                        message = "; ".join(
                            f"{item['code']}: {item['message']}" for item in quote.errors
                        ) or "The provider returned no quote ticks for this symbol."
                        permission = any(
                            item["code"] in (354, 10167, 10168, 10187, 10197, 10225)
                            for item in quote.errors
                        )
                        self.quote_status.failed(
                            message,
                            ProviderCallState.PERMISSION_UNAVAILABLE
                            if permission
                            else ProviderCallState.FAILED,
                        )
                    self._record_borrow_status(quote)
                except Exception as exc:  # noqa: BLE001
                    self.quote_status.failed(f"{type(exc).__name__}: {exc}")

        collection.retrieved_at = _iso(_now())
        return collection

    def _record_borrow_status(self, quote: QuoteTicks) -> None:
        """Shortability comes from generic tick 236 when the entitlement allows it."""
        if "shortable_indicator" in quote.generics or "shortable_shares" in quote.sizes:
            self.borrow_status.succeeded(
                "Provider shortability ticks received (generic tick 236)."
            )
            return
        permission = any(
            item["code"] in (354, 10167, 10168, 10187, 10197, 10225) for item in quote.errors
        )
        self.borrow_status.failed(
            "The provider returned no shortability tick for this contract under the "
            "current entitlement. No borrow value is inferred and none is substituted."
            if permission
            else "No shortability tick was returned. No borrow value is inferred.",
            ProviderCallState.PERMISSION_UNAVAILABLE if permission else ProviderCallState.FAILED,
        )

    def _request_spec(self):
        ensure_tools_importable()
        from tools.ibkr_historical_export.cohort import HistoricalRequestSpec

        from .current_eval import CURRENT_REQUEST_NAME

        end = _now()
        return HistoricalRequestSpec(
            request_name=CURRENT_REQUEST_NAME,
            end_datetime="",  # empty string = the provider's own current time
            duration_str=CURRENT_DURATION,
            bar_size_setting=CURRENT_BAR_SIZE,
            what_to_show=CURRENT_WHAT_TO_SHOW,
            use_rth=CURRENT_USE_RTH,
            format_date=CURRENT_FORMAT_DATE,
            keep_up_to_date=False,
            expected_window_start=end - timedelta(days=1),
            expected_window_end=end,
        )

    # ---------------------------------------------------------------- status

    def statuses(self) -> list[dict[str, Any]]:
        """Every provider surface with its own state, error and last-success time."""
        self.news_status.state = ProviderCallState.NOT_CONFIGURED
        self.news_status.detail = (
            "No lawful news provider is configured. The archived Finviz TLS-impersonation "
            "helper bypasses access controls and is deliberately excluded."
        )
        self.short_interest_status.state = ProviderCallState.NOT_CONFIGURED
        self.short_interest_status.detail = (
            "No published short-interest provider is configured. No value is inferred."
        )
        self.float_status.state = ProviderCallState.NOT_CONFIGURED
        self.float_status.detail = "No float provider is configured. No value is inferred."
        # SEC EDGAR is available (public, no API key)
        self.sec_status.state = ProviderCallState.OK
        self.sec_status.detail = (
            "Public SEC EDGAR API (no API key required). Recent filings available on demand."
        )
        self.halts_status.state = (
            ProviderCallState.OK if self.connected else ProviderCallState.NOT_CONFIGURED
        )
        self.halts_status.detail = (
            "Halt status available via IBKR generic tick 49."
            if self.connected
            else "Not available without a connected gateway."
        )
        # Namespaced so these never collide with the TCP-probe entries of the same name.
        out = []
        for status in (
            self.connection_status, self.scanner_status, self.quote_status,
            self.historical_status, self.borrow_status, self.short_interest_status,
            self.float_status, self.sec_status, self.halts_status,
            self.news_status, self.pacing_status,
        ):
            entry = status.as_dict()
            entry["surface"] = entry["name"]
            entry["name"] = f"Current: {entry['name']}"
            out.append(entry)
        return out


class CloudUnavailableProvider(LiveProvider):
    """IBKR stub when cloud mode runs without ``IBKR_ENABLED``."""

    def __init__(self) -> None:
        super().__init__()
        self.connection_status.failed(
            "IBKR is disabled for this cloud deployment. Set IBKR_ENABLED=true and "
            "configure IBKR_HOST, IBKR_PORT, and IBKR_CLIENT_ID to connect a gateway.",
            ProviderCallState.UNAVAILABLE,
        )

    def ensure_connected(self) -> None:
        raise ProviderUnavailable(self.connection_status.detail)


def _safe_float(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


__all__ = [
    "CONTRACT_TIMEOUT_S",
    "CURRENT_BAR_SIZE",
    "CURRENT_DURATION",
    "HISTORICAL_TIMEOUT_S",
    "INTER_REQUEST_DELAY_S",
    "QUOTE_TIMEOUT_S",
    "REQUESTED_MARKET_DATA_TYPE",
    "CallStatus",
    "CloudUnavailableProvider",
    "CurrentBar",
    "IbkrEndpoint",
    "LiveProvider",
    "ProviderCallState",
    "ProviderUnavailable",
    "SymbolCollection",
    "ibkr_endpoint_from_config",
]
