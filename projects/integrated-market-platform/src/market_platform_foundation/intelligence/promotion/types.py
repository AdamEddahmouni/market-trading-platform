"""Champion-challenger promotion governance contracts (BUILD 20)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import ComplexityBudget, EvidenceTier
from ..validation.types import ContaminationDisposition, KnowledgeAssessmentStatus, ValidationDisposition

PROMOTION_IMPLEMENTATION_VERSION = "champion-challenger-promotion-v1"


class MetricDirection(StrEnum):
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"


class PromotionDecisionKind(StrEnum):
    PROMOTE = "PROMOTE"
    RETAIN_CHAMPION = "RETAIN_CHAMPION"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


class PromotionReasonCode(StrEnum):
    PROMOTION_CRITERIA_MET = "PROMOTION_CRITERIA_MET"
    VALIDATION_NOT_ELIGIBLE = "VALIDATION_NOT_ELIGIBLE"
    CONTAMINATION_NOT_CLEAN = "CONTAMINATION_NOT_CLEAN"
    TEMPORAL_KNOWLEDGE_NOT_CLEAN = "TEMPORAL_KNOWLEDGE_NOT_CLEAN"
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    INSUFFICIENT_HOLDOUT_SAMPLE = "INSUFFICIENT_HOLDOUT_SAMPLE"
    INSUFFICIENT_SHADOW_SAMPLE = "INSUFFICIENT_SHADOW_SAMPLE"
    INSUFFICIENT_SHADOW_DURATION = "INSUFFICIENT_SHADOW_DURATION"
    PRIMARY_METRIC_FAILED = "PRIMARY_METRIC_FAILED"
    STATISTICAL_REQUIREMENT_FAILED = "STATISTICAL_REQUIREMENT_FAILED"
    GUARDRAIL_FAILED = "GUARDRAIL_FAILED"
    COMPLEXITY_NOT_JUSTIFIED = "COMPLEXITY_NOT_JUSTIFIED"
    CHAMPION_CHANGED = "CHAMPION_CHANGED"
    PLAN_DEVIATION = "PLAN_DEVIATION"
    SHADOW_EVIDENCE_MODE_INVALID = "SHADOW_EVIDENCE_MODE_INVALID"
    SETTLEMENT_INCOMPLETE = "SETTLEMENT_INCOMPLETE"
    CHALLENGER_STALE = "CHALLENGER_STALE"
    BOOTSTRAP_CRITERIA_MET = "BOOTSTRAP_CRITERIA_MET"
    MISSING_REQUIRED_GUARDRAIL = "MISSING_REQUIRED_GUARDRAIL"
    SCOPE_INCOMPATIBLE = "SCOPE_INCOMPATIBLE"


class ChallengerLifecycleState(StrEnum):
    REGISTERED = "REGISTERED"
    SHADOW_PENDING = "SHADOW_PENDING"
    SHADOW_ACTIVE = "SHADOW_ACTIVE"
    SHADOW_COMPLETE = "SHADOW_COMPLETE"
    PROMOTION_EVALUATED = "PROMOTION_EVALUATED"
    PROMOTED = "PROMOTED"
    RETAINED_AS_CHALLENGER = "RETAINED_AS_CHALLENGER"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"


class ChampionAssignmentReason(StrEnum):
    BOOTSTRAP = "BOOTSTRAP"
    PROMOTION = "PROMOTION"


class ChampionAssignmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class EligibilityDisposition(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class StatisticalRequirementKind(StrEnum):
    HOLDOUT_PAIRED_CI_IMPROVEMENT = "HOLDOUT_PAIRED_CI_IMPROVEMENT"
    SHADOW_PAIRED_CI_IMPROVEMENT = "SHADOW_PAIRED_CI_IMPROVEMENT"
    NONE = "NONE"


class ComplexityPolicyKind(StrEnum):
    SAME_MARGIN = "SAME_MARGIN"
    TIERED_MARGIN = "TIERED_MARGIN"


@dataclass(frozen=True, slots=True)
class ChampionScopeV1:
    """Scoped champion identity — not a global platform winner."""

    component: str
    target_kind: str
    horizon_ns: int
    mode: str
    scenario_id: str | None = None

    def __post_init__(self) -> None:
        if not self.component or not self.target_kind or not self.mode:
            raise ValueError("CHAMPION_SCOPE_INCOMPLETE")
        if self.horizon_ns <= 0:
            raise ValueError("HORIZON_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class GuardrailRule:
    metric_name: str
    direction: MetricDirection
    max_regression: float | None = None
    max_absolute: float | None = None

    def __post_init__(self) -> None:
        if not self.metric_name:
            raise ValueError("GUARDRAIL_METRIC_REQUIRED")


@dataclass(frozen=True, slots=True)
class ComplexityPolicy:
    kind: ComplexityPolicyKind
    base_required_improvement: float
    minor_complexity_additional_margin: float = 0.0
    major_complexity_additional_margin: float = 0.0

    def __post_init__(self) -> None:
        if self.base_required_improvement < 0:
            raise ValueError("REQUIRED_IMPROVEMENT_INVALID")


@dataclass(frozen=True, slots=True)
class PromotionPolicyV1:
    promotion_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    required_validation_dispositions: tuple[ValidationDisposition, ...]
    require_clean_contamination: bool
    require_temporal_knowledge_pass: bool
    require_artifact_integrity: bool
    primary_metric: str
    primary_metric_direction: MetricDirection
    required_improvement: float
    secondary_metrics: tuple[str, ...]
    guardrails: tuple[GuardrailRule, ...]
    minimum_walk_forward_folds: int
    minimum_holdout_samples: int
    minimum_shadow_samples: int
    minimum_shadow_duration_ns: int
    require_locked_holdout: bool
    require_shadow_evidence: bool
    require_forward_shadow_evidence: bool
    allowed_shadow_evidence_tiers: tuple[EvidenceTier, ...]
    statistical_requirement: StatisticalRequirementKind
    complexity_policy: ComplexityPolicy
    allowed_validation_modes: tuple[str, ...]
    implementation_version: str = PROMOTION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.promotion_policy_id:
            raise ValueError("PROMOTION_POLICY_ID_REQUIRED")
        if self.minimum_holdout_samples < 0 or self.minimum_shadow_samples < 0:
            raise ValueError("MINIMUM_SAMPLE_INVALID")
        if self.minimum_shadow_duration_ns < 0:
            raise ValueError("MINIMUM_SHADOW_DURATION_INVALID")


@dataclass(frozen=True, slots=True)
class PromotionEligibilityAssessmentV1:
    assessment_id: str
    schema_version: str
    promotion_policy_id: str
    champion_scope: ChampionScopeV1
    candidate_id: str
    candidate_artifact_hash: str
    validation_report_id: str
    experiment_id: str
    disposition: EligibilityDisposition
    reason_codes: tuple[PromotionReasonCode, ...]
    validation_disposition: ValidationDisposition | None = None
    contamination_disposition: ContaminationDisposition | None = None
    knowledge_assessment_status: KnowledgeAssessmentStatus | None = None
    artifact_integrity_ok: bool = False
    implementation_version: str = PROMOTION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChallengerRegistrationV1:
    challenger_registration_id: str
    schema_version: str
    candidate_id: str
    candidate_artifact_hash: str
    champion_scope: ChampionScopeV1
    current_champion_assignment_id: str
    validation_report_id: str
    promotion_policy_id: str
    eligibility_assessment_id: str
    registered_at_ns: int
    minimum_shadow_samples: int
    minimum_shadow_duration_ns: int
    shadow_window_start_ns: int | None = None
    shadow_window_end_ns: int | None = None
    lifecycle_state: ChallengerLifecycleState = ChallengerLifecycleState.REGISTERED
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.challenger_registration_id:
            raise ValueError("CHALLENGER_REGISTRATION_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class ShadowMatchedObservation:
    opportunity_key: str
    decision_time_ns: int
    champion_forecast_id: str
    challenger_forecast_id: str
    outcome_id: str | None
    settled: bool
    champion_probability: float
    challenger_probability: float
    binary_label: int | None


@dataclass(frozen=True, slots=True)
class ShadowEvidenceManifestV1:
    shadow_evidence_id: str
    schema_version: str
    challenger_registration_id: str
    champion_assignment_id: str
    promotion_policy_id: str
    evidence_tier: EvidenceTier
    decision_start_ns: int
    decision_end_ns: int
    matched_observations: tuple[ShadowMatchedObservation, ...]
    unmatched_champion_count: int
    unmatched_challenger_count: int
    sample_count: int
    duration_ns: int
    settlement_complete: bool
    evaluation_report_ids: tuple[str, ...] = ()
    implementation_version: str = PROMOTION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetricGateResult:
    metric_name: str
    direction: MetricDirection
    champion_value: float | None
    challenger_value: float | None
    delta: float | None
    required_improvement: float
    passed: bool


@dataclass(frozen=True, slots=True)
class GuardrailGateResult:
    rule: GuardrailRule
    champion_value: float | None
    challenger_value: float | None
    passed: bool | None


@dataclass(frozen=True, slots=True)
class StatisticalGateResult:
    requirement: StatisticalRequirementKind
    sample_count: int
    mean_delta: float | None
    ci_lower: float | None
    ci_upper: float | None
    passed: bool | None


@dataclass(frozen=True, slots=True)
class ComplexityGateResult:
    champion_complexity: ComplexityBudget
    challenger_complexity: ComplexityBudget
    required_improvement: float
    actual_improvement: float | None
    passed: bool | None


@dataclass(frozen=True, slots=True)
class PromotionDecisionV1:
    promotion_decision_id: str
    schema_version: str
    promotion_policy_id: str
    champion_scope: ChampionScopeV1
    current_champion_assignment_id: str
    challenger_registration_id: str
    candidate_id: str
    candidate_artifact_hash: str
    validation_report_ids: tuple[str, ...]
    shadow_evidence_id: str | None
    artifact_integrity_status: bool
    contamination_status: ContaminationDisposition
    knowledge_status: KnowledgeAssessmentStatus
    primary_metric_result: MetricGateResult | None
    guardrail_results: tuple[GuardrailGateResult, ...]
    statistical_result: StatisticalGateResult | None
    complexity_result: ComplexityGateResult | None
    decision: PromotionDecisionKind
    reason_codes: tuple[PromotionReasonCode, ...]
    implementation_version: str = PROMOTION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChampionAssignmentV1:
    assignment_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    candidate_id: str
    candidate_artifact_hash: str
    promotion_decision_id: str | None
    previous_assignment_id: str | None
    effective_from_ns: int
    assignment_reason: ChampionAssignmentReason
    status: ChampionAssignmentStatus = ChampionAssignmentStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.assignment_id:
            raise ValueError("CHAMPION_ASSIGNMENT_ID_REQUIRED")
        if self.assignment_reason == ChampionAssignmentReason.PROMOTION and not self.promotion_decision_id:
            raise ValueError("PROMOTION_DECISION_REF_REQUIRED")


@dataclass(frozen=True, slots=True)
class ChallengerLifecycleEventV1:
    event_id: str
    schema_version: str
    challenger_registration_id: str
    from_state: ChallengerLifecycleState | None
    to_state: ChallengerLifecycleState
    effective_at_ns: int
    reason_code: PromotionReasonCode | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "PROMOTION_IMPLEMENTATION_VERSION",
    "ChallengerLifecycleEventV1",
    "ChallengerLifecycleState",
    "ChallengerRegistrationV1",
    "ChampionAssignmentReason",
    "ChampionAssignmentStatus",
    "ChampionAssignmentV1",
    "ChampionScopeV1",
    "ComplexityGateResult",
    "ComplexityPolicy",
    "ComplexityPolicyKind",
    "EligibilityDisposition",
    "GuardrailGateResult",
    "GuardrailRule",
    "MetricDirection",
    "MetricGateResult",
    "PromotionDecisionKind",
    "PromotionDecisionV1",
    "PromotionEligibilityAssessmentV1",
    "PromotionPolicyV1",
    "PromotionReasonCode",
    "ShadowEvidenceManifestV1",
    "ShadowMatchedObservation",
    "StatisticalGateResult",
    "StatisticalRequirementKind",
]
