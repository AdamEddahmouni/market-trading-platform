"""RT-01 clock helpers — separate wall, monotonic, and provider semantics."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..clock import monotonic_wall_ns


@dataclass(frozen=True, slots=True)
class SpanClocks:
    start_wall_time_ns: int
    end_wall_time_ns: int
    start_monotonic_ns: int
    end_monotonic_ns: int

    @property
    def duration_ns(self) -> int:
        return self.end_monotonic_ns - self.start_monotonic_ns


def monotonic_process_ns() -> int:
    return time.perf_counter_ns()


def wall_time_ns() -> int:
    return monotonic_wall_ns()


def span_clocks(start_wall: int, start_mono: int, end_wall: int, end_mono: int) -> SpanClocks:
    return SpanClocks(
        start_wall_time_ns=start_wall,
        end_wall_time_ns=end_wall,
        start_monotonic_ns=start_mono,
        end_monotonic_ns=end_mono,
    )


__all__ = ["SpanClocks", "monotonic_process_ns", "span_clocks", "wall_time_ns"]
