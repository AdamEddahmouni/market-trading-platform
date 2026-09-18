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
from .governance import historical_research_governance_lines
from .manifest import (
    build_historical_research_run_manifest,
    config_fingerprint,
    derive_historical_research_run_id,
)
from .pipeline import HistoricalResearchHarnessResult, run_historical_research_harness
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
    "ChronologicalSplitPolicy",
    "DEFAULT_HISTORICAL_RESEARCH_FEATURES",
    "HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION",
    "HISTORICAL_RESEARCH_HARNESS_VERSION",
    "HISTORICAL_RESEARCH_LABEL_KIND",
    "HISTORICAL_RESEARCH_RUN_MANIFEST_KIND",
    "HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED",
    "HistoricalResearchHarnessResult",
    "HistoricalResearchHoldoutConsumptionError",
    "HistoricalResearchRunConfig",
    "HistoricalResearchSplitName",
    "ITEM9_CALIBRATION_RESULT_KIND",
    "SIMULATOR_RESEARCH_RESULT_KIND",
    "assert_chronological_order",
    "assert_split_consumable_for_training_or_selection",
    "assign_chronological_splits",
    "build_historical_research_run_manifest",
    "chronological_split_boundaries",
    "config_fingerprint",
    "derive_historical_research_run_id",
    "historical_research_governance_lines",
    "reconstruct_historical_research_features",
    "run_historical_development_simulator_research",
    "run_historical_research_harness",
    "splits_overlap",
]
