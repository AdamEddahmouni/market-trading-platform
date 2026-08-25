"""Fusion, calibration, and uncertainty for BUILD 14."""

from .calibration import CalibrationApplicator, CalibrationApplicationResult
from .calibration_data import CalibrationDatasetBuilder, MINIMUM_CALIBRATION_SAMPLES, MINIMUM_CLASS_COUNT
from .calibrators import CalibrationTrainer, apply_calibration
from .decision import FinalForecastBuilder
from .dependence import DependenceGrouper
from .errors import (
    CalibrationAvailabilityError,
    CalibrationCompatibilityError,
    CalibrationError,
    CalibrationTrainingError,
    FinalForecastError,
    FusionCompatibilityError,
    FusionDependenceError,
    FusionError,
    FusionInputError,
    UncertaintyError,
)
from .fusion import FusionEngine
from .manifest import ForecastFusionManifest, build_contributor_ref
from .policy import (
    DEFAULT_PRODUCTION_FINAL_POLICY,
    DEFAULT_PRODUCTION_FUSION_POLICY,
    DEFAULT_RESEARCH_FINAL_POLICY,
    DEFAULT_RESEARCH_FUSION_POLICY,
    FinalForecastPolicy,
    FusionPolicy,
)
from .provenance import ForecastProvenanceResolver
from .roles import resolve_contributor_role, resolve_forecast_family_key
from .service import ForecastFusionService
from .types import (
    CalibrationDataset,
    CalibrationExample,
    CalibrationMethod,
    CalibrationModelArtifact,
    CalibrationStatus,
    CONTROL_FORECAST_STAGE,
    FINAL_FORECAST_STAGE,
    ForecastContributorRole,
    ForecastDecisionResult,
    ForecastDecisionStatus,
    ForecastDependenceGroup,
    FusionContributorRef,
    FusionDiagnostic,
    FusionDiagnosticCode,
    OodReason,
    POOLING_METHOD,
    RawFusionResult,
    UncertaintyAssessment,
)
from .pooling import across_group_probability, within_group_probability
from .uncertainty import UncertaintyAssessor, inter_group_dispersion, predictive_entropy

__all__ = [
    "CONTROL_FORECAST_STAGE",
    "CalibrationApplicator",
    "CalibrationApplicationResult",
    "CalibrationDataset",
    "CalibrationDatasetBuilder",
    "CalibrationError",
    "CalibrationExample",
    "CalibrationMethod",
    "CalibrationModelArtifact",
    "CalibrationStatus",
    "CalibrationTrainer",
    "CalibrationTrainingError",
    "DependenceGrouper",
    "FINAL_FORECAST_STAGE",
    "FinalForecastBuilder",
    "FinalForecastError",
    "FinalForecastPolicy",
    "ForecastContributorRole",
    "ForecastDecisionResult",
    "ForecastDecisionStatus",
    "ForecastDependenceGroup",
    "ForecastFusionManifest",
    "ForecastFusionService",
    "ForecastProvenanceResolver",
    "FusionCompatibilityError",
    "FusionContributorRef",
    "FusionDependenceError",
    "FusionDiagnostic",
    "FusionDiagnosticCode",
    "FusionEngine",
    "FusionError",
    "FusionInputError",
    "FusionPolicy",
    "MINIMUM_CALIBRATION_SAMPLES",
    "MINIMUM_CLASS_COUNT",
    "OodReason",
    "POOLING_METHOD",
    "RawFusionResult",
    "UncertaintyAssessment",
    "UncertaintyAssessor",
    "UncertaintyError",
    "across_group_probability",
    "apply_calibration",
    "build_contributor_ref",
    "inter_group_dispersion",
    "predictive_entropy",
    "resolve_contributor_role",
    "resolve_forecast_family_key",
    "within_group_probability",
    "DEFAULT_PRODUCTION_FINAL_POLICY",
    "DEFAULT_PRODUCTION_FUSION_POLICY",
    "DEFAULT_RESEARCH_FINAL_POLICY",
    "DEFAULT_RESEARCH_FUSION_POLICY",
]
