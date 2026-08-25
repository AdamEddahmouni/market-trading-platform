"""Bounded scheduler observability for BUILD 10."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SchedulerEventKind(StrEnum):
    JOB_ADMITTED = "JOB_ADMITTED"
    JOB_DEDUPLICATED = "JOB_DEDUPLICATED"
    JOB_BLOCKED_RESOURCE = "JOB_BLOCKED_RESOURCE"
    JOB_READY = "JOB_READY"
    BATCH_PLANNED = "BATCH_PLANNED"
    JOB_DISPATCHED = "JOB_DISPATCHED"
    JOB_RUNNING = "JOB_RUNNING"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    JOB_EXPIRED = "JOB_EXPIRED"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_SUPERSEDED = "JOB_SUPERSEDED"
    RESIDENCY_PLAN = "RESIDENCY_PLAN"


@dataclass(frozen=True, slots=True)
class SchedulerEvent:
    kind: SchedulerEventKind
    at_ns: int
    job_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class SchedulerObserver:
    """Append-only bounded trace — telemetry, not canonical intelligence."""

    def __init__(self, *, max_events: int = 4096) -> None:
        self._max_events = max_events
        self._events: list[SchedulerEvent] = []

    def emit(self, event: SchedulerEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

    def events(self) -> tuple[SchedulerEvent, ...]:
        return tuple(self._events)

    def clear(self) -> None:
        self._events.clear()


__all__ = ["SchedulerEvent", "SchedulerEventKind", "SchedulerObserver"]
