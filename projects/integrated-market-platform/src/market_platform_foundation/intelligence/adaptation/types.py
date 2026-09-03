"""Controlled adaptation and governed research re-entry contracts (BUILD 24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..governance.types import (
    DriftSeverity,
    DriftType,
    GovernanceReasonCode,
    MonitoringWindowV1,
)
from ..promotion.types import ChampionScopeV1

ADAPTATION_IMPLEMENTATION_VERSION = "controlled-adaptation-v1"


class AdaptationEvidenceType(StrEnum):
    DRIFT_ASSESSMENT = "DRIFT_ASSESSMENT"
    GOVERNANCE_ALERT = "GOVERNANCE_ALERT"
    FAIL_SAFE_DECISION = "FAIL_SAFE_DECISION"
    ROLLBACK_DECISION = "ROLLBACK_DECISION"
    PROVIDER_HEALTH = "PROVIDER_HEALTH"
    INTELLIGENCE_HEALTH = "INTELLIGENCE_HEALTH"
    EXECUTION_HEALTH = "EXECUTION_HEALTH"
    OPPORTUNITY_HEALTH = "OPPORTUNITY_HEALTH"


class AdaptationEvidenceClass(StrEnum):
    STATISTICAL_EVIDENCE = "STATISTICAL_EVIDENCE"
    STRUCTURAL_INTEGRITY_EVIDENCE = "STRUCTURAL_INTEGRITY_EVIDENCE"


class AdaptationAction(StrEnum):
    IGNORE = "IGNORE"
    ACCUMULATE = "ACCUMULATE"
    TRIGGER_RESEARCH = "TRIGGER_RESEARCH"
    SUPPRESS_DUPLICATE = "SUPPRESS_DUPLICATE"
    SUPPRESS_COOLDOWN = "SUPPRESS_COOLDOWN"
    SUPPRESS_EXISTING_RESEARCH = "SUPPRESS_EXISTING_RESEARCH"
    FAIL_CLOSED = "FAIL_CLOSED"


class AdaptationReasonCode(StrEnum):
    EVIDENCE_BELOW_SEVERITY = "EVIDENCE_BELOW_SEVERITY"
    EVIDENCE_TYPE_INELIGIBLE = "EVIDENCE_TYPE_INELIGIBLE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INSUFFICIENT_RECURRENCE = "INSUFFICIENT_RECURRENCE"
    INSUFFICIENT_DISTINCT_WINDOWS = "INSUFFICIENT_DISTINCT_WINDOWS"
    RECURRENCE_THRESHOLD_MET = "RECURRENCE_THRESHOLD_MET"
    STRUCTURAL_INTEGRITY_TRIGGER = "STRUCTURAL_INTEGRITY_TRIGGER"
    ROLLBACK_EVIDENCE = "ROLLBACK_EVIDENCE"
    BATCH_ACCUMULATING = "BATCH_ACCUMULATING"
    EXACT_DUPLICATE_SUPPRESSED = "EXACT_DUPLICATE_SUPPRESSED"
    SEMANTIC_DUPLICATE_SUPPRESSED = "SEMANTIC_DUPLICATE_SUPPRESSED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    OPEN_RESEARCH_EXISTS = "OPEN_RESEARCH_EXISTS"
    RUNTIME_DISABLED_SUPPRESSED = "RUNTIME_DISABLED_SUPPRESSED"
    ADAPTATION_ARTIFACT_EXCLUDED = "ADAPTATION_ARTIFACT_EXCLUDED"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"
    HEALTHY_NO_ACTION = "HEALTHY_NO_ACTION"
    RESEARCH_TRIGGER_ISSUED = "RESEARCH_TRIGGER_ISSUED"
    COOLDOWN_BYPASS_SEVERITY = "COOLDOWN_BYPASS_SEVERITY"
    CONSUMED_EVIDENCE = "CONSUMED_EVIDENCE"


class SuggestedResearchClass(StrEnum):
    CALIBRATION = "CALIBRATION"
    FEATURES = "FEATURES"
    MODEL = "MODEL"
    DATA_SOURCE = "DATA_SOURCE"
    QUALITY_POLICY = "QUALITY_POLICY"
    ROUTING = "ROUTING"
    FUSION = "FUSION"
    SPECIALIST = "SPECIALIST"
    EXECUTION_POLICY = "EXECUTION_POLICY"
    OPPORTUNITY_POLICY = "OPPORTUNITY_POLICY"


class ResearchPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AdaptationEventType(StrEnum):
    EVIDENCE_ACCUMULATING = "EVIDENCE_ACCUMULATING"
    TRIGGERED = "TRIGGERED"
    TRIGGER_CONSUMED_BY_FINDING = "TRIGGER_CONSUMED_BY_FINDING"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    COOLDOWN_SUPPRESSED = "COOLDOWN_SUPPRESSED"
    CLOSED_NO_CHANGE = "CLOSED_NO_CHANGE"


@dataclass(frozen=True, slots=True)
class AdaptationPolicyV1:
    adaptation_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    eligible_evidence_types: tuple[AdaptationEvidenceType, ...] = (
        AdaptationEvidenceType.DRIFT_ASSESSMENT,
        AdaptationEvidenceType.GOVERNANCE_ALERT,
        AdaptationEvidenceType.FAIL_SAFE_DECISION,
        AdaptationEvidenceType.ROLLBACK_DECISION,
        AdaptationEvidenceType.PROVIDER_HEALTH,
        AdaptationEvidenceType.INTELLIGENCE_HEALTH,
        AdaptationEvidenceType.EXECUTION_HEALTH,
    )
    eligible_drift_types: tuple[DriftType, ...] = tuple(DriftType)
    minimum_severity: DriftSeverity = DriftSeverity.WARNING
    minimum_sample: int = 10
    minimum_recurrence_count: int = 2
    minimum_distinct_windows: int = 2
    batch_window_ns: int = 3_600_000_000_000
    cooldown_ns: int = 86_400_000_000_000
    deduplication_policy: str = "SEMANTIC_ISSUE_KEY"
    scope_merge_policy: str = "PRESERVE_DISTINCT_ISSUES"
    critical_integrity_trigger_policy: str = "IMMEDIATE_ON_STRUCTURAL"
    allowed_research_classes: tuple[SuggestedResearchClass, ...] = tuple(SuggestedResearchClass)
    priority_policy: str = "SEVERITY_RECURRENCE_TABLE"
    suppress_when_runtime_disabled: bool = True
    suppress_when_existing_open_research: bool = True
    suppress_when_same_evidence_consumed: bool = True
    allow_cooldown_bypass_for_structural: bool = True
    allow_cooldown_bypass_severity: DriftSeverity = DriftSeverity.CRITICAL
    implementation_version: str = ADAPTATION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.minimum_sample < 0:
            raise ValueError("MINIMUM_SAMPLE_INVALID")
        if self.minimum_recurrence_count < 1:
            raise ValueError("MINIMUM_RECURRENCE_INVALID")
        if self.minimum_distinct_windows < 1:
            raise ValueError("MINIMUM_DISTINCT_WINDOWS_INVALID")
        if self.batch_window_ns <= 0:
            raise ValueError("BATCH_WINDOW_INVALID")
        if self.cooldown_ns < 0:
            raise ValueError("COOLDOWN_INVALID")
        if not self.eligible_evidence_types:
            raise ValueError("ELIGIBLE_EVIDENCE_TYPES_REQUIRED")


@dataclass(frozen=True, slots=True)
class AdaptationAssessmentV1:
    adaptation_assessment_id: str
    schema_version: str
    policy_ref: str
    champion_scope: ChampionScopeV1
    evidence_refs: tuple[ContractReference, ...]
    evidence_window: MonitoringWindowV1
    evidence_class: AdaptationEvidenceClass
    severity: DriftSeverity
    sample_count: int
    recurrence_count: int
    distinct_window_count: int
    action: AdaptationAction
    reason_codes: tuple[AdaptationReasonCode, ...]
    cooldown_state: str | None = None
    dedup_state: str | None = None
    open_research_state: str | None = None
    research_trigger_ref: str | None = None
    dedup_key: str | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adaptation_assessment_id or not self.policy_ref:
            raise ValueError("ASSESSMENT_FIELDS_INCOMPLETE")
        if not self.evidence_refs:
            raise ValueError("EVIDENCE_REFS_REQUIRED")
        if self.sample_count < 0:
            raise ValueError("SAMPLE_COUNT_INVALID")


@dataclass(frozen=True, slots=True)
class ResearchTriggerV1:
    """Governed observation routing artifact — not hypothesis, experiment, or training authorization."""

    research_trigger_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    evidence_window: MonitoringWindowV1
    adaptation_policy_ref: str
    adaptation_assessment_ref: str
    source_evidence_refs: tuple[ContractReference, ...]
    evidence_types: tuple[AdaptationEvidenceType, ...]
    severity: DriftSeverity
    champion_assignment_ref: str | None = None
    runtime_activation_ref: str | None = None
    observed_metric_summary: dict[str, float] = field(default_factory=dict)
    sample_counts: dict[str, int] = field(default_factory=dict)
    suggested_research_class: SuggestedResearchClass = SuggestedResearchClass.MODEL
    priority: ResearchPriority = ResearchPriority.NORMAL
    dedup_key: str = ""
    limitations: tuple[str, ...] = ()
    observation_summary: str = ""
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.research_trigger_id:
            raise ValueError("RESEARCH_TRIGGER_ID_REQUIRED")
        if not self.source_evidence_refs:
            raise ValueError("SOURCE_EVIDENCE_REQUIRED")
        if not self.observation_summary:
            raise ValueError("OBSERVATION_SUMMARY_REQUIRED")
        if not self.dedup_key:
            raise ValueError("DEDUP_KEY_REQUIRED")

    @property
    def trigger_id(self) -> str:
        return self.research_trigger_id


@dataclass(frozen=True, slots=True)
class AdaptationCampaignV1:
    """Append-only lineage container linking trigger to downstream research artifacts."""

    adaptation_campaign_id: str
    schema_version: str
    research_trigger_id: str
    research_finding_id: str | None = None
    research_hypothesis_id: str | None = None
    experiment_id: str | None = None
    candidate_id: str | None = None
    validation_report_id: str | None = None
    promotion_decision_id: str | None = None
    runtime_activation_id: str | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdaptationEventV1:
    event_id: str
    schema_version: str
    event_type: AdaptationEventType
    champion_scope: ChampionScopeV1
    effective_at_ns: int
    source_refs: tuple[ContractReference, ...] = ()
    reason_codes: tuple[AdaptationReasonCode, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdaptationAssessmentResult:
    assessment: AdaptationAssessmentV1
    trigger: ResearchTriggerV1 | None = None


__all__ = [
    "ADAPTATION_IMPLEMENTATION_VERSION",
    "AdaptationAction",
    "AdaptationAssessmentResult",
    "AdaptationAssessmentV1",
    "AdaptationCampaignV1",
    "AdaptationEventType",
    "AdaptationEventV1",
    "AdaptationEvidenceClass",
    "AdaptationEvidenceType",
    "AdaptationPolicyV1",
    "AdaptationReasonCode",
    "ResearchPriority",
    "ResearchTriggerV1",
    "SuggestedResearchClass",
]
