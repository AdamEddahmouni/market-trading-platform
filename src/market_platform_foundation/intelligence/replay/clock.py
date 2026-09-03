"""Clock abstractions for live and replay runtimes (BUILD 07)."""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from .errors import ReplayClockError


@runtime_checkable
class Clock(Protocol):
    """Nanosecond epoch clock — intelligence code must not read wall time directly."""

    def now_ns(self) -> int: ...


class LiveClock:
    """Wall-clock boundary for live operation."""

    def now_ns(self) -> int:
        return time.time_ns()


class ReplayClock:
    """Deterministic virtual clock for replay — no wall-clock reads or sleeps."""

    def __init__(self, initial_time_ns: int) -> None:
        if initial_time_ns < 0:
            raise ReplayClockError(
                "REPLAY_CLOCK_NEGATIVE_INITIAL",
                "initial_time_ns must be non-negative",
                details={"initial_time_ns": initial_time_ns},
            )
        self._now_ns = initial_time_ns

    def now_ns(self) -> int:
        return self._now_ns

    def advance_to(self, target_time_ns: int) -> None:
        if target_time_ns < self._now_ns:
            raise ReplayClockError(
                "REPLAY_CLOCK_BACKWARD",
                "ReplayClock cannot move backward",
                details={"current_ns": self._now_ns, "target_ns": target_time_ns},
            )
        self._now_ns = target_time_ns

    def advance_by(self, delta_ns: int) -> None:
        if delta_ns < 0:
            raise ReplayClockError(
                "REPLAY_CLOCK_NEGATIVE_DELTA",
                "ReplayClock cannot advance by negative delta",
                details={"delta_ns": delta_ns},
            )
        self._now_ns += delta_ns


__all__ = ["Clock", "LiveClock", "ReplayClock"]
