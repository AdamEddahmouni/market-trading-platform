"""Moomoo OpenD observational equity quote — Primary L1 (DoD item 2).

Loopback OpenD only; never mock. Reachability is checked at call time inside
``fetch_quote`` (not cached at import/composition time), so a daemon that
goes up or down mid-process is reflected on the next call. When the daemon
is unreachable this fails closed with ``OPEND_UNAVAILABLE``. When it is
reachable, the vendor SDK is loaded from ``tools/moomoo/opend_quote_transport.py``
(the ``moomoo-api`` package is intentionally not a dependency of this
foundation — see ``docs/providers/MOOMOO_OBSERVATIONAL.md``). Missing SDK,
auth failure, protocol error, or a vendor row without ``last_price`` fail
closed. This adapter never synthesizes ``last_price`` from bid/ask/close.
"""

from __future__ import annotations

import importlib.util
import socket
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ...clock import monotonic_wall_ns
from ...local_state.paths import REPO_ROOT
from ...market_data.live_config import moomoo_host, moomoo_port
from ...market_data.normalization import NORMALIZATION_VERSION, canonical_symbol
from ...market_data.provider_time import parse_provider_datetime_ns
from ..contracts import ProviderResult
from ..moomoo_opend_capability import MOOMOO_OPEND_PROVIDER_ID, US_EQUITY_L1_CAPABILITY

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_TOOLS_TRANSPORT_PATH = REPO_ROOT / "tools" / "moomoo" / "opend_quote_transport.py"

OPEND_NON_LOOPBACK_BLOCKED = "OPEND_NON_LOOPBACK_BLOCKED"
OPEND_UNAVAILABLE = "OPEND_UNAVAILABLE"
MOOMOO_SDK_MISSING = "MOOMOO_SDK_MISSING"
MOOMOO_AUTH_FAILURE = "MOOMOO_AUTH_FAILURE"
MOOMOO_PROTOCOL_ERROR = "MOOMOO_PROTOCOL_ERROR"
MOOMOO_LAST_PRICE_MISSING = "MOOMOO_LAST_PRICE_MISSING"
MOOMOO_TRANSPORT_NOT_IMPLEMENTED = "MOOMOO_TRANSPORT_NOT_IMPLEMENTED"
SYMBOL_REQUIRED = "INSTRUMENT_ID_REQUIRED"
MISSING_TIMESTAMP = "MISSING_TIMESTAMP"


@dataclass(frozen=True, slots=True)
class OpenDSnapshotResult:
    """Vendor snapshot or an honest unavailable reason. Never a synthesized tick."""

    reason_code: str | None = None
    row: Mapping[str, Any] | None = None


class OpenDQuoteTransport(Protocol):
    """Observational quote transport. Quote context only; no trade methods."""

    def fetch_snapshot(self, *, symbol: str, host: str, port: int) -> OpenDSnapshotResult: ...


def opend_endpoint() -> tuple[str, int]:
    """Read the configured OpenD endpoint via the canonical live_config accessors."""

    host = (moomoo_host() or "").strip() or "127.0.0.1"
    try:
        port = moomoo_port()
    except (TypeError, ValueError):
        port = 11111
    return host, port


