"""Shared utilities for settings, state I/O, and process guards.

Purpose
-------
Defaults + deep merge for ``settings.json``, atomic JSON writes under ``state/``,
and optional single-instance PID lock for the standalone scheduler.

Features / API role
-------------------
``load_settings``, ``merge_nested_dicts``, ``load_json`` / ``save_json``,
``acquire_pid_lock`` / ``release_pid_lock``.

How ``news_momentum_agent`` consumes it
---------------------------------------
``options_client`` imports ``load_settings`` and ``merge_nested_dicts`` to overlay
agent ``offline_mode`` / ``chain_provider`` onto engine defaults before ``run_batch``.

Options-specific vs reusable
----------------------------
Mostly reusable infrastructure; default dict embeds options scoring weights and
chain provider blocks specific to this engine.
"""

from __future__ import annotations

import atexit
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
STATE_DIR = PROJECT_ROOT / "state"
PID_PATH = STATE_DIR / "agent.pid"


def merge_nested_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge nested dictionaries."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_nested_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def load_settings() -> Dict[str, Any]:
    """Load settings with defaults and deep merge user overrides."""
    defaults: Dict[str, Any] = {
        "chain": {
            "provider": "yfinance",
            "expiries_to_scan": 2,
            "max_dte": 45,
            "min_open_interest": 50,
            "min_contract_volume": 10,
            "request_timeout_seconds": 10,
            "finviz": {
                "base_url": "https://elite.finviz.com/export/options",
                "auth_token_env": "FINVIZ_AUTH_TOKEN",
                "max_retries": 3,
                "retry_backoff_seconds": 1.0,
                "min_request_interval_seconds": 0.4,
            },
            "replay": {
                "snapshot_dir": "state/raw_snapshots",
                "min_contracts": 20,
            },
        },
        "features": {
            "lookback_days_for_averages": 20,
            "atm_strike_band_pct": 0.03,
            "iv_rank_lookback_days": 60,
            "skew_delta_low": 0.15,
            "skew_delta_high": 0.35,
        },
        "scoring": {
            "weights": {
                "call_volume_share": 25,
                "net_delta_oi": 25,
                "iv_skew": 22,
                "put_call_oi_ratio": 16,
                "put_call_volume_ratio": 12,
            },
            "bullish_threshold": 60,
            "bearish_threshold": 40,
            "min_data_quality_score": 0.6,
            "min_directional_signals": 2,
        },
        "runtime": {"single_instance_required": True, "state_write_atomic": True, "stale_buffer_seconds": 120},
        "universe": {
            "source": "finviz_screener",
            "screener_export_url": "https://elite.finviz.com/export.ashx?v=111&s=ta_mostactive&f=ind_stocksonly,sh_opt_option,sh_price_o10,sh_avgvol_o1000",
            "max_tickers": 15,
            "fallback_tickers": ["AAPL", "TSLA", "NVDA"],
        },
        "scheduler": {
            "interval_seconds": 300,
            "market_hours_only": True,
            "timezone": "America/New_York",
            "market_holidays": [
                "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
                "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
                "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
                "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
            ],
        },
        "trading": {
            "enabled": True,
            "starting_cash": 100000,
            "max_positions": 10,
            "allow_short": True,
            "exit_on_neutral": True,
        },
        "logging": {"max_reasoning_chars": 300, "save_raw_snapshot": True},
    }
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return merge_nested_dicts(defaults, payload)
    except Exception:
        pass
    return defaults


def load_json(path: Path, default: Any) -> Any:
    """Load JSON data from disk safely."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any, atomic: bool = True) -> None:
    """Save JSON with optional atomic temp+replace behavior."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if atomic:
        temp_path = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_process_running(pid: int) -> bool:
    """Check process existence."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def release_pid_lock() -> None:
    """Release process lock if owned by current process."""
    lock = load_json(PID_PATH, {})
    lock_pid = int(lock.get("pid", -1)) if isinstance(lock, dict) else -1
    if lock_pid == os.getpid():
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def acquire_pid_lock(single_instance_required: bool) -> bool:
    """Acquire process lock for single-instance mode."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_json(PID_PATH, {})
    existing_pid = int(existing.get("pid", -1)) if isinstance(existing, dict) else -1
    if existing_pid > 0 and existing_pid != os.getpid() and is_process_running(existing_pid):
        if single_instance_required:
            print(f"[options_engine] Another instance is active (pid={existing_pid}). Exiting.")
            return False
    save_json(
        PID_PATH,
        {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()},
        atomic=True,
    )
    atexit.register(release_pid_lock)
    return True

