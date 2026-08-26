"""Evaluation configuration and result types (BUILD 16)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import Direction, ForecastTarget, QualityState
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..fusion.types import ForecastContributorRole

EVALUATION_IMPLEMENTATION_VERSION = "evaluation-diagnostics-v1"
DEFAULT_CALIBRATION_BIN_COUNT = 10
DEFAULT_LOG_LOSS_EPSILON = 1e-15
DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_MINIMUM_SLICE_SIZE = 5


class ProbabilityView(StrEnum):
    RAW = "RAW"
    CALIBRATED = "CALIBRATED"
    OPERATIONAL = "OPERATIONAL"


class PredictionDiagnosticState(StrEnum):
    CORRECT = "CORRECT"
    FALSE_UP = "FALSE_UP"
    FALSE_DOWN = "FALSE_DOWN"
    UNLABELABLE = "UNLABELABLE"
    NOT_SETTLED = "NOT_SETTLED"
    FUTURE_LABEL = "FUTURE_LABEL"
    INELIGIBLE = "INELIGIBLE"


class SliceStatus(StrEnum):
    OK = "OK"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    UNSUPPORTED = "UNSUPPORTED"


class AggregateStatus(StrEnum):
    OK = "OK"
    EMPTY_COHORT = "EMPTY_COHORT"
    NO_LABELABLE = "NO_LABELABLE"
    PROBABILITY_UNAVAILABLE = "PROBABILITY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class EvaluationSpec:
    """Frozen evaluation configuration — identity excludes runtime and wall clock."""

    evaluation_as_of_ns: int
    decision_start_ns: int
    decision_end_ns: int
    target_kind: str
    horizon_ns: int
    mode: str
    probability_view: ProbabilityView
    calibration_bin_count: int = DEFAULT_CALIBRATION_BIN_COUNT
    log_loss_epsilon: float = DEFAULT_LOG_LOSS_EPSILON
    minimum_slice_size: int = DEFAULT_MINIMUM_SLICE_SIZE
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD
    scenario_id: str | None = None
    slice_dimensions: tuple[str, ...] = ()
    implementation_version: str = EVALUATION_IMPLEMENTATION_VERSION

    def __post_init__(self) -> None:
        if self.decision_start_ns >= self.decision_end_ns:
            raise ValueError("DECISION_RANGE_INVALID")
        if self.horizon_ns <= 0:
            raise ValueError("HORIZON_MUST_BE_POSITIVE")
        if not self.target_kind:
            raise ValueError("TARGET_KIND_REQUIRED")
        if not self.mode:
            raise ValueError("MODE_REQUIRED")
        if self.calibration_bin_count < 1:
            raise ValueError("CALIBRATION_BIN_COUNT_INVALID")
        if not 0.0 < self.log_loss_epsilon < 0.5:
            raise ValueError("LOG_LOSS_EPSILON_INVALID")
        if self.minimum_slice_size < 1:
            raise ValueError("MINIMUM_SLICE_SIZE_INVALID")
        if not 0.0 < self.high_confidence_threshold <= 1.0:
            raise ValueError("HIGH_CONFIDENCE_THRESHOLD_INVALID")


@dataclass(frozen=True, slots=True)
class EvaluationCohortRow:
    """One frozen scientific prediction binding forecast, ledger, and outcome."""

    forecast: ForecastV1
    ledger_entry: PredictionLedgerEntryV1
    outcome: OutcomeV1 | None
    label_available_time_ns: int | None
    diagnostic_state: PredictionDiagnosticState
    probability_raw: float | None
    probability_calibrated: float | None
    probability_operational: float | None
    binary_label: int | None
    predicted_direction: Direction | None
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted_probability: float | None
    empirical_positive_rate: float | None
    calibration_gap: float | None


@dataclass(frozen=True, slots=True)
class CalibrationDiagnostics:
    bins: tuple[ReliabilityBin, ...]
    ece: float | None
    mce: float | None
    brier_reliability: float | None = None
    brier_resolution: float | None = None
    brier_uncertainty: float | None = None


@dataclass(frozen=True, slots=True)
class PredictiveMetrics:
    status: AggregateStatus
    sample_count: int
    brier_score: float | None
    log_loss: float | None
    directional_hit_rate: float | None
    mean_confidence: float | None
    boundary_clip_count: int = 0
    per_row_brier: tuple[tuple[str, float], ...] = ()
    per_row_log_loss: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class SettlementDiagnostics:
    registered_count: int
    outcome_available_count: int
    labelable_count: int
    unlabelable_count: int
    not_settled_count: int
    future_label_count: int
    settlement_coverage: float | None
    labelable_fraction: float | None
    true_prediction_coverage_status: str
    adjudication_lag_ns: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SliceResult:
    dimension: str
    value: str
    status: SliceStatus
    sample_count: int
    metrics: PredictiveMetrics
    calibration: CalibrationDiagnostics | None = None


@dataclass(frozen=True, slots=True)
class PairedComparisonMetrics:
    candidate_forecast_id: str
    control_forecast_id: str
    candidate_brier: float | None
    control_brier: float | None
    brier_delta: float | None
    candidate_log_loss: float | None
    control_log_loss: float | None
    log_loss_delta: float | None
    candidate_hit_rate: float | None
    control_hit_rate: float | None
    hit_rate_delta: float | None


@dataclass(frozen=True, slots=True)
class ControlComparisonSummary:
    match_key_fields: tuple[str, ...]
    matched_count: int
    candidate_only_count: int
    control_only_count: int
    paired_metrics: tuple[PairedComparisonMetrics, ...] = ()
    aggregate_brier_delta: float | None = None
    aggregate_log_loss_delta: float | None = None
    aggregate_hit_rate_delta: float | None = None


@dataclass(frozen=True, slots=True)
class ProbabilityViewComparison:
    matched_count: int
    raw_brier: float | None
    calibrated_brier: float | None
    brier_delta: float | None
    raw_log_loss: float | None
    calibrated_log_loss: float | None
    log_loss_delta: float | None
    raw_ece: float | None
    calibrated_ece: float | None
    ece_delta: float | None


@dataclass(frozen=True, slots=True)
class ErrorSummary:
    correct_count: int
    false_up_count: int
    false_down_count: int
    unlabelable_count: int
    not_settled_count: int
    high_confidence_wrong_count: int
    largest_brier_contributions: tuple[tuple[str, float], ...] = ()
    largest_log_loss_contributions: tuple[tuple[str, float], ...] = ()
    highest_confidence_wrong: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationReportV1:
    report_id: str
    evaluation_spec_id: str
    evaluation_as_of_ns: int
    cohort_fingerprint: str
    probability_view: ProbabilityView
    implementation_version: str
    settlement: SettlementDiagnostics
    aggregate_metrics: PredictiveMetrics
    calibration: CalibrationDiagnostics | None
    probability_view_comparison: ProbabilityViewComparison | None
    slice_results: tuple[SliceResult, ...] = ()
    error_summary: ErrorSummary | None = None
    control_comparison: ControlComparisonSummary | None = None
    limitations: tuple[str, ...] = ()
    lineage: dict[str, Any] = field(default_factory=dict)
    row_diagnostics: tuple[dict[str, Any], ...] = ()


def forecast_role(forecast: ForecastV1) -> str:
    role = forecast.metadata.get("contributor_role")
    if role is not None:
        return str(role)
    stage = forecast.metadata.get("forecast_stage")
    if stage == "CONTROL_RAW":
        return ForecastContributorRole.CONTROL.value
    return ForecastContributorRole.PRODUCTION.value


def instrument_id_for_forecast(forecast: ForecastV1) -> str | None:
    ids = forecast.scope.instrument_ids
    if not ids:
        return None
    return ids[0]


__all__ = [
    "AggregateStatus",
    "CalibrationDiagnostics",
    "ControlComparisonSummary",
    "DEFAULT_CALIBRATION_BIN_COUNT",
    "DEFAULT_HIGH_CONFIDENCE_THRESHOLD",
    "DEFAULT_LOG_LOSS_EPSILON",
    "DEFAULT_MINIMUM_SLICE_SIZE",
    "EVALUATION_IMPLEMENTATION_VERSION",
    "ErrorSummary",
    "EvaluationCohortRow",
    "EvaluationReportV1",
    "EvaluationSpec",
    "PairedComparisonMetrics",
    "PredictionDiagnosticState",
    "PredictiveMetrics",
    "ProbabilityView",
    "ProbabilityViewComparison",
    "ReliabilityBin",
    "SettlementDiagnostics",
    "SliceResult",
    "SliceStatus",
    "forecast_role",
    "instrument_id_for_forecast",
]
