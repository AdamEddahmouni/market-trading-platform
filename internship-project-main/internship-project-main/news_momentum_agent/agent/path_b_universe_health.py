"""Track Path B Finviz expiry-screener health across scheduler cycles.

Pipeline role
-------------
Path B scans Finviz for unusual options activity / near-expiry names.
``update_universe_health`` increments ``consecutive_zero_finviz`` when the raw
Finviz row count is zero and sets ``_should_notify`` when the streak exceeds
``expiry_screener.zero_finviz_alert_cycles``.

State file: ``state/path_b_universe_health.json``.

Merge notes: Path B / options-expiry specific screener health; the consecutive-zero
alert pattern mirrors ``path_a_pipeline_health`` and is reusable for any
external universe feed (e.g. futures watchlist provider).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
HEALTH_PATH = STATE_DIR / "path_b_universe_health.json"


def load_health() -> Dict[str, Any]:
    """Load Path B universe health from ``state/path_b_universe_health.json``."""
    try:
        if not HEALTH_PATH.exists():
            return {"consecutive_zero_finviz": 0, "alerted": False}
        data = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"consecutive_zero_finviz": 0, "alerted": False}
    except Exception:
        return {"consecutive_zero_finviz": 0, "alerted": False}


def save_health(data: Dict[str, Any]) -> None:
    """Persist Path B universe health counters and last scan stats."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = HEALTH_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(HEALTH_PATH)


def update_universe_health(
    stats: Dict[str, Any],
    *,
    kept_0dte: int = 0,
    dropped_non_0dte: int = 0,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update consecutive-zero counter. Alert when Finviz raw is 0 for N cycles.
    """
    threshold = int(((settings or {}).get("expiry_screener") or {}).get("zero_finviz_alert_cycles", 3))
    data = load_health()
    finviz_raw = int(stats.get("finviz_raw") or 0)
    if finviz_raw <= 0:
        data["consecutive_zero_finviz"] = int(data.get("consecutive_zero_finviz") or 0) + 1
    else:
        data["consecutive_zero_finviz"] = 0
        data["alerted"] = False

    data.update(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_stats": {
                **stats,
                "kept_0dte": kept_0dte,
                "dropped_non_0dte": dropped_non_0dte,
            },
            "alert_threshold": threshold,
            "alert": int(data.get("consecutive_zero_finviz") or 0) >= threshold,
        }
    )

    should_notify = bool(data.get("alert")) and not bool(data.get("alerted"))
    if should_notify:
        data["alerted"] = True
        data["last_alert_at"] = data["updated_at"]
    save_health(data)
    data["_should_notify"] = should_notify
    return data
