"""Idempotency tracker for once-per-day EOD / deadline flatten per position key.

Pipeline role
-------------
``portfolio.manage_option_exits`` uses this to avoid double-closing the same
option position when EOD flatten runs on repeated scheduler ticks. Keys are
position dict keys in ``portfolio.json`` (typically contract symbols).

State file: ``state/eod_flattened.json`` — resets each ET calendar day.

Merge notes: reusable idempotency pattern for any scheduled flatten/roll job;
options-specific only in how keys are chosen (contract vs futures symbol).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
EOD_FLAT_PATH = STATE_DIR / "eod_flattened.json"


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def load_eod_state() -> Dict[str, Any]:
    """Load today's flatten keys from ``state/eod_flattened.json`` (empty if date rolled)."""
    try:
        if not EOD_FLAT_PATH.exists():
            return {"date": _today_et(), "keys": []}
        data = json.loads(EOD_FLAT_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"date": _today_et(), "keys": []}
        if str(data.get("date")) != _today_et():
            return {"date": _today_et(), "keys": []}
        data.setdefault("keys", [])
        return data
    except Exception:
        return {"date": _today_et(), "keys": []}


def save_eod_state(data: Dict[str, Any]) -> None:
    """Persist EOD flatten idempotency state to ``state/eod_flattened.json``."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = EOD_FLAT_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(EOD_FLAT_PATH)


def already_flattened(position_key: str) -> bool:
    """True if this position key was already EOD-flattened today."""
    data = load_eod_state()
    keys = {str(k) for k in (data.get("keys") or [])}
    return str(position_key) in keys


def mark_flattened(position_key: str) -> None:
    """Record that ``position_key`` was flattened today to prevent duplicate closes."""
    data = load_eod_state()
    keys: Set[str] = {str(k) for k in (data.get("keys") or [])}
    keys.add(str(position_key))
    data["keys"] = sorted(keys)
    data["date"] = _today_et()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_eod_state(data)


def flattened_keys_today() -> Set[str]:
    """Return the set of position keys already flattened this ET session."""
    data = load_eod_state()
    return {str(k) for k in (data.get("keys") or [])}
