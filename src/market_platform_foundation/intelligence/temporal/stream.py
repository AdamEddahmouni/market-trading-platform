"""Lightweight stream observation for duplicates and ordering (BUILD 02)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from ..contracts.event import EventV1
from .models import (
    DuplicateClassification,
    TemporalViolation,
    TemporalViolationCode,
    TemporalViolationSeverity,
)
from .validation import classify_duplicate_events


@dataclass(frozen=True, slots=True)
class TemporalStreamObservation:
    """Result of observing one event against stream state."""

    duplicate: DuplicateClassification
    violations: tuple[TemporalViolation, ...] = ()


@dataclass
class TemporalStreamState:
    """Bounded in-memory stream guard — deterministic, no wall clock.

    Tracks canonical event ids for duplicate detection and monotonic
    received/available progression for out-of-order diagnostics.
    """

    max_tracked_ids: int = 10_000

    def __post_init__(self) -> None:
        self._seen_ids: OrderedDict[str, EventV1] = OrderedDict()
        self._last_received_time_ns: int | None = None
        self._last_available_time_ns: int | None = None

    def reset(self) -> None:
        self._seen_ids.clear()
        self._last_received_time_ns = None
        self._last_available_time_ns = None

    def observe(self, event: EventV1) -> TemporalStreamObservation:
        violations: list[TemporalViolation] = []
        prior = self._seen_ids.get(event.event_id)
        duplicate_code = classify_duplicate_events(prior, event)
        if duplicate_code == TemporalViolationCode.EXACT_DUPLICATE:
            duplicate = DuplicateClassification.EXACT_DUPLICATE
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.EXACT_DUPLICATE,
                    severity=TemporalViolationSeverity.INFO,
                    message=f"EXACT_DUPLICATE: event {event.event_id} repeats prior semantic content",
                    record_kind="event",
                    record_id=event.event_id,
                    relevant_time_ns=event.available_time_ns,
                )
            )
        elif duplicate_code == TemporalViolationCode.CONFLICTING_DUPLICATE:
            duplicate = DuplicateClassification.CONFLICTING_DUPLICATE
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.CONFLICTING_DUPLICATE,
                    severity=TemporalViolationSeverity.WARNING,
                    message=(
                        f"CONFLICTING_DUPLICATE: event {event.event_id} repeats identity "
                        "with different semantic content"
                    ),
                    record_kind="event",
                    record_id=event.event_id,
                    relevant_time_ns=event.available_time_ns,
                )
            )
        else:
            duplicate = DuplicateClassification.NEW
            self._remember(event)

        if event.received_time_ns is not None and self._last_received_time_ns is not None:
            if event.received_time_ns < self._last_received_time_ns:
                violations.append(
                    TemporalViolation(
                        code=TemporalViolationCode.OUT_OF_ORDER,
                        severity=TemporalViolationSeverity.WARNING,
                        message=(
                            f"OUT_OF_ORDER: event {event.event_id} received_time "
                            f"{event.received_time_ns}ns regresses from prior "
                            f"{self._last_received_time_ns}ns"
                        ),
                        record_kind="event",
                        record_id=event.event_id,
                        relevant_time_ns=event.received_time_ns,
                        delta_ns=self._last_received_time_ns - event.received_time_ns,
                    )
                )

        if self._last_available_time_ns is not None and event.available_time_ns < self._last_available_time_ns:
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.OUT_OF_ORDER,
                    severity=TemporalViolationSeverity.WARNING,
                    message=(
                        f"OUT_OF_ORDER: event {event.event_id} available_time "
                        f"{event.available_time_ns}ns regresses from prior "
                        f"{self._last_available_time_ns}ns"
                    ),
                    record_kind="event",
                    record_id=event.event_id,
                    relevant_time_ns=event.available_time_ns,
                    delta_ns=self._last_available_time_ns - event.available_time_ns,
                )
            )

        if event.received_time_ns is not None:
            if self._last_received_time_ns is None or event.received_time_ns >= self._last_received_time_ns:
                self._last_received_time_ns = event.received_time_ns
        if self._last_available_time_ns is None or event.available_time_ns >= self._last_available_time_ns:
            self._last_available_time_ns = event.available_time_ns

        return TemporalStreamObservation(duplicate=duplicate, violations=tuple(violations))

    def _remember(self, event: EventV1) -> None:
        self._seen_ids[event.event_id] = event
        self._seen_ids.move_to_end(event.event_id)
        while len(self._seen_ids) > self.max_tracked_ids:
            self._seen_ids.popitem(last=False)


__all__ = ["TemporalStreamObservation", "TemporalStreamState"]
