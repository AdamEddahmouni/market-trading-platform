"""0DTE specialization prerequisites (O11) — fixture-proven infrastructure only.

Phase C intraday chain snapshots are NOT admitted; every entry point in this
package fails closed until admission completes. No analytics, no live capture,
no predictive claims. See docs/superpowers/specs/2026-08-22-options-o11-0dte-prerequisites-design.md.
"""

from __future__ import annotations

from .admission import (
    DEFAULT_ADMISSION_MANIFEST,
    PHASE_C_ADMISSION_STATUS_PENDING,
    PHASE_C_DATA_NOT_ADMITTED_REASON,
    PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT,
    evaluate_phase_c_admission,
    load_phase_c_admission_manifest,
    run_o11_zerodte_prerequisite_harness,
)
from .contracts import (
    ET_TIMEZONE_NAME,
    SESSION_CLOSE_ET_HOUR,
    SESSION_CLOSE_ET_MINUTE,
    IntradayChainSnapshotRecord,
    expiration_session_close_ns,
    et_calendar_date,
    is_zero_dte_snapshot,
    snapshot_dte_hours,
    snapshot_from_dict,
    snapshot_to_dict,
)
from .pit import (
    PIT_REJECTED_FUTURE_AVAILABLE_TIME,
    PIT_REJECTED_FUTURE_EVENT_TIME,
    PIT_REJECTED_MISSING_TIMESTAMPS,
    PitDecision,
    admissible_snapshots_at,
    snapshot_usable_at,
)
from .quality import (
    DUPLICATE_SNAPSHOT_KEY_REASON,
    LiquidityPolicy,
    StalenessPolicy,
    ZeroDTEQualityFlag,
    detect_duplicate_snapshots,
    evaluate_snapshot_quality,
    expiration_boundary_flags,
    liquidity_flags,
    staleness_flags,
)

__all__ = [
    "DEFAULT_ADMISSION_MANIFEST",
    "DUPLICATE_SNAPSHOT_KEY_REASON",
    "ET_TIMEZONE_NAME",
    "SESSION_CLOSE_ET_HOUR",
    "SESSION_CLOSE_ET_MINUTE",
    "PHASE_C_ADMISSION_STATUS_PENDING",
    "PHASE_C_DATA_NOT_ADMITTED_REASON",
    "PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT",
    "PIT_REJECTED_FUTURE_AVAILABLE_TIME",
    "PIT_REJECTED_FUTURE_EVENT_TIME",
    "PIT_REJECTED_MISSING_TIMESTAMPS",
    "IntradayChainSnapshotRecord",
    "LiquidityPolicy",
    "PitDecision",
    "StalenessPolicy",
    "ZeroDTEQualityFlag",
    "admissible_snapshots_at",
    "detect_duplicate_snapshots",
    "et_calendar_date",
    "evaluate_phase_c_admission",
    "evaluate_snapshot_quality",
    "expiration_boundary_flags",
    "expiration_session_close_ns",
    "is_zero_dte_snapshot",
    "liquidity_flags",
    "load_phase_c_admission_manifest",
    "run_o11_zerodte_prerequisite_harness",
    "snapshot_dte_hours",
    "snapshot_from_dict",
    "snapshot_to_dict",
    "snapshot_usable_at",
    "staleness_flags",
]
