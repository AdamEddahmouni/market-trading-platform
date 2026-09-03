"""Pilot governance state machine (BUILD 33)."""

from __future__ import annotations

from .types import PilotGovernanceState

_VALID_TRANSITIONS: dict[PilotGovernanceState, frozenset[PilotGovernanceState]] = {
    PilotGovernanceState.PILOT_PREPARED: frozenset(
        {PilotGovernanceState.PILOT_READY, PilotGovernanceState.PILOT_INVALID}
    ),
    PilotGovernanceState.PILOT_READY: frozenset(
        {
            PilotGovernanceState.PILOT_ACTIVE,
            PilotGovernanceState.PILOT_HALTED,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_ACTIVE: frozenset(
        {
            PilotGovernanceState.PILOT_DEGRADED,
            PilotGovernanceState.PILOT_PAUSED,
            PilotGovernanceState.PILOT_HALTED,
            PilotGovernanceState.PILOT_RECONCILING,
            PilotGovernanceState.PILOT_COMPLETE,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_DEGRADED: frozenset(
        {
            PilotGovernanceState.PILOT_ACTIVE,
            PilotGovernanceState.PILOT_PAUSED,
            PilotGovernanceState.PILOT_HALTED,
            PilotGovernanceState.PILOT_RECONCILING,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_PAUSED: frozenset(
        {
            PilotGovernanceState.PILOT_ACTIVE,
            PilotGovernanceState.PILOT_DEGRADED,
            PilotGovernanceState.PILOT_HALTED,
            PilotGovernanceState.PILOT_RECONCILING,
            PilotGovernanceState.PILOT_COMPLETE,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_HALTED: frozenset(
        {
            PilotGovernanceState.PILOT_RECONCILING,
            PilotGovernanceState.PILOT_COMPLETE,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_RECONCILING: frozenset(
        {
            PilotGovernanceState.PILOT_PAUSED,
            PilotGovernanceState.PILOT_HALTED,
            PilotGovernanceState.PILOT_COMPLETE,
            PilotGovernanceState.PILOT_INVALID,
        }
    ),
    PilotGovernanceState.PILOT_COMPLETE: frozenset(),
    PilotGovernanceState.PILOT_INVALID: frozenset(),
}


def can_transition_pilot_state(
    current: PilotGovernanceState | str,
    target: PilotGovernanceState | str,
) -> bool:
    cur = PilotGovernanceState(current) if isinstance(current, str) else current
    tgt = PilotGovernanceState(target) if isinstance(target, str) else target
    return tgt in _VALID_TRANSITIONS.get(cur, frozenset())


def transition_pilot_state(
    current: PilotGovernanceState | str,
    target: PilotGovernanceState | str,
) -> PilotGovernanceState:
    cur = PilotGovernanceState(current) if isinstance(current, str) else current
    tgt = PilotGovernanceState(target) if isinstance(target, str) else target
    if not can_transition_pilot_state(cur, tgt):
        raise ValueError(f"Invalid pilot transition {cur.value} -> {tgt.value}")
    return tgt


def pilot_ready_implies_trading_authority(state: PilotGovernanceState | str) -> bool:
    """PILOT_READY does NOT authorize live orders."""
    return False


def pilot_state_allows_observation(state: PilotGovernanceState | str) -> bool:
    s = PilotGovernanceState(state) if isinstance(state, str) else state
    return s in {
        PilotGovernanceState.PILOT_ACTIVE,
        PilotGovernanceState.PILOT_DEGRADED,
        PilotGovernanceState.PILOT_PAUSED,
    }
