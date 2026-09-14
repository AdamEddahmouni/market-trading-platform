"""Item 7 — lawful OpenD ``get_market_snapshot`` BBO diagnostic (Lane C).

Read-only. Never fabricates bid/ask from ``last_price``. Never redefines
``US_EQUITY_L1``. Distinct capability ``SNAPSHOT_BBO`` for vendor snapshot BBO.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRANSPORT_PATH = _REPO_ROOT / "tools" / "moomoo" / "opend_quote_transport.py"

MOOMOO_OPEND_PROVIDER_ID = "moomoo.opend.observational"
SNAPSHOT_BBO_CAPABILITY = "SNAPSHOT_BBO"
ITEM7_ADAPTER_VERSION = "1.0.0"
VENDOR_API_METHOD = "OpenQuoteContext.get_market_snapshot"

OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED = "REAL_SNAPSHOT_BBO_VALIDATED"
OUTCOME_DERIVED_BBO_DESIGN_REQUIRED = "DERIVED_BBO_DESIGN_REQUIRED"

DEFAULT_SYMBOL = "US.AAPL"
DEFAULT_STALE_THRESHOLD_NS = 120_000_000_000


@dataclass(frozen=True, slots=True)
class VendorSnapshotFetch:
    reason_code: str | None
    row: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class BboClocks:
    request_time_ns: int
    provider_time_ns: int | None
    receive_time_ns: int
    available_time_ns: int


@dataclass(frozen=True, slots=True)
class BboDiagnostic:
    lane: str = "ITEM7_BBO_SNAPSHOT"
    symbol: str = DEFAULT_SYMBOL
    provider_id: str = MOOMOO_OPEND_PROVIDER_ID
    capability: str = SNAPSHOT_BBO_CAPABILITY
    identity: str = f"{MOOMOO_OPEND_PROVIDER_ID}:{SNAPSHOT_BBO_CAPABILITY}"
    clocks: BboClocks | None = None
    last_price: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    market_status: str | None = None
    entitlement: str = "UNKNOWN"
    bbo_source: str = "VENDOR_MARKET_SNAPSHOT"
    quality_flags: tuple[str, ...] = ()
    temporal_order_valid: bool = True
    raw_hash: str | None = None
    adapter_version: str = ITEM7_ADAPTER_VERSION
    vendor_api_method: str = VENDOR_API_METHOD
    lane_outcome: str = ""
    derived_design_note: str | None = None
    probe_status: str = "OK"
    block_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.clocks is not None:
            payload["clocks"] = asdict(self.clocks)
        return payload


def monotonic_wall_ns() -> int:
    return time.time_ns()


def is_us_equity_rth(now: datetime | None = None) -> bool:
    """US cash regular session (NYSE), excluding weekends."""

    moment = now or datetime.now(_ET)
    if moment.weekday() >= 5:
        return False
    open_minutes = 9 * 60 + 30
    close_minutes = 16 * 60
    minutes = moment.hour * 60 + moment.minute
    return open_minutes <= minutes < close_minutes


def opend_reachable(host: str, port: int, timeout_sec: float = 0.4) -> bool:
    if host not in _LOOPBACK_HOSTS:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def raw_row_sha256(row: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(row), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_positive_price(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price != price or price in {float("inf"), float("-inf")}:
        return None
    return price


def _parse_size(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        size = float(value)
    except (TypeError, ValueError):
        return None
    if size < 0 or size != size:
        return None
    return size


def _load_transport_module() -> Any | None:
    if not _TRANSPORT_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("imp_opend_quote_transport_item7", _TRANSPORT_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001
        return None
    return module


def fetch_vendor_market_snapshot(
    symbol: str,
    *,
    host: str,
    port: int,
    sdk: Any | None = None,
) -> VendorSnapshotFetch:
    """``get_market_snapshot`` row only — no bid/ask synthesis, no last_price gate."""

    transport = _load_transport_module()
    if transport is None:
        return VendorSnapshotFetch("MOOMOO_TRANSPORT_MISSING", None)
    if host not in _LOOPBACK_HOSTS:
        return VendorSnapshotFetch("OPEND_NON_LOOPBACK_BLOCKED", None)

    ft = sdk if sdk is not None else transport.load_vendor_sdk()
    if ft is None or not hasattr(ft, "OpenQuoteContext"):
        return VendorSnapshotFetch("MOOMOO_SDK_MISSING", None)
    if not hasattr(ft, "RET_OK"):
        return VendorSnapshotFetch("MOOMOO_PROTOCOL_ERROR", None)

    code = transport._provider_code(symbol)  # noqa: SLF001 — shared normalization
    if not code:
        return VendorSnapshotFetch("MOOMOO_PROTOCOL_ERROR", None)

    ctx = None
    try:
        ctx = ft.OpenQuoteContext(host=host, port=port)
        ret, state = ctx.get_global_state()
        if ret != ft.RET_OK:
            return VendorSnapshotFetch("MOOMOO_PROTOCOL_ERROR", None)
        if not transport._qot_logined(state):  # noqa: SLF001
            return VendorSnapshotFetch("MOOMOO_AUTH_FAILURE", None)
        snap_ret, data = ctx.get_market_snapshot([code])
        if snap_ret != ft.RET_OK:
            return VendorSnapshotFetch("MOOMOO_ENTITLEMENT_OR_PROTOCOL", None)
        row = transport._matching_row(transport._snapshot_rows(data), code)  # noqa: SLF001
        if row is None:
            return VendorSnapshotFetch("MOOMOO_PROTOCOL_ERROR", None)
        return VendorSnapshotFetch(None, row)
    except Exception:  # noqa: BLE001
        return VendorSnapshotFetch("MOOMOO_PROTOCOL_ERROR", None)
    finally:
        if ctx is not None:
            closer = getattr(ctx, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass


def provider_time_ns_from_row(row: Mapping[str, Any], *, receive_time_ns: int) -> int | None:
    from market_platform_foundation.market_data.provider_time import event_time_ns_from_payload

    return event_time_ns_from_payload(dict(row), received_ns=receive_time_ns)


def assess_snapshot_bbo(
    row: Mapping[str, Any],
    *,
    clocks: BboClocks,
    stale_threshold_ns: int = DEFAULT_STALE_THRESHOLD_NS,
    delayed_sec_statuses: frozenset[str] | None = None,
) -> BboDiagnostic:
    """Classify vendor snapshot BBO without deriving prices from last."""

    delayed_tokens = delayed_sec_statuses or frozenset({"DELAYED", "DELAY", "NON_REALTIME"})
    receive_ns = clocks.receive_time_ns
    provider_ns = clocks.provider_time_ns
    if provider_ns is None:
        provider_ns = provider_time_ns_from_row(row, receive_time_ns=receive_ns)

    bid = _parse_positive_price(row.get("bid_price"))
    ask = _parse_positive_price(row.get("ask_price"))
    last = _parse_positive_price(row.get("last_price"))
    bid_size = _parse_size(row.get("bid_vol"))
    ask_size = _parse_size(row.get("ask_vol"))
    market_status = str(row.get("sec_status") or row.get("market_status") or "").strip() or None

    flags: list[str] = []
    temporal_valid = (
        clocks.request_time_ns <= receive_ns <= clocks.available_time_ns
        and (provider_ns is None or clocks.request_time_ns <= provider_ns <= receive_ns)
    )
    if not temporal_valid:
        flags.append("TEMPORAL_ORDER_VIOLATION")

    entitlement = "ENTITLED"
    if bid is None or ask is None:
        flags.append("BBO_MISSING_BID_ASK")
    elif bid > ask:
        flags.append("BBO_INVALID_SPREAD")

    if provider_ns is not None and receive_ns - provider_ns > stale_threshold_ns:
        flags.append("BBO_STALE")

    status_upper = (market_status or "").upper()
    if status_upper and any(token in status_upper for token in delayed_tokens):
        flags.append("BBO_DELAYED")

    bbo_valid = (
        bid is not None
        and ask is not None
        and bid <= ask
        and "BBO_STALE" not in flags
        and "BBO_DELAYED" not in flags
        and temporal_valid
    )
    if bbo_valid:
        flags.append("BBO_VALID")

    if bbo_valid:
        lane_outcome = OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED
        derived_note = None
    elif last is not None and ("BBO_MISSING_BID_ASK" in flags or "BBO_INVALID_SPREAD" in flags):
        lane_outcome = OUTCOME_DERIVED_BBO_DESIGN_REQUIRED
        derived_note = (
            "Vendor snapshot lacks lawful top-of-book; G5/depth-derived BBO would be "
            "a separate labeled capability — not SNAPSHOT_BBO."
        )
    else:
        lane_outcome = OUTCOME_DERIVED_BBO_DESIGN_REQUIRED
        derived_note = (
            "Snapshot row does not admit REAL_SNAPSHOT_BBO_VALIDATED; depth/G5 design "
            "review required before any derived BBO."
        )

    symbol = str(row.get("code") or DEFAULT_SYMBOL).strip() or DEFAULT_SYMBOL
    return BboDiagnostic(
        symbol=symbol,
        clocks=BboClocks(
            request_time_ns=clocks.request_time_ns,
            provider_time_ns=provider_ns,
            receive_time_ns=receive_ns,
            available_time_ns=clocks.available_time_ns,
        ),
        last_price=last,
        bid_price=bid,
        ask_price=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        market_status=market_status,
        entitlement=entitlement,
        quality_flags=tuple(dict.fromkeys(flags)),
        temporal_order_valid=temporal_valid,
        raw_hash=raw_row_sha256(row),
        lane_outcome=lane_outcome,
        derived_design_note=derived_note,
    )


def blocked_diagnostic(
    *,
    symbol: str,
    block_reason: str,
    request_time_ns: int | None = None,
    require_rth: bool = False,
    rth_open: bool = False,
) -> BboDiagnostic:
    now = request_time_ns if request_time_ns is not None else monotonic_wall_ns()
    return BboDiagnostic(
        symbol=symbol,
        clocks=BboClocks(request_time_ns=now, provider_time_ns=None, receive_time_ns=now, available_time_ns=now),
        entitlement="NOT_ENTITLED" if block_reason.startswith("MOOMOO_") else "UNKNOWN",
        probe_status="BLOCKED",
        block_reason=block_reason,
        lane_outcome="",
        extra={"require_rth": require_rth, "us_equity_rth": rth_open},
    )


def run_live_probe(
    *,
    symbol: str = DEFAULT_SYMBOL,
    host: str = "127.0.0.1",
    port: int = 11111,
    require_rth: bool = True,
    stale_threshold_ns: int = DEFAULT_STALE_THRESHOLD_NS,
    fetcher: Callable[..., VendorSnapshotFetch] | None = None,
    sdk: Any | None = None,
    clock: datetime | None = None,
) -> BboDiagnostic:
    """Probe OpenD when reachable; honest block otherwise."""

    request_ns = monotonic_wall_ns()
    rth_open = is_us_equity_rth(clock)
    injected_fetch = fetcher is not None
    if require_rth and not rth_open:
        return blocked_diagnostic(
            symbol=symbol,
            block_reason="OUTSIDE_US_EQUITY_RTH",
            request_time_ns=request_ns,
            require_rth=True,
            rth_open=False,
        )
    if not injected_fetch:
        if not opend_reachable(host, port):
            return blocked_diagnostic(symbol=symbol, block_reason="OPEND_UNAVAILABLE", request_time_ns=request_ns)
        transport = _load_transport_module()
        if transport is None or not transport.sdk_available():
            return blocked_diagnostic(symbol=symbol, block_reason="MOOMOO_SDK_MISSING", request_time_ns=request_ns)

    do_fetch = fetcher or fetch_vendor_market_snapshot
    fetched = do_fetch(symbol, host=host, port=port, sdk=sdk)
    receive_ns = monotonic_wall_ns()
    if fetched.reason_code is not None:
        reason = fetched.reason_code
        entitlement = (
            "ENTITLEMENT_FAILURE"
            if reason in {"MOOMOO_AUTH_FAILURE", "MOOMOO_ENTITLEMENT_OR_PROTOCOL"}
            else "NOT_ENTITLED"
        )
        flags: tuple[str, ...] = ("ENTITLEMENT_FAILURE",) if entitlement == "ENTITLEMENT_FAILURE" else ()
        now = receive_ns
        return BboDiagnostic(
            symbol=symbol,
            clocks=BboClocks(
                request_time_ns=request_ns,
                provider_time_ns=None,
                receive_time_ns=now,
                available_time_ns=now,
            ),
            entitlement=entitlement,
            quality_flags=flags,
            probe_status="BLOCKED",
            block_reason=reason,
            lane_outcome="",
        )
    if fetched.row is None:
        return blocked_diagnostic(symbol=symbol, block_reason="MOOMOO_PROTOCOL_ERROR", request_time_ns=request_ns)

    available_ns = monotonic_wall_ns()
    provider_ns = provider_time_ns_from_row(fetched.row, receive_time_ns=receive_ns)
    clocks = BboClocks(
        request_time_ns=request_ns,
        provider_time_ns=provider_ns,
        receive_time_ns=receive_ns,
        available_time_ns=available_ns,
    )
    return assess_snapshot_bbo(fetched.row, clocks=clocks, stale_threshold_ns=stale_threshold_ns)


__all__ = [
    "BboClocks",
    "BboDiagnostic",
    "DEFAULT_SYMBOL",
    "OUTCOME_DERIVED_BBO_DESIGN_REQUIRED",
    "OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED",
    "SNAPSHOT_BBO_CAPABILITY",
    "VendorSnapshotFetch",
    "assess_snapshot_bbo",
    "blocked_diagnostic",
    "fetch_vendor_market_snapshot",
    "is_us_equity_rth",
    "opend_reachable",
    "raw_row_sha256",
    "run_live_probe",
]
