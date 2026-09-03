"""Typed errors for BUILD 14 fusion, calibration, and uncertainty."""

from __future__ import annotations


class FusionError(Exception):
    """Base fusion error."""


class FusionInputError(FusionError):
    """Invalid fusion manifest or contributor input."""


class FusionCompatibilityError(FusionError):
    """Contributor compatibility violation."""


class FusionDependenceError(FusionError):
    """Dependence resolution failure."""


class CalibrationError(Exception):
    """Base calibration error."""


class CalibrationTrainingError(CalibrationError):
    """Calibration dataset or training failure."""


class CalibrationCompatibilityError(CalibrationError):
    """Calibration artifact mismatch with application context."""


class CalibrationAvailabilityError(CalibrationError):
    """Calibration artifact not yet available at decision time."""


class UncertaintyError(Exception):
    """Uncertainty assessment failure."""


class FinalForecastError(Exception):
    """Final forecast construction failure."""


__all__ = [
    "CalibrationAvailabilityError",
    "CalibrationCompatibilityError",
    "CalibrationError",
    "CalibrationTrainingError",
    "FinalForecastError",
    "FusionCompatibilityError",
    "FusionDependenceError",
    "FusionError",
    "FusionInputError",
    "UncertaintyError",
]
