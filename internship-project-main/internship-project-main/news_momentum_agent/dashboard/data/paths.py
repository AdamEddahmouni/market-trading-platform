"""Filesystem paths for dashboard state reads."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state"
LOGS_DIR = PROJECT_ROOT / "logs"
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
DEMO_LOCK_PATH = STATE_DIR / "demo.lock"
PID_PATH = STATE_DIR / "agent.pid"
WATCHLIST_PATH = STATE_DIR / "watchlist.json"
HIGH_ALERT_PATH = STATE_DIR / "high_alert.json"
TRADE_LOG_PATH = STATE_DIR / "trade_log.json"
HEALTH_PATH = STATE_DIR / "health.json"
ODTE_WATCHLIST_PATH = STATE_DIR / "odte_watchlist.json"
QUADRANT_PATH = STATE_DIR / "quadrant_candidates.json"
PENDING_REVIEWS_PATH = STATE_DIR / "pending_reviews.json"
PORTFOLIO_PATH = STATE_DIR / "portfolio.json"
EXECUTIONS_PATH = STATE_DIR / "executions.json"
PATH_B_HEALTH_PATH = STATE_DIR / "path_b_universe_health.json"
PATH_A_HEALTH_PATH = STATE_DIR / "path_a_pipeline_health.json"
QUOTE_SANITY_PATH = STATE_DIR / "quote_sanity.json"
FLIP_COOLDOWN_PATH = STATE_DIR / "flip_cooldown.json"
FLIP_AUDIT_PATH = STATE_DIR / "flip_audit.json"
LEARNING_DIR = STATE_DIR / "learning"
MINER_RESULT_PATH = LEARNING_DIR / "spy_qqq_miner_result.json"
PROPOSALS_PATH = LEARNING_DIR / "proposals" / "latest_proposal.json"
AGENT_LOG_PATH = LOGS_DIR / "overnight_agent.log"


def session_date_et(now: Optional[datetime] = None) -> str:
    """Return YYYY-MM-DD in America/New_York when possible."""
    try:
        from zoneinfo import ZoneInfo

        current = now or datetime.now(ZoneInfo("America/New_York"))
        if current.tzinfo is None:
            current = current.replace(tzinfo=ZoneInfo("America/New_York"))
        return current.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (now or datetime.now(timezone.utc)).date().isoformat()


def eod_summary_path(day: Optional[str] = None) -> Path:
    return STATE_DIR / f"eod_summary_{day or session_date_et()}.json"


def near_miss_eod_path(day: Optional[str] = None) -> Path:
    return STATE_DIR / f"near_miss_eod_{day or session_date_et()}.json"


def near_miss_tracker_path(day: Optional[str] = None) -> Path:
    return STATE_DIR / f"near_miss_tracker_{day or session_date_et()}.json"


def latest_eod_summary_path() -> Optional[Path]:
    """Newest eod_summary_*.json by filename date, else None."""
    files = sorted(STATE_DIR.glob("eod_summary_20*.json"), reverse=True)
    return files[0] if files else None
