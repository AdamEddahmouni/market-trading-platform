"""Anti-churn guards for signal-flip option exits and opposite-side re-entry.

Pipeline role
-------------
When ``execution.exit_on_signal_flip`` is enabled, an opposite BUY/SELL can
close an open call/put. These guards prevent whipsaw:
  - ``evaluate_flip_close`` — min hold time + confidence hysteresis before closing.
  - ``evaluate_opposite_reentry`` — cooldown before opening the opposite side.
  - ``record_flip_close`` / ``load_flip_cooldown`` — persist flip timing state.

State files
-----------
  - ``state/flip_cooldown.json`` — per-ticker last flip-close metadata.
  - ``state/flip_audit.json`` — append-only flip decision audit (cap 500 rows).

Merge notes for stocks/futures
------------------------------
  - **Reusable concept:** min-hold + hysteresis + re-entry cooldown for any
    strategy that flips long/short on signal reversal.
  - **Options-specific:** side semantics (call vs put); map to long/short equity
    or futures direction in a fork.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
FLIP_COOLDOWN_PATH = STATE_DIR / "flip_cooldown.json"
FLIP_AUDIT_PATH = STATE_DIR / "flip_audit.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, payload: Any) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def load_flip_cooldown() -> Dict[str, Any]:
    """Load flip re-entry cooldown state from ``state/flip_cooldown.json``."""
    data = _load(FLIP_COOLDOWN_PATH, {"entries": {}})
    if not isinstance(data, dict):
        return {"entries": {}}
    data.setdefault("entries", {})
    return data


def record_flip_close(ticker: str, closed_side: str, settings: Optional[Dict[str, Any]] = None) -> None:
    """Record that a signal-flip close occurred so opposite re-entry can be cooldown-gated."""
    data = load_flip_cooldown()
    key = ticker.upper().strip()
    data["entries"][key] = {
        "closed_at": _now_iso(),
        "closed_side": str(closed_side).lower().strip(),
        "opposite_side": "put" if str(closed_side).lower() == "call" else "call",
    }
    data["updated_at"] = _now_iso()
    _save(FLIP_COOLDOWN_PATH, data)


def append_flip_audit(entry: Dict[str, Any]) -> None:
    """Append one flip guard decision to ``state/flip_audit.json`` (ring buffer, max 500)."""
    rows = _load(FLIP_AUDIT_PATH, [])
    if not isinstance(rows, list):
        rows = []
    rows.append({**entry, "timestamp": _now_iso()})
    if len(rows) > 500:
        rows = rows[-500:]
    _save(FLIP_AUDIT_PATH, rows)


def _age_minutes(opened_at: str, now: Optional[datetime] = None) -> float:
    try:
        opened = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        return max(0.0, (current - opened).total_seconds() / 60.0)
    except Exception:
        return 9999.0


def evaluate_flip_close(
    *,
    ticker: str,
    position: Dict[str, Any],
    settings: Dict[str, Any],
    signal_confidence: float | None = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Decide whether an opposite signal may close via signal_flip.

    Returns (allowed, reason_code, details).
    """
    exec_cfg = settings.get("execution") or {}
    if not bool(exec_cfg.get("exit_on_signal_flip", False)):
        return False, "flip_disabled", {"flip_decision": "suppressed"}

    min_hold = float(exec_cfg.get("min_hold_minutes_before_flip", 8))
    flip_min_conf = float(exec_cfg.get("flip_min_confidence", 70))
    opened_at = str(position.get("opened_at") or "")
    age = _age_minutes(opened_at, now)
    conf = float(signal_confidence) if signal_confidence is not None else 0.0

    details = {
        "flip_decision": "suppressed",
        "age_minutes": round(age, 2),
        "min_hold_minutes": min_hold,
        "signal_confidence": conf,
        "flip_min_confidence": flip_min_conf,
    }

    if age < min_hold:
        return False, "min_hold", details
    if conf < flip_min_conf:
        return False, "hysteresis", details

    details["flip_decision"] = "accepted"
    return True, "accepted", details


def evaluate_opposite_reentry(
    *,
    ticker: str,
    option_side: str,
    settings: Dict[str, Any],
    signal_confidence: float | None = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Block re-entering opposite side too soon after a flip-close."""
    exec_cfg = settings.get("execution") or {}
    cooldown_min = float(exec_cfg.get("flip_reentry_cooldown_minutes", 30))
    strong_conf = float(exec_cfg.get("flip_strong_reentry_confidence", 80))
    conf = float(signal_confidence) if signal_confidence is not None else 0.0

    data = load_flip_cooldown()
    entry = (data.get("entries") or {}).get(ticker.upper().strip())
    if not isinstance(entry, dict):
        return True, "no_prior_flip", {"flip_reentry": "allowed"}

    closed_at = str(entry.get("closed_at") or "")
    age = _age_minutes(closed_at, now)
    expected_opposite = str(entry.get("opposite_side") or "").lower()
    side = str(option_side).lower().strip()
    details = {
        "flip_reentry": "blocked",
        "minutes_since_flip": round(age, 2),
        "cooldown_minutes": cooldown_min,
        "signal_confidence": conf,
        "strong_reentry_confidence": strong_conf,
    }
    if expected_opposite and side != expected_opposite:
        # Same-direction re-entry after flip-close of the other side is fine.
        return True, "same_direction", {**details, "flip_reentry": "allowed"}
    if age >= cooldown_min:
        return True, "cooldown_elapsed", {**details, "flip_reentry": "allowed"}
    if conf >= strong_conf:
        return True, "strong_signal_override", {**details, "flip_reentry": "allowed"}
    return False, "cooldown", details
