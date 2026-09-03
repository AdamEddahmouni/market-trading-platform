"""Deterministic point-in-time event selection (BUILD 02)."""

from __future__ import annotations

from ..contracts.event import EventV1
from .policy import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy
from .validation import event_sort_key, inspect_event_temporal_integrity


def eligible_as_of(
    events: list[EventV1] | tuple[EventV1, ...],
    decision_time_ns: int,
    *,
    policy: TemporalIntegrityPolicy | None = None,
) -> tuple[EventV1, ...]:
    """Return events knowable at decision time (availability gate only)."""
    _ = policy
    eligible = [event for event in events if event.available_time_ns <= decision_time_ns]
    return tuple(sorted(eligible, key=event_sort_key))


def usable_as_of(
    events: list[EventV1] | tuple[EventV1, ...],
    decision_time_ns: int,
    *,
    policy: TemporalIntegrityPolicy | None = None,
) -> tuple[EventV1, ...]:
    """Return events eligible and usable under freshness/validity policy."""
    active = policy or DEFAULT_TEMPORAL_POLICY
    usable: list[EventV1] = []
    for event in events:
        report = inspect_event_temporal_integrity(event, decision_time_ns=decision_time_ns, policy=active)
        if report.usable:
            usable.append(event)
    return tuple(sorted(usable, key=event_sort_key))


def select_events_as_of(
    events: list[EventV1] | tuple[EventV1, ...],
    decision_time_ns: int,
    *,
    policy: TemporalIntegrityPolicy | None = None,
    require_usable: bool = False,
) -> tuple[EventV1, ...]:
    """Deterministic point-in-time selection with stable ordering."""
    if require_usable:
        return usable_as_of(events, decision_time_ns, policy=policy)
    return eligible_as_of(events, decision_time_ns, policy=policy)


__all__ = [
    "eligible_as_of",
    "select_events_as_of",
    "usable_as_of",
]
