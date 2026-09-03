"""Baseline prediction error taxonomy (BUILD 08)."""

from __future__ import annotations

from typing import Any


class BaselineError(Exception):
    """Base baseline failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class BaselineTrainingError(BaselineError):
    """Training dataset or fit procedure rejected."""


class BaselinePredictionError(BaselineError):
    """Prediction request or model output rejected."""


__all__ = ["BaselineError", "BaselinePredictionError", "BaselineTrainingError"]
