"""Calibration application and compatibility checks for BUILD 14."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .calibration_data import horizons_equal, targets_equal
from .calibrators import apply_calibration
from .errors import CalibrationAvailabilityError, CalibrationCompatibilityError
from .types import CalibrationModelArtifact, CalibrationStatus, OodReason


@dataclass(frozen=True, slots=True)
class CalibrationApplicationResult:
    calibrated_probability: float | None
    status: CalibrationStatus
    ood_reasons: tuple[OodReason, ...] = ()


class CalibrationApplicator:
    def apply(
        self,
        *,
        artifact: CalibrationModelArtifact | None,
        raw_probability: float | None,
        target,
        horizon,
        fusion_policy_identity: str,
        decision_time_ns: int,
        regime_key: str | None = None,
    ) -> CalibrationApplicationResult:
        if raw_probability is None:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_UNAVAILABLE)
        if artifact is None:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_UNAVAILABLE)
        if artifact.available_time_ns > decision_time_ns:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_UNAVAILABLE)
        if not targets_equal(artifact.target, target):
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_MISMATCH)
        if not horizons_equal(artifact.horizon, horizon):
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_MISMATCH)
        if artifact.fusion_policy_identity != fusion_policy_identity:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_MISMATCH)
        if artifact.regime_key is not None and artifact.regime_key != regime_key:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_MISMATCH, (OodReason.REGIME_OOD,))
        if not math.isfinite(raw_probability):
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_MISMATCH)
        ood_reasons: list[OodReason] = []
        if raw_probability < artifact.min_training_raw_probability or raw_probability > artifact.max_training_raw_probability:
            ood_reasons.append(OodReason.CALIBRATION_RANGE_OOD)
        if artifact.method.value == "IDENTITY_CONTROL":
            return CalibrationApplicationResult(raw_probability, CalibrationStatus.IDENTITY_CONTROL, tuple(ood_reasons))
        try:
            calibrated = apply_calibration(artifact, raw_probability)
        except Exception:
            return CalibrationApplicationResult(None, CalibrationStatus.CALIBRATION_OOD, tuple(ood_reasons))
        if ood_reasons:
            return CalibrationApplicationResult(calibrated, CalibrationStatus.CALIBRATION_OOD, tuple(ood_reasons))
        return CalibrationApplicationResult(calibrated, CalibrationStatus.CALIBRATED)


def require_available(artifact: CalibrationModelArtifact, decision_time_ns: int) -> None:
    if artifact.available_time_ns > decision_time_ns:
        raise CalibrationAvailabilityError("CALIBRATION_NOT_YET_AVAILABLE")


__all__ = ["CalibrationApplicator", "CalibrationApplicationResult", "require_available"]
