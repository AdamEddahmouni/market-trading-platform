"""HTTP handlers for causal intelligence evaluation (cross-lane + hysteresis)."""

from __future__ import annotations

from typing import Any

from .causal_intelligence import build_causal_intelligence, finalize_causal_intelligence_for_row


def evaluate_causal_request(body: dict[str, Any]) -> dict[str, Any]:
    """Evaluate causal intelligence from an explicit research payload."""
    row = body.get("row")
    if not isinstance(row, dict):
        raise ValueError("row object is required")
    cross_lane = body.get("cross_lane")
    fuel_history = body.get("fuel_history")
    horizon_model = body.get("horizon_model")
    previous_state = body.get("previous_state")
    state_since = body.get("state_since")
    if previous_state or state_since:
        payload, _changed = finalize_causal_intelligence_for_row(
            row,
            previous_state=str(previous_state) if previous_state else None,
            state_since=str(state_since) if state_since else None,
            cross_lane=cross_lane if isinstance(cross_lane, dict) else None,
            fuel_history=fuel_history if isinstance(fuel_history, dict) else None,
            horizon_model=horizon_model if isinstance(horizon_model, dict) else None,
        )
    else:
        payload = build_causal_intelligence(
            row,
            cross_lane=cross_lane if isinstance(cross_lane, dict) else None,
            fuel_history=fuel_history if isinstance(fuel_history, dict) else None,
            horizon_model=horizon_model if isinstance(horizon_model, dict) else None,
            apply_state_hysteresis=False,
        )
    return {"causal_intelligence": payload}


def attach_cross_lane(symbol: str, body: dict[str, Any]) -> dict[str, Any]:
    from . import session_state

    snapshot = body.get("cross_lane")
    if snapshot is not None and not isinstance(snapshot, dict):
        raise ValueError("cross_lane must be an object")
    session = session_state.get_session()
    ok = session.set_cross_lane_snapshot(symbol, snapshot)
    return {"symbol": symbol.strip().upper(), "attached": ok}
