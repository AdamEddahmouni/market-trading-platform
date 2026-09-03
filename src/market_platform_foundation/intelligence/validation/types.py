"""Independent validation contracts (BUILD 19)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

VALIDATION_IMPLEMENTATION_VERSION = "independent-validation-temporal-firewall-v1"


class WalkForwardMode(StrEnum):
    EXPANDING = "EXPANDING"
    ROLLING = "ROLLING"


class ValidationDisposition(StrEnum):
    MEETS_PRE_REGISTERED_CRITERIA = "MEETS_PRE_REGISTERED_CRITERIA"
    DOES_NOT_MEET_PRE_REGISTERED_CRITERIA = "DOES_NOT_MEET_PRE_REGISTERED_CRITERIA"
    INCONCLUSIVE = "INCONCLUSIVE"
    INCONCLUSIVE_INSUFFICIENT_SAMPLE = "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    INVALID_CONTAMINATED = "INVALID_CONTAMINATED"
    INVALID_TEMPORAL_LEAKAGE = "INVALID_TEMPORAL_LEAKAGE"
    INVALID_KNOWLEDGE_FIREWALL = "INVALID_KNOWLEDGE_FIREWALL"
    INVALID_PLAN_DEVIATION = "INVALID_PLAN_DEVIATION"
    INVALID_CANDIDATE_ARTIFACT_HASH = "INVALID_CANDIDATE_ARTIFACT_HASH"
    MISSING_FOLD_CANDIDATE = "MISSING_FOLD_CANDIDATE"


class ContaminationType(StrEnum):
    DEVELOPMENT_EVALUATION_OVERLAP = "DEVELOPMENT_EVALUATION_OVERLAP"
    TRAINING_DATA_OVERLAP = "TRAINING_DATA_OVERLAP"
    PRIOR_HOLDOUT_ACCESS = "PRIOR_HOLDOUT_ACCESS"
    METRIC_TUNING_ON_HOLDOUT = "METRIC_TUNING_ON_HOLDOUT"
    HYPERPARAMETER_TUNING_ON_HOLDOUT = "HYPERPARAMETER_TUNING_ON_HOLDOUT"
    MANUAL_HOLDOUT_INSPECTION = "MANUAL_HOLDOUT_INSPECTION"
    TEACHER_KNOWLEDGE_LEAKAGE = "TEACHER_KNOWLEDGE_LEAKAGE"
    MODEL_KNOWLEDGE_CUTOFF_VIOLATION = "MODEL_KNOWLEDGE_CUTOFF_VIOLATION"
    FUTURE_RETRIEVAL_SOURCE = "FUTURE_RETRIEVAL_SOURCE"
    FUTURE_TOOL_RESULT = "FUTURE_TOOL_RESULT"
    FUTURE_LABEL_ACCESS = "FUTURE_LABEL_ACCESS"
    UNKNOWN_MODEL_KNOWLEDGE = "UNKNOWN_MODEL_KNOWLEDGE"
    VALIDATION_PLAN_CHANGED_AFTER_UNLOCK = "VALIDATION_PLAN_CHANGED_AFTER_UNLOCK"


class ContaminationDisposition(StrEnum):
    CLEAN = "CLEAN"
    CONTAMINATED = "CONTAMINATED"
    UNKNOWN = "UNKNOWN"


class KnowledgeCutoffState(StrEnum):
    DECLARED_BOUNDED = "DECLARED_BOUNDED"
    UNKNOWN = "UNKNOWN"
    UNBOUNDED = "UNBOUNDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"


class KnowledgeAssessmentStatus(StrEnum):
    PASS = "PASS"
    FAIL_KNOWLEDGE_CUTOFF = "FAIL_KNOWLEDGE_CUTOFF"
    FAIL_RETRIEVAL_TIME = "FAIL_RETRIEVAL_TIME"
    FAIL_TOOL_POLICY = "FAIL_TOOL_POLICY"
    FAIL_TEACHER_PROVENANCE = "FAIL_TEACHER_PROVENANCE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF = "BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF"


class ToolPolicyClass(StrEnum):
    PIT_SAFE = "PIT_SAFE"
    CURRENT_ONLY = "CURRENT_ONLY"
    UNSAFE_UNBOUNDED = "UNSAFE_UNBOUNDED"


class NetworkPolicy(StrEnum):
    DENIED = "DENIED"
    PIT_ADAPTERS_ONLY = "PIT_ADAPTERS_ONLY"


@dataclass(frozen=True, slots=True)
class ValidationFoldSpec:
    fold_id: str
    validation_start_ns: int
    validation_end_ns: int
    training_cutoff_ns: int
    candidate_id: str | None = None

    def __post_init__(self) -> None:
        if self.validation_start_ns >= self.validation_end_ns:
            raise ValueError("FOLD_VALIDATION_RANGE_INVALID")


@dataclass(frozen=True, slots=True)
class WalkForwardSpec:
    mode: WalkForwardMode
    fold_boundaries_ns: tuple[int, ...]
    fold_candidate_ids: tuple[str | None, ...] = ()

    def __post_init__(self) -> None:
        if len(self.fold_boundaries_ns) < 2:
            raise ValueError("FOLD_BOUNDARIES_INSUFFICIENT")
        if self.fold_candidate_ids and len(self.fold_candidate_ids) != len(self.fold_boundaries_ns) - 1:
            raise ValueError("FOLD_CANDIDATE_COUNT_MISMATCH")


@dataclass(frozen=True, slots=True)
class HoldoutSpec:
    holdout_start_ns: int
    holdout_end_ns: int
    selector_ref: str | None = None

    def __post_init__(self) -> None:
        if self.holdout_start_ns >= self.holdout_end_ns:
            raise ValueError("HOLDOUT_RANGE_INVALID")


@dataclass(frozen=True, slots=True)
class StatisticalPlan:
    block_length: int
    replicate_count: int
    seed: int
    confidence_level: float
    minimum_paired_sample: int
    criterion_upper_ci_bound_lt_zero: bool = False

    def __post_init__(self) -> None:
        if self.block_length < 1:
            raise ValueError("BLOCK_LENGTH_INVALID")
        if self.replicate_count < 1:
            raise ValueError("REPLICATE_COUNT_INVALID")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("CONFIDENCE_LEVEL_INVALID")
        if self.minimum_paired_sample < 1:
            raise ValueError("MINIMUM_PAIRED_SAMPLE_INVALID")


@dataclass(frozen=True, slots=True)
class TemporalKnowledgePolicyV1:
    policy_id: str
    schema_version: str
    network_policy: NetworkPolicy = NetworkPolicy.DENIED
    require_declared_model_cutoff: bool = True
    reject_prompt_only_time_travel: bool = True
    allow_synthetic_test_teachers: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("POLICY_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class KnowledgeProfileV1:
    component_id: str
    component_kind: str
    is_llm: bool
    knowledge_cutoff_state: KnowledgeCutoffState
    model_knowledge_cutoff_ns: int | None = None
    finetune_cutoff_ns: int | None = None
    teacher_id: str | None = None
    teacher_knowledge_cutoff_ns: int | None = None
    teacher_knowledge_cutoff_state: KnowledgeCutoffState | None = None
    retrieval_policy_ref: str | None = None
    tool_policy_classes: tuple[ToolPolicyClass, ...] = ()
    network_policy: NetworkPolicy = NetworkPolicy.DENIED
    declared_source_restrictions: tuple[str, ...] = ()
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("COMPONENT_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class TemporalKnowledgeAssessment:
    assessment_id: str
    policy_id: str
    profile_id: str
    decision_time_ns: int
    status: KnowledgeAssessmentStatus
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationPlanV1:
    validation_plan_id: str
    schema_version: str
    experiment_id: str
    candidate_ids: tuple[str, ...]
    candidate_artifact_hashes: tuple[str, ...]
    control_ref: str
    target_kind: str
    horizon_ns: int
    mode: str
    validation_method: str
    walk_forward_spec: WalkForwardSpec | None
    purge_ns: int
    embargo_ns: int
    holdout_spec: HoldoutSpec
    primary_metric: str
    guardrail_metrics: tuple[str, ...]
    statistical_plan: StatisticalPlan
    temporal_knowledge_policy: TemporalKnowledgePolicyV1
    minimum_paired_sample: int
    scenario_id: str | None = None
    implementation_version: str = VALIDATION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validation_plan_id or not self.experiment_id:
            raise ValueError("VALIDATION_PLAN_FIELDS_INCOMPLETE")
        if len(self.candidate_ids) != len(self.candidate_artifact_hashes):
            raise ValueError("CANDIDATE_HASH_COUNT_MISMATCH")
        if not self.candidate_ids:
            raise ValueError("CANDIDATE_SET_REQUIRED")
        if self.purge_ns < 0:
            raise ValueError("PURGE_NS_INVALID")
        if self.embargo_ns < 0:
            raise ValueError("EMBARGO_NS_INVALID")


@dataclass(frozen=True, slots=True)
class HoldoutCommitmentV1:
    holdout_commitment_id: str
    schema_version: str
    validation_plan_id: str
    experiment_id: str
    candidate_ids: tuple[str, ...]
    candidate_artifact_hashes: tuple[str, ...]
    control_ref: str
    holdout_spec: HoldoutSpec
    primary_metric: str
    guardrail_metrics: tuple[str, ...]
    statistical_plan: StatisticalPlan
    temporal_knowledge_policy_id: str
    implementation_version: str = VALIDATION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.holdout_commitment_id:
            raise ValueError("HOLDOUT_COMMITMENT_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class HoldoutUnlockReceiptV1:
    receipt_id: str
    schema_version: str
    holdout_commitment_id: str
    validation_plan_id: str
    candidate_ids: tuple[str, ...]
    unlocked_at_ns: int
    context: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContaminationRecordV1:
    contamination_record_id: str
    schema_version: str
    experiment_id: str
    validation_plan_id: str
    holdout_commitment_id: str | None
    contamination_type: ContaminationType
    disposition: ContaminationDisposition
    source_ref: str | None = None
    affected_decision_start_ns: int | None = None
    affected_decision_end_ns: int | None = None
    affected_artifact_refs: tuple[str, ...] = ()
    detected_context: str = ""
    severity: str = "HIGH"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationDatasetManifestV1:
    validation_dataset_id: str
    schema_version: str
    validation_plan_id: str
    fold_or_holdout_ref: str
    decision_start_ns: int
    decision_end_ns: int
    forecast_ids: tuple[str, ...]
    outcome_ids: tuple[str, ...]
    dataset_fingerprint: str
    target_kind: str
    horizon_ns: int
    mode: str
    scenario_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PairedMetricDelta:
    metric_name: str
    mean_delta: float
    sample_count: int
    ci_lower: float | None = None
    ci_upper: float | None = None
    block_length: int | None = None
    replicate_count: int | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class FoldMetricResult:
    fold_id: str
    candidate_id: str
    control_ref: str
    matched_count: int
    candidate_primary_metric: float | None
    control_primary_metric: float | None
    primary_delta: float | None
    guardrail_results: dict[str, bool | None]
    knowledge_assessment_status: KnowledgeAssessmentStatus
    contamination_disposition: ContaminationDisposition
    disposition: ValidationDisposition


@dataclass(frozen=True, slots=True)
class HoldoutMetricResult:
    candidate_id: str
    control_ref: str
    matched_count: int
    candidate_metrics: dict[str, float | None]
    control_metrics: dict[str, float | None]
    primary_delta: float | None
    paired_delta: PairedMetricDelta | None
    guardrail_results: dict[str, bool | None]
    knowledge_assessment_status: KnowledgeAssessmentStatus
    contamination_disposition: ContaminationDisposition
    disposition: ValidationDisposition
    coverage_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationReportV1:
    validation_report_id: str
    schema_version: str
    validation_plan_id: str
    experiment_id: str
    candidate_ids: tuple[str, ...]
    candidate_artifact_hashes: tuple[str, ...]
    control_ref: str
    holdout_commitment_id: str
    fold_results: tuple[FoldMetricResult, ...]
    holdout_results: tuple[HoldoutMetricResult, ...]
    contamination_disposition: ContaminationDisposition
    contamination_record_ids: tuple[str, ...]
    knowledge_assessment_status: KnowledgeAssessmentStatus
    candidate_family_size: int
    final_disposition: ValidationDisposition
    limitations: tuple[str, ...] = ()
    implementation_version: str = VALIDATION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationExample:
    """Internal validation row for metric computation."""

    example_id: str
    snapshot_id: str
    decision_time_ns: int
    label_available_time_ns: int
    binary_label: int
    candidate_probability: float
    control_probability: float
    outcome_id: str | None = None
    forecast_id: str | None = None


__all__ = [
    "VALIDATION_IMPLEMENTATION_VERSION",
    "ContaminationDisposition",
    "ContaminationRecordV1",
    "ContaminationType",
    "FoldMetricResult",
    "HoldoutCommitmentV1",
    "HoldoutMetricResult",
    "HoldoutSpec",
    "HoldoutUnlockReceiptV1",
    "KnowledgeAssessmentStatus",
    "KnowledgeCutoffState",
    "KnowledgeProfileV1",
    "NetworkPolicy",
    "PairedMetricDelta",
    "StatisticalPlan",
    "TemporalKnowledgeAssessment",
    "TemporalKnowledgePolicyV1",
    "ToolPolicyClass",
    "ValidationDatasetManifestV1",
    "ValidationDisposition",
    "ValidationExample",
    "ValidationFoldSpec",
    "ValidationPlanV1",
    "ValidationReportV1",
    "WalkForwardMode",
    "WalkForwardSpec",
]
