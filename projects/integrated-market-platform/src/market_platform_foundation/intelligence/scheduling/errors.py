"""BUILD 10 scheduler error hierarchy."""

from __future__ import annotations


class SchedulerError(Exception):
    """Base scheduler error."""

    def __init__(self, code: str, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class SchedulerConfigurationError(SchedulerError):
    """Invalid scheduler configuration."""


class SchedulerAdmissionError(SchedulerError):
    """Route admission rejected."""


class SchedulerStateTransitionError(SchedulerError):
    """Invalid lifecycle transition."""


class SchedulerResourceError(SchedulerError):
    """Resource admission failure."""


class SchedulerDispatchError(SchedulerError):
    """Dispatch boundary failure."""


__all__ = [
    "SchedulerAdmissionError",
    "SchedulerConfigurationError",
    "SchedulerDispatchError",
    "SchedulerError",
    "SchedulerResourceError",
    "SchedulerStateTransitionError",
]
