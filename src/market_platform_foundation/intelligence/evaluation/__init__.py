"""Deterministic evaluation diagnostics (BUILD 16)."""

from .errors import EvaluationError
from .identity import derive_cohort_fingerprint, derive_evaluation_spec_id, derive_report_id
from .report import evaluation_report_v1_from_dict, evaluation_report_v1_to_dict
from .service import EvaluationService, TRUE_PREDICTION_COVERAGE_UNAVAILABLE
from .types import (
    EVALUATION_IMPLEMENTATION_VERSION,
    EvaluationReportV1,
    EvaluationSpec,
    ProbabilityView,
)

__all__ = [
    "EVALUATION_IMPLEMENTATION_VERSION",
    "EvaluationError",
    "EvaluationReportV1",
    "EvaluationService",
    "EvaluationSpec",
    "ProbabilityView",
    "TRUE_PREDICTION_COVERAGE_UNAVAILABLE",
    "derive_cohort_fingerprint",
    "derive_evaluation_spec_id",
    "derive_report_id",
    "evaluation_report_v1_from_dict",
    "evaluation_report_v1_to_dict",
]
