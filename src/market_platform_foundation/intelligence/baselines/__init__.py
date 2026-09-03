"""Baseline prediction system (BUILD 08)."""

from .controls import (
    AlwaysDownBaseline,
    AlwaysUpBaseline,
    DeterministicRandomBaseline,
    EmpiricalPriorBaseline,
    FixedPriorBaseline,
    GradientBoostingBaseline,
    LogisticRegressionBaseline,
    MomentumBaseline,
    RegimeConditionedPriorBaseline,
    UnseenRegimePolicy,
)
from .engine import (
    BaselinePredictionEngine,
    direction_up_down_target,
    persist_forecast,
)
from .errors import BaselineError, BaselinePredictionError, BaselineTrainingError
from .features import (
    DEFAULT_STATISTICAL_FEATURE_SCHEMA,
    DEFAULT_STATISTICAL_WINDOW_NS,
    BaselineFeatureSchema,
    FeatureSelector,
    FeatureVectorBuilder,
)
from .suite import BaselineSuite, BaselineSuiteResult, default_control_suite
from .training import (
    BaselineTrainingDataset,
    BaselineTrainingExample,
    build_training_dataset,
    build_training_example,
)
from .types import (
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineModelDescriptor,
    BaselinePredictionContext,
    BaselinePredictionRequest,
    BaselinePredictionResult,
    FitSummary,
    PredictionDiagnostic,
    PredictionDiagnosticCode,
    PredictionStatus,
)

__all__ = [
    "AlwaysDownBaseline",
    "AlwaysUpBaseline",
    "BaselineClassLabel",
    "BaselineError",
    "BaselineFeatureSchema",
    "BaselineFeatureVector",
    "BaselineModelDescriptor",
    "BaselinePredictionContext",
    "BaselinePredictionError",
    "BaselinePredictionRequest",
    "BaselinePredictionResult",
    "BaselineSuite",
    "BaselineSuiteResult",
    "BaselineTrainingDataset",
    "BaselineTrainingExample",
    "BaselineTrainingError",
    "DEFAULT_STATISTICAL_FEATURE_SCHEMA",
    "DEFAULT_STATISTICAL_WINDOW_NS",
    "DeterministicRandomBaseline",
    "EmpiricalPriorBaseline",
    "FeatureSelector",
    "FeatureVectorBuilder",
    "FitSummary",
    "FixedPriorBaseline",
    "GradientBoostingBaseline",
    "LogisticRegressionBaseline",
    "MomentumBaseline",
    "PredictionDiagnostic",
    "PredictionDiagnosticCode",
    "PredictionStatus",
    "RegimeConditionedPriorBaseline",
    "UnseenRegimePolicy",
    "build_training_dataset",
    "build_training_example",
    "default_control_suite",
    "direction_up_down_target",
    "persist_forecast",
]
