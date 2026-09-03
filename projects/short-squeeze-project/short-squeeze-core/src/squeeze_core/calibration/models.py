from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.analysis.models import AnalysisCohortType, AnalysisUnit, ResearchAnalysisResult
from squeeze_core.research.models import (
    DetectionPredicatePolicy,
    DetectionStatus,
    FixtureClassification,
    OutcomeLabel,
    OutcomeLabelPolicy,
    ResearchCaseClassification,
)


class CalibrationExperimentType(StrEnum):
    DETECTION_ABLATION = "DETECTION_ABLATION"
    OUTCOME_SENSITIVITY = "OUTCOME_SENSITIVITY"


class DetectionVariantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str
    required_rule_ids: tuple[str, ...]
    provisional: bool = True
    rationale_code: str

    @field_validator("required_rule_ids")
    @classmethod
    def sort_rules(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class OutcomeVariantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str
    reference_price_policy: str = "first_eligible_trade_bar_close_at_or_after_boundary.v1"
    horizon: str = "24_HOURS"
    upward_threshold_percent: Decimal
    downward_threshold_percent: Decimal
    provisional: bool = True
    rationale_code: str


class CalibrationVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str
    description: str
    detection_policy: DetectionVariantSpec | None = None
    outcome_policy: OutcomeVariantSpec | None = None


class CalibrationExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    experiment_version: str
    experiment_type: CalibrationExperimentType
    source_dataset_path: str
    cohort_type: AnalysisCohortType
    analysis_unit: AnalysisUnit = AnalysisUnit.CASE_BOUNDARY
    baseline_variant_id: str
    variants: tuple[CalibrationVariant, ...]

    @field_validator("variants")
    @classmethod
    def non_empty(cls, value: tuple[CalibrationVariant, ...]) -> tuple[CalibrationVariant, ...]:
        if not value:
            raise ValueError("at least one variant is required")
        return value


class ClassificationFlip(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    baseline: ResearchCaseClassification
    variant: ResearchCaseClassification
    baseline_detection: DetectionStatus
    variant_detection: DetectionStatus
    baseline_outcome: OutcomeLabel
    variant_outcome: OutcomeLabel


class VariantResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str
    description: str
    case_count: int
    analysis: ResearchAnalysisResult
    flips_from_baseline: tuple[ClassificationFlip, ...] = ()


class CalibrationLimitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    statement: str


class CalibrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    calibration_version: str = "phase_3d_calibration.v1"
    experiment_version: str
    experiment_type: CalibrationExperimentType
    cohort_type: AnalysisCohortType
    analysis_unit: AnalysisUnit
    source_dataset_path: str
    baseline_variant_id: str
    variant_results: tuple[VariantResult, ...]
    limitations: tuple[CalibrationLimitation, ...]


_COHORT_FIXTURE_MAP = {
    AnalysisCohortType.SYNTHETIC_CASES: FixtureClassification.SYNTHETIC_EDGE_CASE,
    AnalysisCohortType.HISTORICAL_COMPLETED_CASES: (
        FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA
    ),
}


def fixture_classification_for_cohort(cohort_type: AnalysisCohortType) -> FixtureClassification:
    try:
        return _COHORT_FIXTURE_MAP[cohort_type]
    except KeyError as exc:
        raise ValueError(f"unsupported calibration cohort: {cohort_type}") from exc


__all__ = [
    "CalibrationExperiment",
    "CalibrationExperimentType",
    "CalibrationLimitation",
    "CalibrationReport",
    "CalibrationVariant",
    "ClassificationFlip",
    "DetectionVariantSpec",
    "OutcomeVariantSpec",
    "VariantResult",
    "fixture_classification_for_cohort",
]
