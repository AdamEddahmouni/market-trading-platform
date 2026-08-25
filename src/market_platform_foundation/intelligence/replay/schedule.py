"""Deterministic replay decision schedules (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ReplayConfigurationError


@dataclass(frozen=True, slots=True)
class ReplayDecisionSchedule:
    """Explicit monotonic decision times within the replay window."""

    decision_times_ns: tuple[int, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(int(value) for value in self.decision_times_ns))
        if len(ordered) != len(set(ordered)):
            raise ReplayConfigurationError(
                "DECISION_SCHEDULE_DUPLICATE",
                "decision schedule must not contain duplicate times",
            )
        object.__setattr__(self, "decision_times_ns", ordered)

    @classmethod
    def fixed_cadence(
        cls,
        *,
        start_time_ns: int,
        end_time_ns: int,
        interval_ns: int,
        inclusive_end: bool = True,
    ) -> ReplayDecisionSchedule:
        if interval_ns <= 0:
            raise ReplayConfigurationError(
                "DECISION_INTERVAL_INVALID",
                "interval_ns must be positive",
            )
        if start_time_ns > end_time_ns:
            raise ReplayConfigurationError(
                "DECISION_RANGE_INVALID",
                "start_time_ns must be <= end_time_ns",
            )
        times: list[int] = []
        current = start_time_ns
        while current < end_time_ns or (inclusive_end and current == end_time_ns):
            times.append(current)
            if current == end_time_ns:
                break
            current += interval_ns
            if current > end_time_ns and not inclusive_end:
                break
        return cls(decision_times_ns=tuple(times))

    def validate_within_window(
        self,
        *,
        window_start_ns: int,
        window_end_ns: int,
    ) -> None:
        for decision_time_ns in self.decision_times_ns:
            if decision_time_ns < window_start_ns:
                raise ReplayConfigurationError(
                    "DECISION_BEFORE_WINDOW",
                    "decision time precedes replay window start",
                    details={"decision_time_ns": decision_time_ns, "window_start_ns": window_start_ns},
                )
            if decision_time_ns > window_end_ns:
                raise ReplayConfigurationError(
                    "DECISION_AFTER_WINDOW",
                    "decision time exceeds replay window end",
                    details={"decision_time_ns": decision_time_ns, "window_end_ns": window_end_ns},
                )


__all__ = ["ReplayDecisionSchedule"]
