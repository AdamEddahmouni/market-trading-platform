"""Paper simulator calibration contracts and metric computation (not market truth)."""

from .asset_scope import (
    EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
    CalibrationAssetScopeError,
    assert_calibration_unit_asset_scope,
)
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
    CalibrationMetricReport,
    SampleHonesty,
    compute_calibration_metric_report,
    compute_calibration_metrics,
)
from .pairing import (
    ComparatorPairingRecord,
    PairedObservation,
    PairingResult,
    forward_test_correlation_id,
    pair_imp_and_comparator,
)
from .runner import (
    STATUS_COMPARATOR_NOT_CONFIGURED,
    STATUS_WAITING_FOR_MARKET,
    classify_calibration_run,
    run_calibration_campaign,
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
    "EQUITY_PAPER_DOES_NOT_VALIDATE_ES",
    "CalibrationAssetScopeError",
    "CalibrationDivergenceClass",
    "CalibrationMetricBundle",
    "CalibrationMetricReport",
    "CalibrationThresholdConfig",
    "CalibrationThresholdField",
    "ComparatorPairingRecord",
    "ExternalPaperComparatorBinding",
    "FuturesComparatorSuitability",
    "PairedObservation",
    "PairingResult",
    "STATUS_COMPARATOR_NOT_CONFIGURED",
    "STATUS_WAITING_FOR_MARKET",
    "SampleHonesty",
    "THRESHOLD_UNSET_BLOCKING",
    "ThresholdStatus",
    "assert_calibration_unit_asset_scope",
    "assess_futures_comparator_suitability",
    "classify_calibration_run",
    "compute_calibration_metric_report",
    "compute_calibration_metrics",
    "default_unset_threshold_config",
    "forward_test_correlation_id",
    "load_threshold_config",
    "pair_imp_and_comparator",
    "run_calibration_campaign",
    "validate_comparator_binding",
    "validate_threshold_config",
]
