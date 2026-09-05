"""Causal state hysteresis — reduce state flapping on ephemeral evidence."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from .contracts import SqueezeState

_STATE_ORDER: dict[SqueezeState, int] = {
    SqueezeState.BASELINE: 0,
    SqueezeState.VULNERABLE: 1,
    SqueezeState.ARMED: 2,
    SqueezeState.IGNITION_WATCH: 3,
    SqueezeState.LIVE_CONFIRMATION: 4,
    SqueezeState.ACTIVE_SQUEEZE: 5,
    SqueezeState.EXHAUSTION: 6,
    SqueezeState.POST_SQUEEZE: 7,
    SqueezeState.UNEVALUABLE: -1,
}

DEFAULT_COOLDOWN_SECONDS = int(os.environ.get("CAUSAL_STATE_COOLDOWN_SECONDS", "120"))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _order(state: str | None) -> int:
    if not state:
        return -1
    try:
        return _STATE_ORDER[SqueezeState(state)]
    except ValueError:
        return -1


def apply_hysteresis(
    result: dict[str, Any],
    *,
    previous_state: str | None,
    state_since: str | None,
    now: datetime | None = None,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
) -> dict[str, Any]:
    """Hold backward state transitions during cooldown unless contradictions are strong."""
    if not previous_state:
        return result

    proposed = str(result.get("state", ""))
    if not proposed or proposed == previous_state:
        return result

    proposed_order = _order(proposed)
    previous_order = _order(previous_state)
    if proposed_order < 0 or previous_order < 0:
        return result

    # Upgrades apply immediately.
    if proposed_order >= previous_order:
        return result

    since = _parse_iso(state_since)
    now_dt = now or datetime.now(tz=UTC)
    elapsed = (now_dt - since).total_seconds() if since else cooldown_seconds + 1

    contradicting = result.get("contradicting_evidence") or []
    strong_contradiction = any(
        isinstance(item, dict) and item.get("strength") == "HIGH" for item in contradicting
    )

    if elapsed >= cooldown_seconds or strong_contradiction:
        transition = dict(result.get("transition") or {})
        transition["hysteresis_applied"] = False
        transition["downgrade_allowed"] = True
        result = {**result, "transition": transition}
        return result

    held = {**result}
    held["state"] = previous_state
    held["previous_state"] = previous_state
    flags = list(held.get("quality_flags") or [])
    if "HYSTERESIS_HOLD" not in flags:
        flags.append("HYSTERESIS_HOLD")
    held["quality_flags"] = flags
    transition = dict(held.get("transition") or {})
    transition["hysteresis_applied"] = True
    transition["proposed_state"] = proposed
    transition["held_state"] = previous_state
    transition["cooldown_seconds"] = cooldown_seconds
    transition["cooldown_remaining_seconds"] = max(0, int(cooldown_seconds - elapsed))
    held["transition"] = transition
    summary = str(held.get("explanation", {}).get("summary", ""))
    held["explanation"] = {
        **(held.get("explanation") or {}),
        "summary": (
            f"{summary} Hysteresis held state at {previous_state} "
            f"(proposed {proposed}, cooldown {int(max(0, cooldown_seconds - elapsed))}s remaining)."
        ).strip(),
    }
    return held
