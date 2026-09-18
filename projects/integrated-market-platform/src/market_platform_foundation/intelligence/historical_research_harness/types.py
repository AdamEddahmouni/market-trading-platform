"""Historical research harness types (HISTORICAL_DEVELOPMENT authority only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

HISTORICAL_RESEARCH_HARNESS_VERSION = "historical-research-harness-v1"
HISTORICAL_RESEARCH_RUN_MANIFEST_KIND = "historical_research_run_manifest_v1"
HISTORICAL_RESEARCH_RUN_SCHEMA_VERSION = "imp.historical-research-harness/1.0.0"
HISTORICAL_RESEARCH_LABEL_KIND = "historical_research_forward_return_label_v1"
HISTORICAL_RESEARCH_LABEL_AUTHORITY = "HISTORICAL_DEVELOPMENT"


class HistoricalResearchSplitName(StrEnum):
    """Chronological partitions; all remain HISTORICAL_DEVELOPMENT."""

    HISTORICAL_TRAIN = "HISTORICAL_TRAIN"
    HISTORICAL_DEVELOPMENT_VALIDATE = "HISTORICAL_DEVELOPMENT_VALIDATE"
    HISTORICAL_RESEARCH_TEST = "HISTORICAL_RESEARCH_TEST"


class MissingDataBehavior(StrEnum):
    SKIP = "SKIP"
    ZERO = "ZERO"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class ChronologicalSplitPolicy:
    """Chronological split; no random time-series shuffle by default."""

    policy_id: str = "historical_chronological_split_v1"
    train_fraction: float = 0.6
    development_validate_fraction: float = 0.2
    allow_shuffle: bool = False

    def __post_init__(self) -> None:
        if self.allow_shuffle:
            raise ValueError("CHRONOLOGICAL_SPLIT_SHUFFLE_FORBIDDEN")
        if self.train_fraction <= 0 or self.development_validate_fraction <= 0:
            raise ValueError("SPLIT_FRACTION_INVALID")
        if self.train_fraction + self.development_validate_fraction >= 1.0:
            raise ValueError("SPLIT_FRACTION_SUM_INVALID")


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    feature_id: str
    schema_version: str
    lookback_bars: int
    missing_data_behavior: MissingDataBehavior = MissingDataBehavior.ABSTAIN

    def __post_init__(self) -> None:
        if not self.feature_id or self.lookback_bars < 0:
            raise ValueError("FEATURE_SPEC_INVALID")


@dataclass(frozen=True, slots=True)
class HistoricalResearchSplitAssignment:
    decision_time_ns: int
    split: HistoricalResearchSplitName


@dataclass(frozen=True, slots=True)
class HistoricalResearchRunConfig:
    experiment_id: str
    hypothesis_id: str
    forward_horizon_bars: int = 1
    split_policy: ChronologicalSplitPolicy = field(default_factory=ChronologicalSplitPolicy)
    strategy_id: str = "historical_momentum_sign_v1"
    strategy_version: str = "1.0.0"
    simulator_version: str = "paper_bar_conservative_v1"
    cost_slippage_bps: float = 5.0
    parent_run_id: str | None = None
    challenger_of_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.hypothesis_id:
            raise ValueError("RUN_CONFIG_IDS_REQUIRED")
        if self.forward_horizon_bars < 1:
            raise ValueError("FORWARD_HORIZON_INVALID")


__all__ = [
    "ChronologicalSplitPolicy",
    "FeatureSpec",
    "HISTORICAL_RESEARCH_HARNESS_VERSION",
    "HISTORICAL_RESEARCH_LABEL_AUTHORITY",
    "HISTORICAL_RESEARCH_LABEL_KIND",
    "HISTORICAL_RESEARCH_RUN_MANIFEST_KIND",
    "HISTORICAL_RESEARCH_RUN_SCHEMA_VERSION",
    "HistoricalResearchRunConfig",
    "HistoricalResearchSplitAssignment",
    "HistoricalResearchSplitName",
    "MissingDataBehavior",
]
