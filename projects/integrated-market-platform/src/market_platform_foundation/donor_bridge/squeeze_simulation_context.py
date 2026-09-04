"""Resolve squeeze causal context at a prediction cutoff for execution simulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .transition_stream import DEFAULT_TRANSITION_STREAM_FIXTURE, replay_transition_stream


def resolve_squeeze_context_at_cutoff(
    cutoff_ns: int,
    *,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    """Return latest PIT-valid squeeze state visible at cutoff_ns."""
    transitions = replay_transition_stream(fixture_path, as_of_time_ns=cutoff_ns)
    if not transitions:
        return {"available": False, "reason": "NO_TRANSITIONS_AT_CUTOFF"}

    latest = transitions[0]
    state = latest.get("to_state")
    if not state:
        return {"available": False, "reason": "SQUEEZE_STATE_MISSING"}

    return {
        "available": True,
        "squeeze_state": str(state),
        "exhaustion_risk": latest.get("exhaustion_risk"),
        "remaining_fuel": latest.get("remaining_fuel"),
        "cvd_slope": latest.get("cvd_slope"),
        "reflexivity_strength": latest.get("reflexivity_strength"),
        "changed_at": latest.get("changed_at"),
        "provenance_ref": "squeeze:transition_stream",
    }


__all__ = ["DEFAULT_TRANSITION_STREAM_FIXTURE", "resolve_squeeze_context_at_cutoff"]
