"""Structured replay runtime errors (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ReplayError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}:{self.message}"


class ReplayConfigurationError(ReplayError):
    """Invalid replay scenario or schedule configuration."""


class ReplayClockError(ReplayError):
    """Replay virtual clock violation."""


class ReplayIsolationError(ReplayError):
    """Unsafe source/output repository aliasing."""


class ReplayVisibilityError(ReplayError):
    """Replay visibility boundary violation."""


class ReplayRuntimeError(ReplayError):
    """Unexpected replay runtime failure."""


__all__ = [
    "ReplayClockError",
    "ReplayConfigurationError",
    "ReplayError",
    "ReplayIsolationError",
    "ReplayRuntimeError",
    "ReplayVisibilityError",
]
