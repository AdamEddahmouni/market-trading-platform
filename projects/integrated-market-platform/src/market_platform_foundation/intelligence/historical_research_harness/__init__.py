"""Historical research harness (HISTORICAL_DEVELOPMENT authority only)."""

from .consumption import (
    HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED,
    HistoricalResearchHoldoutConsumptionError,
    assert_split_consumable_for_training_or_selection,
)
from .features import (
    DEFAULT_HISTORICAL_RESEARCH_FEATURES,
    HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
    reconstruct_historical_research_features,
)
from .baseline_pack import (
    HISTORICAL_BASELINE_PACK_V1,
    build_frozen_baseline_pack_experiment_definition,
    run_frozen_historical_baseline_pack_v1,
)
from .governance import historical_research_governance_lines
from .strategies import predict_direction
from .manifest import (
    build_historical_research_run_manifest,
    config_fingerprint,
    derive_historical_research_run_id,
)
from .pipeline import HistoricalResearchHarnessResult, run_historical_research_harness
from .fill_economics import (
    ACCOUNTING_VERSION,
    COST_MODEL_VERSION,
    FillEconomicsInvariantError,
)
from .prediction_coupling import (
    PREDICTION_COUPLING_SCHEMA_VERSION,
    PredictionCoupledSimulatorError,
    build_signal_interpretations_from_predictions,
)
from .simulator import (
    ITEM9_CALIBRATION_RESULT_KIND,
    SIMULATOR_RESEARCH_RESULT_KIND,
    run_historical_development_simulator_research,
)
from .split import (
    assign_chronological_splits,
    assert_chronological_order,
    chronological_split_boundaries,
    splits_overlap,
)
from .types import (
    HISTORICAL_RESEARCH_HARNESS_VERSION,
    HISTORICAL_RESEARCH_LABEL_KIND,
    HISTORICAL_RESEARCH_RUN_MANIFEST_KIND,
    ChronologicalSplitPolicy,
    HistoricalResearchRunConfig,
    HistoricalResearchSplitName,
)

__all__ = [
    "ACCOUNTING_VERSION",
    "COST_MODEL_VERSION",
    "ChronologicalSplitPolicy",
    "FillEconomicsInvariantError",
    "DEFAULT_HISTORICAL_RESEARCH_FEATURES",
    "HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION",
    "HISTORICAL_RESEARCH_HARNESS_VERSION",
    "HISTORICAL_RESEARCH_LABEL_KIND",
    "HISTORICAL_BASELINE_PACK_V1",
    "HISTORICAL_RESEARCH_RUN_MANIFEST_KIND",
    "HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED",
    "HistoricalResearchHarnessResult",
    "HistoricalResearchHoldoutConsumptionError",
    "HistoricalResearchRunConfig",
    "HistoricalResearchSplitName",
    "ITEM9_CALIBRATION_RESULT_KIND",
    "PREDICTION_COUPLING_SCHEMA_VERSION",
    "PredictionCoupledSimulatorError",
    "SIMULATOR_RESEARCH_RESULT_KIND",
    "assert_chronological_order",
    "assert_split_consumable_for_training_or_selection",
    "assign_chronological_splits",
    "build_frozen_baseline_pack_experiment_definition",
    "build_historical_research_run_manifest",
    "build_signal_interpretations_from_predictions",
    "chronological_split_boundaries",
    "config_fingerprint",
    "derive_historical_research_run_id",
    "historical_research_governance_lines",
    "predict_direction",
    "reconstruct_historical_research_features",
    "run_frozen_historical_baseline_pack_v1",
    "run_historical_development_simulator_research",
    "run_historical_research_harness",
    "splits_overlap",
]
