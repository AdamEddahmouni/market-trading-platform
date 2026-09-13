"""Fail-closed errors for PRODUCTION specialist ForecastV1 emission."""

from __future__ import annotations

from typing import Any


class ProductionError(Exception):
    """Base PRODUCTION specialist failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ProductionTrainingError(ProductionError):
    """Specialist training dataset or fit rejected."""


class ProductionEmitError(ProductionError):
    """PRODUCTION ForecastV1 emission rejected."""


class ProductionCalibrationError(ProductionError):
    """PRODUCTION calibrator training or persist rejected."""


__all__ = [
    "ProductionCalibrationError",
    "ProductionEmitError",
    "ProductionError",
    "ProductionTrainingError",
]
