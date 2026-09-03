"""Point-in-time admissibility join for intraday chain snapshots.

A snapshot is usable at decision time ``T`` iff ``available_time_ns <= T`` AND
``event_time_ns <= T``. Either timestamp in the future of ``T`` is lookahead
and is rejected with an explicit reason (research plan §2.4 "never allow newer
Options observation into earlier decision").
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import IntradayChainSnapshotRecord

PIT_REJECTED_FUTURE_AVAILABLE_TIME = "PIT_REJECTED_FUTURE_AVAILABLE_TIME"
PIT_REJECTED_FUTURE_EVENT_TIME = "PIT_REJECTED_FUTURE_EVENT_TIME"
PIT_REJECTED_MISSING_TIMESTAMPS = "PIT_REJECTED_MISSING_TIMESTAMPS"


@dataclass(frozen=True, slots=True)
class PitDecision:
    """Outcome of the PIT admissibility check; ``usable`` fails closed."""

    usable: bool
    reason: str | None = None


def _require_decision_time(decision_time_ns: int) -> None:
    if not isinstance(decision_time_ns, int) or isinstance(decision_time_ns, bool):
        raise TypeError("decision_time_ns must be an integer epoch nanosecond value")
    if decision_time_ns < 0:
        raise ValueError("decision_time_ns must be non-negative")


def evaluate_pit(
    *,
    event_time_ns: int | None,
    available_time_ns: int | None,
    decision_time_ns: int,
) -> PitDecision:
    """Fail-closed PIT join over raw timestamps (absent timestamps reject)."""
    _require_decision_time(decision_time_ns)
    if event_time_ns is None or available_time_ns is None:
        return PitDecision(usable=False, reason=PIT_REJECTED_MISSING_TIMESTAMPS)
    if not isinstance(event_time_ns, int) or isinstance(event_time_ns, bool):
        raise TypeError("event_time_ns must be an integer epoch nanosecond value")
    if not isinstance(available_time_ns, int) or isinstance(available_time_ns, bool):
        raise TypeError("available_time_ns must be an integer epoch nanosecond value")
    if available_time_ns > decision_time_ns:
        return PitDecision(usable=False, reason=PIT_REJECTED_FUTURE_AVAILABLE_TIME)
    if event_time_ns > decision_time_ns:
        return PitDecision(usable=False, reason=PIT_REJECTED_FUTURE_EVENT_TIME)
    return PitDecision(usable=True)


def snapshot_usable_at(
    record: IntradayChainSnapshotRecord,
    *,
    decision_time_ns: int,
) -> PitDecision:
    """PIT admissibility of one snapshot at decision time ``decision_time_ns``."""
    return evaluate_pit(
        event_time_ns=record.event_time_ns,
        available_time_ns=record.available_time_ns,
        decision_time_ns=decision_time_ns,
    )


def admissible_snapshots_at(
    records: list[IntradayChainSnapshotRecord] | tuple[IntradayChainSnapshotRecord, ...],
    *,
    decision_time_ns: int,
) -> tuple[IntradayChainSnapshotRecord, ...]:
    """Only snapshots whose bitemporal pair is closed at ``decision_time_ns``."""
    usable: list[IntradayChainSnapshotRecord] = []
    for record in records:
        decision = snapshot_usable_at(record, decision_time_ns=decision_time_ns)
        if decision.usable:
            usable.append(record)
    return tuple(usable)


__all__ = [
    "PIT_REJECTED_FUTURE_AVAILABLE_TIME",
    "PIT_REJECTED_FUTURE_EVENT_TIME",
    "PIT_REJECTED_MISSING_TIMESTAMPS",
    "PitDecision",
    "admissible_snapshots_at",
    "evaluate_pit",
    "snapshot_usable_at",
]
