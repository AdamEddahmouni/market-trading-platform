"""Strategy research promotion and evidence registry contracts (Phase 5 Lane J).

Research promotion records govern eligibility for human review and FTEP candidacy.
They never grant Paper or Live execution authority on their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION

STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION = (
    "strategy-research-promotion-registry-v1"
)
STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY = "STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY"

RESEARCH_PROMOTION_RECORD_PREFIX = "SRP"


class StrategyResearchPromotionLifecycleState(StrEnum):
    DISCOVERED = "DISCOVERED"
    RUNNABLE = "RUNNABLE"
    PARITY_CHECKED = "PARITY_CHECKED"
    HISTORICAL_VALIDATED = "HISTORICAL_VALIDATED"
    OOS_VALIDATED = "OOS_VALIDATED"
    RESEARCH_APPROVED = "RESEARCH_APPROVED"
    FTEP_ELIGIBLE = "FTEP_ELIGIBLE"
    FTEP_TESTING = "FTEP_TESTING"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    REJECTED = "REJECTED"


class RuntimeParityDisposition(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class ResearchPromotionReasonCode(StrEnum):
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    INVALID_LIFECYCLE_TRANSITION = "INVALID_LIFECYCLE_TRANSITION"
    PARITY_EVIDENCE_MISSING = "PARITY_EVIDENCE_MISSING"
    PARITY_NOT_PASS = "PARITY_NOT_PASS"
    AUTO_PAPER_LIVE_ACTIVATION_FORBIDDEN = "AUTO_PAPER_LIVE_ACTIVATION_FORBIDDEN"
    RESEARCH_SUBORDINATE_TO_EXECUTION_ELIGIBILITY = "RESEARCH_SUBORDINATE_TO_EXECUTION_ELIGIBILITY"
    PROMOTION_REVIEW_ELIGIBLE = "PROMOTION_REVIEW_ELIGIBLE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ResearchResultSummaryV1:
    """Compact, comparable research outcome — not an execution signal."""

    summary_id: str
    metric_name: str
    metric_value: float | None
    sample_count: int | None = None
    window_label: str = ""
    report_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.summary_id or not self.metric_name:
            raise ValueError("RESEARCH_RESULT_SUMMARY_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class StrategyResearchEvidenceBundleV1:
    """Required evidence fields for governed promotion — completeness is enforced by the registry."""

    strategy_id: str
    runtime_id: str
    runtime_version: str
    source_hash: str
    dataset_hashes: tuple[str, ...]
    pit_classification: str
    in_sample_result: ResearchResultSummaryV1 | None
    out_of_sample_result: ResearchResultSummaryV1 | None
    walk_forward_result: ResearchResultSummaryV1 | None
    transaction_cost_assumptions: str
    regime_sensitivity: str
    capacity_liquidity_notes: str
    multiple_testing_controls: str
    challenger_results: tuple[str, ...]
    known_contradictions: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("STRATEGY_ID_REQUIRED")
        object.__setattr__(self, "dataset_hashes", tuple(self.dataset_hashes))
        object.__setattr__(self, "challenger_results", tuple(self.challenger_results))
        object.__setattr__(self, "known_contradictions", tuple(self.known_contradictions))


@dataclass(frozen=True, slots=True)
class RuntimeParityComparisonRecordV1:
    """One generic cross-runtime parity artifact (python | matlab | pinets, etc.)."""

    comparison_id: str
    schema_version: str
    strategy_id: str
    reference_runtime_id: str
    candidate_runtime_id: str
    reference_source_hash: str
    candidate_source_hash: str
    disposition: RuntimeParityDisposition
    metric_comparisons: tuple[dict[str, Any], ...] = ()
    notes: str = ""
    implementation_version: str = STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.comparison_id or not self.strategy_id:
            raise ValueError("PARITY_COMPARISON_IDENTITY_REQUIRED")
        if not self.reference_runtime_id or not self.candidate_runtime_id:
            raise ValueError("PARITY_RUNTIME_IDENTITY_REQUIRED")
        object.__setattr__(self, "metric_comparisons", tuple(self.metric_comparisons))


@dataclass(frozen=True, slots=True)
class StrategyResearchPromotionRecordV1:
    """Governed research promotion row — review eligibility only, never execution authority."""

    promotion_record_id: str
    schema_version: str
    strategy_id: str
    lifecycle_state: StrategyResearchPromotionLifecycleState
    evidence: StrategyResearchEvidenceBundleV1
    parity_records: tuple[RuntimeParityComparisonRecordV1, ...] = ()
    reason_codes: tuple[ResearchPromotionReasonCode, ...] = ()
    review_eligible: bool = False
    grants_execution_authority: bool = False
    updated_at_ns: int = 0
    implementation_version: str = STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.promotion_record_id or not self.strategy_id:
            raise ValueError("PROMOTION_RECORD_IDENTITY_REQUIRED")
        if self.grants_execution_authority:
            raise ValueError("RESEARCH_PROMOTION_CANNOT_GRANT_EXECUTION_AUTHORITY")
        object.__setattr__(self, "parity_records", tuple(self.parity_records))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class StrategyResearchPromotionTransitionV1:
    event_id: str
    schema_version: str
    promotion_record_id: str
    from_state: StrategyResearchPromotionLifecycleState | None
    to_state: StrategyResearchPromotionLifecycleState
    effective_at_ns: int
    reason_codes: tuple[ResearchPromotionReasonCode, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "RESEARCH_PROMOTION_RECORD_PREFIX",
    "ResearchPromotionReasonCode",
    "ResearchResultSummaryV1",
    "RuntimeParityComparisonRecordV1",
    "RuntimeParityDisposition",
    "STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION",
    "STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY",
    "StrategyResearchEvidenceBundleV1",
    "StrategyResearchPromotionLifecycleState",
    "StrategyResearchPromotionRecordV1",
    "StrategyResearchPromotionTransitionV1",
]
