"""Runtime types for BUILD 14 fusion, calibration, and uncertainty."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import ForecastV1
from ..contracts.common import ContractReference, ForecastTarget, IntelligenceScope, QualityState, TimeHorizonNs


class ForecastContributorRole(StrEnum):
    PRODUCTION = "PRODUCTION"
    CONTROL = "CONTROL"
    RESEARCH = "RESEARCH"


class FusionDiagnosticCode(StrEnum):
    CONTROL_EXCLUDED = "CONTROL_EXCLUDED"
    NO_ELIGIBLE_CONTRIBUTOR = "NO_ELIGIBLE_CONTRIBUTOR"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    HORIZON_MISMATCH = "HORIZON_MISMATCH"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    DECISION_TIME_MISMATCH = "DECISION_TIME_MISMATCH"
    INVALID_PROBABILITY = "INVALID_PROBABILITY"
    DEGRADED_EXCLUDED = "DEGRADED_EXCLUDED"
    DEPENDENCE_UNKNOWN = "DEPENDENCE_UNKNOWN"
    DUPLICATE_FORECAST = "DUPLICATE_FORECAST"
    INSUFFICIENT_INDEPENDENT_GROUPS = "INSUFFICIENT_INDEPENDENT_GROUPS"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"


class CalibrationStatus(StrEnum):
    CALIBRATED = "CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
    CALIBRATION_MISMATCH = "CALIBRATION_MISMATCH"
    CALIBRATION_OOD = "CALIBRATION_OOD"
    IDENTITY_CONTROL = "IDENTITY_CONTROL"


class CalibrationMethod(StrEnum):
    LOGISTIC_PROBABILITY = "LOGISTIC_PROBABILITY"
    ISOTONIC = "ISOTONIC"
    IDENTITY_CONTROL = "IDENTITY_CONTROL"


class ForecastDecisionStatus(StrEnum):
    EMITTED_CALIBRATED = "EMITTED_CALIBRATED"
    RAW_ONLY_RESEARCH = "RAW_ONLY_RESEARCH"
    ABSTAINED_NO_CONTRIBUTORS = "ABSTAINED_NO_CONTRIBUTORS"
    ABSTAINED_CONTROL_ONLY = "ABSTAINED_CONTROL_ONLY"
    ABSTAINED_INSUFFICIENT_COVERAGE = "ABSTAINED_INSUFFICIENT_COVERAGE"
    ABSTAINED_INSUFFICIENT_INDEPENDENCE = "ABSTAINED_INSUFFICIENT_INDEPENDENCE"
    ABSTAINED_CALIBRATION_UNAVAILABLE = "ABSTAINED_CALIBRATION_UNAVAILABLE"
    ABSTAINED_CALIBRATION_MISMATCH = "ABSTAINED_CALIBRATION_MISMATCH"
    ABSTAINED_OOD = "ABSTAINED_OOD"
    ABSTAINED_DISAGREEMENT = "ABSTAINED_DISAGREEMENT"
    ABSTAINED_QUALITY = "ABSTAINED_QUALITY"
    INVALID_INPUT = "INVALID_INPUT"


class OodReason(StrEnum):
    CALIBRATION_RANGE_OOD = "CALIBRATION_RANGE_OOD"
    REGIME_OOD = "REGIME_OOD"


class EpistemicState(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class DependenceState(StrEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"


POOLING_METHOD = "DEPENDENCY_GROUP_EQUALIZED_LINEAR_POOL_V1"
DEPENDENCE_RESOLVER_VERSION = "forecast-dependence-resolver-v1"
FINAL_FORECAST_STAGE = "FINAL_FUSED_CALIBRATED"
CONTROL_FORECAST_STAGE = "CONTROL_RAW"


@dataclass(frozen=True, slots=True)
class FusionDiagnostic:
    code: FusionDiagnosticCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FusionContributorRef:
    forecast: ForecastV1
    role: ForecastContributorRole
    contributor_weight: float = 1.0
    forecast_family_key: str | None = None

    def __post_init__(self) -> None:
        if self.contributor_weight <= 0:
            raise ValueError("FUSION_CONTRIBUTOR_WEIGHT_INVALID")


@dataclass(frozen=True, slots=True)
class ForecastDependenceGroup:
    group_id: str
    forecast_ids: tuple[str, ...]
    group_probability: float | None = None
    group_weight: float = 1.0


@dataclass(frozen=True, slots=True)
class RawFusionResult:
    fusion_id: str
    manifest_id: str
    raw_probability: float | None
    eligible_contributor_ids: tuple[str, ...]
    excluded_contributor_ids: tuple[str, ...]
    dependence_groups: tuple[ForecastDependenceGroup, ...]
    quality: QualityState
    diagnostics: tuple[FusionDiagnostic, ...] = ()
    dependence_state: DependenceState = DependenceState.RESOLVED


@dataclass(frozen=True, slots=True)
class CalibrationExample:
    raw_fusion_id: str
    raw_probability: float
    target: ForecastTarget
    horizon: TimeHorizonNs
    scope: IntelligenceScope
    forecast_decision_time_ns: int
    label: int
    label_available_time_ns: int
    fusion_policy_identity: str
    regime_key: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrationDataset:
    dataset_id: str
    examples: tuple[CalibrationExample, ...]
    target: ForecastTarget
    horizon: TimeHorizonNs
    fusion_policy_identity: str
    calibration_cutoff_ns: int
    regime_key: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrationModelArtifact:
    calibration_model_id: str
    method: CalibrationMethod
    method_version: str
    target: ForecastTarget
    horizon: TimeHorizonNs
    fusion_policy_identity: str
    dataset_fingerprint: str
    training_cutoff_ns: int
    available_time_ns: int
    parameters: dict[str, Any]
    parameter_fingerprint: str
    min_training_raw_probability: float
    max_training_raw_probability: float
    sample_count: int
    class_counts: dict[str, int]
    regime_key: str | None = None


@dataclass(frozen=True, slots=True)
class UncertaintyAssessment:
    assessment_id: str
    raw_probability: float | None
    calibrated_probability: float | None
    predictive_entropy: float | None
    independent_group_count: int
    inter_group_probability_dispersion: float | None
    epistemic_state: EpistemicState
    coverage: dict[str, Any]
    calibration_status: CalibrationStatus
    ood_reasons: tuple[OodReason, ...] = ()
    quality_state: QualityState = QualityState.UNKNOWN
    abstention_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ForecastDecisionResult:
    status: ForecastDecisionStatus
    forecast: ForecastV1 | None = None
    raw_fusion: RawFusionResult | None = None
    uncertainty: UncertaintyAssessment | None = None
    diagnostics: tuple[FusionDiagnostic, ...] = ()


__all__ = [
    "CalibrationDataset",
    "CalibrationExample",
    "CalibrationMethod",
    "CalibrationModelArtifact",
    "CalibrationStatus",
    "CONTROL_FORECAST_STAGE",
    "DependenceState",
    "EpistemicState",
    "FINAL_FORECAST_STAGE",
    "ForecastContributorRole",
    "ForecastDecisionResult",
    "ForecastDecisionStatus",
    "ForecastDependenceGroup",
    "FusionContributorRef",
    "FusionDiagnostic",
    "FusionDiagnosticCode",
    "OodReason",
    "POOLING_METHOD",
    "RawFusionResult",
    "UncertaintyAssessment",
]