def opend_is_loopback(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


def opend_reachable(*, host: str | None = None, port: int | None = None, timeout_sec: float = 0.4) -> bool:
    """TCP-connect probe only. Never treated as evidence of quote availability."""

    target_host, target_port = (host, port) if host is not None and port is not None else opend_endpoint()
    if not opend_is_loopback(target_host):
        return False
    try:
        with socket.create_connection((target_host, target_port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def opend_sdk_available() -> bool:
    """True when the optional vendor SDK imports. Not a tick and not reachability."""

    module = _load_tools_transport_module()
    if module is None:
        return False
    checker = getattr(module, "sdk_available", None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except Exception:  # noqa: BLE001
        return False


def _load_tools_transport_module() -> Any | None:
    path = _TOOLS_TRANSPORT_PATH
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("imp_opend_quote_transport", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001
        return None
    return module


class VendorSdkOpenDQuoteTransport:
    """Default transport: outer tools/moomoo module; vendor package stays out of src."""

    def fetch_snapshot(self, *, symbol: str, host: str, port: int) -> OpenDSnapshotResult:
        module = _load_tools_transport_module()
        if module is None:
            return OpenDSnapshotResult(reason_code=MOOMOO_TRANSPORT_NOT_IMPLEMENTED)
        fetcher = getattr(module, "fetch_snapshot", None)
        if not callable(fetcher):
            return OpenDSnapshotResult(reason_code=MOOMOO_TRANSPORT_NOT_IMPLEMENTED)
        try:
            payload = fetcher(symbol, host=host, port=port)
        except Exception:  # noqa: BLE001
            return OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
        if not isinstance(payload, dict):
            return OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
        reason = payload.get("reason_code")
        row = payload.get("row")
        if reason:
            return OpenDSnapshotResult(reason_code=str(reason))
        if not isinstance(row, Mapping):
            return OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
        return OpenDSnapshotResult(row=row)


class MoomooOpenDEquityQuoteProvider:
    """Primary L1 equity quote slot. Fail-closed; never substitutes mock ticks."""

    provider_id = MOOMOO_OPEND_PROVIDER_ID
    capability = US_EQUITY_L1_CAPABILITY
    timeliness = "REAL_TIME"

    def __init__(self, *, transport: OpenDQuoteTransport | None = None) -> None:
        self._transport = transport if transport is not None else VendorSdkOpenDQuoteTransport()

    def fetch_quote(self, symbol: str) -> ProviderResult:
        wanted = str(symbol or "").strip().upper()
        if not wanted:
            return self._unavailable(SYMBOL_REQUIRED)
        host, port = opend_endpoint()
        if not opend_is_loopback(host):
            return self._unavailable(OPEND_NON_LOOPBACK_BLOCKED)
        if not opend_reachable(host=host, port=port):
            return self._unavailable(OPEND_UNAVAILABLE)

        snapshot = self._transport.fetch_snapshot(symbol=wanted, host=host, port=port)
        if snapshot.reason_code:
            return self._unavailable(snapshot.reason_code)
        if snapshot.row is None:
            return self._unavailable(MOOMOO_PROTOCOL_ERROR)

        event, reason_code = _quote_event_from_vendor_row(
            snapshot.row, symbol=wanted, received_ns=monotonic_wall_ns()
        )
        if event is None:
            return self._unavailable(reason_code or MOOMOO_PROTOCOL_ERROR)
        return ProviderResult(
            status="available",
            events=(event,),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def _unavailable(self, reason_code: str) -> ProviderResult:
        return ProviderResult(
            status="unavailable",
            reason_code=reason_code,
            provider_id=self.provider_id,
            capability=self.capability,
        )


def _required_last_price(row: Mapping[str, Any]) -> float | None:
    """Vendor ``last_price`` only. Never filled from bid/ask/close/session fields."""

    if "last_price" not in row:
        return None
    value = row.get("last_price")
    if value in {None, ""}:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price != price or price in {float("inf"), float("-inf")}:
        return None
    return price


def _optional_float(row: Mapping[str, Any], key: str) -> float | None:
    if key not in row:
        return None
    value = row.get(key)
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _vendor_event_time_ns(row: Mapping[str, Any]) -> int | None:
    for key in ("update_time", "time"):
        parsed = parse_provider_datetime_ns(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _quote_event_from_vendor_row(
    row: Mapping[str, Any], *, symbol: str, received_ns: int
) -> tuple[dict[str, Any] | None, str | None]:
    last_price = _required_last_price(row)
    if last_price is None:
        return None, MOOMOO_LAST_PRICE_MISSING
    event_time_ns = _vendor_event_time_ns(row)
    if event_time_ns is None:
        return None, MISSING_TIMESTAMP

    mapping = canonical_symbol(str(row.get("code") or symbol))
    raw_payload: dict[str, Any] = {"last_price": last_price}
    bid = _optional_float(row, "bid_price")
    ask = _optional_float(row, "ask_price")
    bid_vol = _optional_float(row, "bid_vol")
    ask_vol = _optional_float(row, "ask_vol")
    if bid is not None:
        raw_payload["bid_price"] = bid
    if ask is not None:
        raw_payload["ask_price"] = ask
    if bid_vol is not None:
        raw_payload["bid_vol"] = bid_vol
    if ask_vol is not None:
        raw_payload["ask_vol"] = ask_vol

    return (
        {
            "capability": US_EQUITY_L1_CAPABILITY,
            "clocks": {
                "event_time_ns": event_time_ns,
                "provider_time_ns": event_time_ns,
                "received_time_ns": received_ns,
            },
            "entitlement": "REAL_TIME",
            "instrument_id": mapping.instrument_id,
            "normalization_version": NORMALIZATION_VERSION,
            "provider": MOOMOO_OPEND_PROVIDER_ID,
            "provider_symbol": mapping.provider_symbol,
            "raw_payload": raw_payload,
            "sequence": event_time_ns,
            "timeliness": "REAL_TIME",
        },
        None,
    )


__all__ = [
    "MISSING_TIMESTAMP",
    "MOOMOO_AUTH_FAILURE",
    "MOOMOO_LAST_PRICE_MISSING",
    "MOOMOO_OPEND_PROVIDER_ID",
    "MOOMOO_PROTOCOL_ERROR",
    "MOOMOO_SDK_MISSING",
    "MOOMOO_TRANSPORT_NOT_IMPLEMENTED",
    "MoomooOpenDEquityQuoteProvider",
    "OPEND_NON_LOOPBACK_BLOCKED",
    "OPEND_UNAVAILABLE",
    "OpenDQuoteTransport",
    "OpenDSnapshotResult",
    "SYMBOL_REQUIRED",
    "US_EQUITY_L1_CAPABILITY",
    "VendorSdkOpenDQuoteTransport",
    "opend_endpoint",
    "opend_is_loopback",
    "opend_reachable",
    "opend_sdk_available",
]
