"""Paper simulator calibration contracts and metric computation (not market truth)."""

from .comparator_contract import (
    COMPARATOR_NOT_MARKET_TRUTH_STATEMENT,
    ExternalPaperComparatorBinding,
    validate_comparator_binding,
)
from .futures_suitability import (
    FuturesComparatorSuitability,
    assess_futures_comparator_suitability,
)
from .metrics import (
    CalibrationDivergenceClass,
    CalibrationMetricBundle,
    compute_calibration_metrics,
)
from .thresholds import (
    THRESHOLD_UNSET_BLOCKING,
    CalibrationThresholdConfig,
    CalibrationThresholdField,
    ThresholdStatus,
    default_unset_threshold_config,
    load_threshold_config,
    validate_threshold_config,
)

__all__ = [
    "COMPARATOR_NOT_MARKET_TRUTH_STATEMENT",
    "CalibrationDivergenceClass",
    "CalibrationMetricBundle",
    "CalibrationThresholdConfig",
    "CalibrationThresholdField",
    "ExternalPaperComparatorBinding",
    "FuturesComparatorSuitability",
    "THRESHOLD_UNSET_BLOCKING",
    "ThresholdStatus",
    "assess_futures_comparator_suitability",
    "compute_calibration_metrics",
    "default_unset_threshold_config",
    "load_threshold_config",
    "validate_comparator_binding",
    "validate_threshold_config",
]
