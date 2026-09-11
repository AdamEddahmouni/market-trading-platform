"""Forward-test lifecycle transitions."""

from __future__ import annotations

from .types import ForwardTestState

_TRANSITIONS: dict[ForwardTestState, frozenset[ForwardTestState]] = {
    ForwardTestState.DRAFT: frozenset({ForwardTestState.LOCKED, ForwardTestState.CANCELLED, ForwardTestState.INVALID}),
    ForwardTestState.LOCKED: frozenset(
        {
            ForwardTestState.PAPER_SUBMITTED,
            ForwardTestState.OBSERVING,
            ForwardTestState.REJECTED,
            ForwardTestState.CANCELLED,
            ForwardTestState.INVALID,
        }
    ),
    ForwardTestState.PAPER_SUBMITTED: frozenset(
        {ForwardTestState.PAPER_ACTIVE, ForwardTestState.REJECTED, ForwardTestState.OBSERVING}
    ),
    ForwardTestState.PAPER_ACTIVE: frozenset({ForwardTestState.OBSERVING, ForwardTestState.REJECTED}),
    ForwardTestState.OBSERVING: frozenset(
        {ForwardTestState.EVALUABLE, ForwardTestState.INSUFFICIENT_DATA, ForwardTestState.EXPIRED}
    ),
    ForwardTestState.EVALUABLE: frozenset({ForwardTestState.EVALUATED, ForwardTestState.INSUFFICIENT_DATA}),
    ForwardTestState.EVALUATED: frozenset(),
    ForwardTestState.REJECTED: frozenset(),
    ForwardTestState.CANCELLED: frozenset(),
    ForwardTestState.EXPIRED: frozenset(),
    ForwardTestState.INVALID: frozenset(),
    ForwardTestState.INSUFFICIENT_DATA: frozenset({ForwardTestState.EVALUABLE, ForwardTestState.EVALUATED}),
}


class ForwardTestLifecycleError(ValueError):
    """Illegal lifecycle transition."""


def assert_transition(current: ForwardTestState, target: ForwardTestState) -> None:
    allowed = _TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ForwardTestLifecycleError(f"FORWARD_TEST_TRANSITION_INVALID:{current.value}->{target.value}")


def is_terminal(state: ForwardTestState) -> bool:
    return state in {
        ForwardTestState.EVALUATED,
        ForwardTestState.REJECTED,
        ForwardTestState.CANCELLED,
        ForwardTestState.EXPIRED,
        ForwardTestState.INVALID,
    }
