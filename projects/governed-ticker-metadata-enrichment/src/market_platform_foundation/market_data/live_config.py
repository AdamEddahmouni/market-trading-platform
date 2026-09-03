"""Fail-closed configuration for live observational market data (P2)."""

from __future__ import annotations

import os
from pathlib import Path


def live_observational_enabled() -> bool:
    return os.environ.get("IMP_LIVE_OBSERVATIONAL") == "1"


def moomoo_live_enabled() -> bool:
    return os.environ.get("IMP_MOOMOO_LIVE") == "1"


def shadow_recording_enabled() -> bool:
    """Run-1 prospective shadow recording opt-in gate (IMP_SHADOW_RECORDING)."""
    return os.environ.get("IMP_SHADOW_RECORDING", "").strip().lower() in {"1", "true", "yes"}


def live_internal_simulation_enabled() -> bool:
    from ..operating_modes import paper_execution_env_enabled

    return (
        os.environ.get("IMP_LIVE_INTERNAL_SIMULATION") == "1"
        and live_observational_enabled()
        and paper_execution_env_enabled()
    )


def moomoo_host() -> str:
    return os.environ.get("IMP_MOOMOO_HOST", "127.0.0.1")


def moomoo_port() -> int:
    return int(os.environ.get("IMP_MOOMOO_PORT", "11111"))


def subscription_quota_override() -> int | None:
    """Explicit local/test override. None means use the provider-reported quota."""

    raw = os.environ.get("IMP_MOOMOO_SUBSCRIPTION_QUOTA")
    if raw is None or raw.strip() == "":
        return None
    return int(raw)


def subscription_quota() -> int:
    override = subscription_quota_override()
    if override is not None:
        return override
    return 100


def quote_stale_threshold_ms() -> int:
    return int(os.environ.get("IMP_LIVE_QUOTE_STALE_MS", "5000"))


def clock_drift_threshold_ms() -> int:
    """Broad malformed/clock corruption alarm — not execution freshness."""

    return int(os.environ.get("IMP_LIVE_CLOCK_DRIFT_MS", "60000"))


def execution_freshness_threshold_ms() -> int:
    """Execution-sensitive admission threshold (measured policy default)."""

    return int(os.environ.get("IMP_LIVE_EXECUTION_FRESHNESS_MS", "5000"))


def live_execution_wait_ms() -> int:
    """Bounded wait for a post-intent EXECUTION_ADMITTED L1 snapshot on submit."""

    return int(os.environ.get("IMP_LIVE_EXECUTION_WAIT_MS", "8000"))


def ingest_queue_max_size() -> int:
    return int(os.environ.get("IMP_LIVE_INGEST_QUEUE_MAX", "10000"))


def probe_report_path() -> Path:
    raw = os.environ.get("IMP_MOOMOO_PROBE_REPORT")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[3] / "evidence" / "market_data" / "moomoo" / "capability-report.json"


def probe_staleness_seconds() -> int:
    return int(os.environ.get("IMP_MOOMOO_PROBE_STALENESS_SEC", "86400"))


def reconnect_backoff_seconds(attempt: int = 0) -> float:
    schedule = os.environ.get("IMP_LIVE_RECONNECT_BACKOFF_SEC", "1,2,5,10,30")
    values = [float(item.strip()) for item in schedule.split(",") if item.strip()]
    if not values:
        values = [1.0, 2.0, 5.0, 10.0, 30.0]
    idx = max(0, min(attempt, len(values) - 1))
    return values[idx]


def default_capture_root() -> Path:
    root = os.environ.get("IMP_LIVE_CAPTURE_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[3] / "evidence" / "live-captures"


def fixture_feed_path() -> Path | None:
    raw = os.environ.get("IMP_LIVE_FIXTURE_FEED")
    if not raw:
        return None
    return Path(raw)
