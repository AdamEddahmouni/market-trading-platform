"""Signal computation errors (BUILD 06)."""

from __future__ import annotations


class SignalComputationError(Exception):
    """Base error for signal engine failures."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class SignalInputError(SignalComputationError):
    """Invalid or prohibited snapshot/input state for computation."""


class UnsupportedSignalError(SignalComputationError):
    """Requested signal type is not registered."""


class SignalDeterminismError(SignalComputationError):
    """Non-deterministic or conflicting signal identity detected."""


__all__ = [
    "SignalComputationError",
    "SignalDeterminismError",
    "SignalInputError",
    "UnsupportedSignalError",
]
