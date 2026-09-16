"""Item 7 — lawful OpenD ``get_market_snapshot`` BBO diagnostic (Lane C).

Read-only. Never fabricates bid/ask from ``last_price``. Never redefines
``US_EQUITY_L1``. Distinct capability ``SNAPSHOT_BBO`` for vendor snapshot BBO.
"""

from __future__ import annotations

import importlib.util
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from market_platform_foundation.market_data.moomoo_snapshot_bbo import (
    BboClocks,
    BboDiagnostic,
    DEFAULT_STALE_THRESHOLD_NS,
    DEFAULT_SYMBOL,
    ITEM7_ADAPTER_VERSION,
    MOOMOO_OPEND_PROVIDER_ID,
    OUTCOME_DERIVED_BBO_DESIGN_REQUIRED,
    OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED,
    SNAPSHOT_BBO_CAPABILITY,
    VENDOR_API_METHOD,
    assess_snapshot_bbo,
    provider_time_ns_from_row,
    raw_row_sha256,
)

_ET = ZoneInfo("America/New_York")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRANSPORT_PATH = _REPO_ROOT / "tools" / "moomoo" / "opend_quote_transport.py"


@dataclass(frozen=True, slots=True)
class VendorSnapshotFetch:
    reason_code: str | None
    row: Mapping[str, Any] | None


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
    "ITEM7_ADAPTER_VERSION",
    "MOOMOO_OPEND_PROVIDER_ID",
    "OUTCOME_DERIVED_BBO_DESIGN_REQUIRED",
    "OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED",
    "SNAPSHOT_BBO_CAPABILITY",
    "VENDOR_API_METHOD",
    "VendorSnapshotFetch",
    "assess_snapshot_bbo",
    "blocked_diagnostic",
    "fetch_vendor_market_snapshot",
    "is_us_equity_rth",
    "opend_reachable",
    "provider_time_ns_from_row",
    "raw_row_sha256",
    "run_live_probe",
]
