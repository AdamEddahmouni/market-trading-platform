"""Temporally legal Path A PRODUCTION CalibrationModelArtifact trainer.

Trains ``LOGISTIC_PROBABILITY`` or ``ISOTONIC`` on settled labels through the
BUILD 14 dataset firewall. ``IDENTITY_CONTROL`` is rejected. Live is
forbidden. The artifact is not a Model Registry entry.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import ForecastTarget, TimeHorizonNs
from ..fusion.calibration_data import (
    CalibrationDatasetBuilder,
    MINIMUM_CALIBRATION_SAMPLES,
    MINIMUM_CLASS_COUNT,
    dataset_support_summary,
    horizons_equal,
    targets_equal,
)
from ..fusion.calibrators import CalibrationTrainer
from ..fusion.errors import CalibrationTrainingError
from ..fusion.policy import DEFAULT_PRODUCTION_FUSION_POLICY
from ..fusion.types import CalibrationExample, CalibrationMethod, CalibrationModelArtifact
from .identity import matches_path_a_identity

STATUS_TRAINED = "TRAINED"
STATUS_CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"
ALLOWED_MODES = frozenset({"demo", "paper"})
FORBIDDEN_LIVE_MODES = frozenset({"live", "actual_live"})
ALLOWED_METHODS = frozenset({CalibrationMethod.LOGISTIC_PROBABILITY, CalibrationMethod.ISOTONIC})


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()


@dataclass(frozen=True, slots=True)
class ProductionCalibrationResult:
    status: str
    reason_codes: tuple[str, ...]
    artifact: CalibrationModelArtifact | None = None

    @property
    def trained(self) -> bool:
        return self.status == STATUS_TRAINED and self.artifact is not None


def _unavailable(*reason_codes: str) -> ProductionCalibrationResult:
    codes = tuple(dict.fromkeys((STATUS_CALIBRATION_UNAVAILABLE, *reason_codes)))
    return ProductionCalibrationResult(status=STATUS_CALIBRATION_UNAVAILABLE, reason_codes=codes)


def train_production_calibration(
    examples: list[CalibrationExample],
    *,
    method: CalibrationMethod,
    available_time_ns: int,
    decision_time_ns: int,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    fusion_policy_identity: str,
    calibration_cutoff_ns: int,
    mode: str,
    regime_key: str | None = None,
) -> ProductionCalibrationResult:
    """Fit a Path A PRODUCTION calibrator. Persist is a separate lawful step."""

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        return ProductionCalibrationResult(
            status=STATUS_LIVE_FORBIDDEN,
            reason_codes=("LIVE_SCAN_CALLER_FORBIDDEN",),
        )
    if mode_n not in ALLOWED_MODES:
        return _unavailable("MODE_NOT_PAPER_OR_DEMO")
    if method == CalibrationMethod.IDENTITY_CONTROL:
        return _unavailable("IDENTITY_CONTROL_REJECTED")
    if method not in ALLOWED_METHODS:
        return _unavailable("UNSUPPORTED_CALIBRATION_METHOD")

    identity_reasons = matches_path_a_identity(target=target, horizon=horizon)
    if identity_reasons:
        return _unavailable(*identity_reasons)
    expected_policy = DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity
    if fusion_policy_identity != expected_policy:
        return _unavailable("FUSION_POLICY_MISMATCH")
    if available_time_ns > decision_time_ns:
        return _unavailable("CALIBRATION_NOT_YET_AVAILABLE")
    if available_time_ns < calibration_cutoff_ns:
        return _unavailable("AVAILABLE_BEFORE_TRAINING_CUTOFF")
    if calibration_cutoff_ns > decision_time_ns:
        return _unavailable("TRAINING_CUTOFF_AFTER_DECISION")

    for example in examples:
        if not targets_equal(example.target, target):
            return _unavailable("TARGET_MISMATCH")
        if not horizons_equal(example.horizon, horizon):
            return _unavailable("HORIZON_MISMATCH")
        if example.fusion_policy_identity != fusion_policy_identity:
            return _unavailable("FUSION_POLICY_MISMATCH")

    try:
        dataset = CalibrationDatasetBuilder().build(
            examples,
            target=target,
            horizon=horizon,
            fusion_policy_identity=fusion_policy_identity,
            calibration_cutoff_ns=calibration_cutoff_ns,
            regime_key=regime_key,
        )
    except CalibrationTrainingError as error:
        return _unavailable(str(error))

    support = dataset_support_summary(dataset)
    if support["sample_count"] < MINIMUM_CALIBRATION_SAMPLES:
        return _unavailable("INSUFFICIENT_CALIBRATION_SAMPLES")
    if support["class_0"] < MINIMUM_CLASS_COUNT or support["class_1"] < MINIMUM_CLASS_COUNT:
        return _unavailable("INSUFFICIENT_CALIBRATION_CLASS_COUNT")

    artifact = CalibrationTrainer().fit(
        dataset,
        method=method,
        available_time_ns=available_time_ns,
    )
    if artifact is None:
        return _unavailable("CALIBRATION_TRAINING_ABSTAINED")
    if artifact.method == CalibrationMethod.IDENTITY_CONTROL:
        return _unavailable("IDENTITY_CONTROL_REJECTED")
    if artifact.available_time_ns > decision_time_ns:
        return _unavailable("CALIBRATION_NOT_YET_AVAILABLE")
    return ProductionCalibrationResult(
        status=STATUS_TRAINED,
        reason_codes=(STATUS_TRAINED,),
        artifact=artifact,
    )


__all__ = [
    "ALLOWED_METHODS",
    "ALLOWED_MODES",
    "FORBIDDEN_LIVE_MODES",
    "ProductionCalibrationResult",
    "STATUS_CALIBRATION_UNAVAILABLE",
    "STATUS_LIVE_FORBIDDEN",
    "STATUS_TRAINED",
    "train_production_calibration",
]
