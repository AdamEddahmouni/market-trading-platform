"""Research finding, hypothesis, and experiment types (BUILD 17)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

RESEARCH_IMPLEMENTATION_VERSION = "research-experiment-system-v1"


class ResearchFindingType(StrEnum):
    ERROR_CONCENTRATION = "ERROR_CONCENTRATION"
    CONTROL_UNDERPERFORMANCE = "CONTROL_UNDERPERFORMANCE"
    CONTROL_OUTPERFORMANCE = "CONTROL_OUTPERFORMANCE"
    CALIBRATION_GAP = "CALIBRATION_GAP"
    QUALITY_SENSITIVITY = "QUALITY_SENSITIVITY"
    HORIZON_SENSITIVITY = "HORIZON_SENSITIVITY"
    OOD_SENSITIVITY = "OOD_SENSITIVITY"
    SETTLEMENT_COVERAGE_GAP = "SETTLEMENT_COVERAGE_GAP"
    ROBUSTNESS_GAP = "ROBUSTNESS_GAP"
    NO_DEMONSTRATED_IMPROVEMENT = "NO_DEMONSTRATED_IMPROVEMENT"
    MONITORING_OBSERVATION = "MONITORING_OBSERVATION"


class EvidenceTier(StrEnum):
    ACTUAL_LIVE = "ACTUAL_LIVE"
    OBSERVED_REPLAY = "OBSERVED_REPLAY"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"


class ResearchHypothesisKind(StrEnum):
    FEATURE_CHANGE = "FEATURE_CHANGE"
    QUALITY_POLICY_CHANGE = "QUALITY_POLICY_CHANGE"
    ROUTING_CHANGE = "ROUTING_CHANGE"
    SPECIALIST_CHANGE = "SPECIALIST_CHANGE"
    PROMPT_CHANGE = "PROMPT_CHANGE"
    MODEL_CHANGE = "MODEL_CHANGE"
    CALIBRATION_CHANGE = "CALIBRATION_CHANGE"
    FUSION_CHANGE = "FUSION_CHANGE"
    DATA_SOURCE_CHANGE = "DATA_SOURCE_CHANGE"
    THRESHOLD_CHANGE = "THRESHOLD_CHANGE"
    ABSTENTION_CHANGE = "ABSTENTION_CHANGE"


class ExperimentKind(StrEnum):
    ABLATION = "ABLATION"
    FEATURE_POLICY = "FEATURE_POLICY"
    MODEL_VARIANT = "MODEL_VARIANT"
    PROMPT_VARIANT = "PROMPT_VARIANT"
    ROUTING_POLICY = "ROUTING_POLICY"
    CALIBRATION_VARIANT = "CALIBRATION_VARIANT"
    FUSION_VARIANT = "FUSION_VARIANT"
    DATA_SOURCE_VARIANT = "DATA_SOURCE_VARIANT"
    THRESHOLD_VARIANT = "THRESHOLD_VARIANT"


class ComplexityBudget(StrEnum):
    SAME_COMPLEXITY = "SAME_COMPLEXITY"
    MINOR_COMPLEXITY_INCREASE = "MINOR_COMPLEXITY_INCREASE"
    MAJOR_COMPLEXITY_INCREASE = "MAJOR_COMPLEXITY_INCREASE"


class ResearchLifecycleState(StrEnum):
    REGISTERED = "REGISTERED"
    EXPERIMENT_DESIGNED = "EXPERIMENT_DESIGNED"
    CANDIDATE_PENDING = "CANDIDATE_PENDING"
    CANDIDATE_AVAILABLE = "CANDIDATE_AVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class ResearchEntityKind(StrEnum):
    RESEARCH_FINDING = "research_finding"
    RESEARCH_HYPOTHESIS = "research_hypothesis"
    EXPERIMENT_MANIFEST = "experiment_manifest"


@dataclass(frozen=True, slots=True)
class MetricObservation:
    metric_name: str
    value: float | None
    sample_count: int
    baseline_value: float | None = None
    delta: float | None = None

    def __post_init__(self) -> None:
        if not self.metric_name:
            raise ValueError("METRIC_NAME_REQUIRED")
        if self.sample_count < 0:
            raise ValueError("SAMPLE_COUNT_INVALID")


@dataclass(frozen=True, slots=True)
class ComponentMutationSpec:
    """Structured treatment or control specification."""

    component: str
    parameter: str
    baseline_ref: str | None = None
    candidate_ref: str | None = None
    mutation_kind: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component or not self.parameter:
            raise ValueError("COMPONENT_MUTATION_INCOMPLETE")
        if not isinstance(self.details, dict):
            raise ValueError("MUTATION_DETAILS_INVALID")

    @property
    def identity_key(self) -> tuple[str, ...]:
        return (
            self.component,
            self.parameter,
            self.baseline_ref or "",
            self.candidate_ref or "",
            self.mutation_kind or "",
        )


@dataclass(frozen=True, slots=True)
class MetricPlan:
    primary_metric: str
    secondary_metrics: tuple[str, ...] = ()
    guardrails: tuple[str, ...] = ()
    expected_direction: str | None = None

    def __post_init__(self) -> None:
        if not self.primary_metric:
            raise ValueError("PRIMARY_METRIC_REQUIRED")


@dataclass(frozen=True, slots=True)
class GuardrailCriterion:
    metric_name: str
    max_regression: float | None = None
    min_value: float | None = None
    max_value: float | None = None

    def __post_init__(self) -> None:
        if not self.metric_name:
            raise ValueError("GUARDRAIL_METRIC_REQUIRED")


@dataclass(frozen=True, slots=True)
class FalsificationCriterion:
    description: str
    metric_name: str | None = None
    failure_condition: str | None = None

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("FALSIFICATION_DESCRIPTION_REQUIRED")


@dataclass(frozen=True, slots=True)
class ResearchKnowledgeFootprint:
    """Development knowledge preserved for BUILD 19 contamination tracking."""

    evaluation_report_ids: tuple[str, ...] = ()
    evaluation_spec_ids: tuple[str, ...] = ()
    cohort_fingerprints: tuple[str, ...] = ()
    decision_start_ns: int | None = None
    decision_end_ns: int | None = None
    slice_keys: tuple[str, ...] = ()
    comparison_keys: tuple[str, ...] = ()
    mode: str | None = None
    scenario_id: str | None = None
    evidence_tier: EvidenceTier | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluation_report_ids",
            tuple(sorted(set(self.evaluation_report_ids))),
        )
        object.__setattr__(
            self,
            "evaluation_spec_ids",
            tuple(sorted(set(self.evaluation_spec_ids))),
        )
        object.__setattr__(
            self,
            "cohort_fingerprints",
            tuple(sorted(set(self.cohort_fingerprints))),
        )


@dataclass(frozen=True, slots=True)
class DataSpecification:
    target_kind: str
    horizon_ns: int
    mode: str
    decision_start_ns: int
    decision_end_ns: int
    scenario_id: str | None = None
    instrument_ids: tuple[str, ...] = ()
    quality_requirements: tuple[str, ...] = ()
    feature_schema_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.decision_start_ns >= self.decision_end_ns:
            raise ValueError("DATA_RANGE_INVALID")
        if self.horizon_ns <= 0:
            raise ValueError("HORIZON_MUST_BE_POSITIVE")
        if not self.target_kind or not self.mode:
            raise ValueError("DATA_SPEC_INCOMPLETE")


@dataclass(frozen=True, slots=True)
class ValidationRequirements:
    requires_walk_forward: bool = True
    requires_purge: bool = True
    requires_embargo: bool = True
    requires_locked_holdout: bool = True
    validation_policy_ref: str | None = None


@dataclass(frozen=True, slots=True)
class SearchSpaceSpec:
    parameters: dict[str, tuple[Any, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, dict):
            raise ValueError("SEARCH_SPACE_INVALID")
        for key, values in self.parameters.items():
            if not key or not values:
                raise ValueError("SEARCH_SPACE_PARAMETER_INVALID")
            if not isinstance(values, tuple):
                raise ValueError("SEARCH_SPACE_VALUES_MUST_BE_TUPLE")


@dataclass(frozen=True, slots=True)
class SeedPolicy:
    fixed_seeds: tuple[int, ...] = ()
    derivation_algorithm: str | None = None

    def __post_init__(self) -> None:
        if self.fixed_seeds and self.derivation_algorithm:
            raise ValueError("SEED_POLICY_AMBIGUOUS")


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_training_runs: int | None = None
    max_candidates: int | None = None
    max_gpu_hours: float | None = None

    def __post_init__(self) -> None:
        if self.max_training_runs is not None and self.max_training_runs < 1:
            raise ValueError("MAX_TRAINING_RUNS_INVALID")
        if self.max_candidates is not None and self.max_candidates < 1:
            raise ValueError("MAX_CANDIDATES_INVALID")


@dataclass(frozen=True, slots=True)
class ResearchFindingV1:
    finding_id: str
    schema_version: str
    finding_type: ResearchFindingType
    evaluation_report_id: str
    evaluation_spec_id: str
    cohort_fingerprint: str
    metric_observations: tuple[MetricObservation, ...]
    sample_count: int
    mode: str
    evidence_tier: EvidenceTier
    slice_dimension: str | None = None
    slice_value: str | None = None
    comparison_key: str | None = None
    scenario_id: str | None = None
    limitations: tuple[str, ...] = ()
    finding_policy_id: str | None = None
    observation_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.finding_id or not self.evaluation_report_id:
            raise ValueError("FINDING_EVIDENCE_INCOMPLETE")
        if not self.metric_observations:
            raise ValueError("FINDING_METRICS_REQUIRED")
        if self.sample_count < 0:
            raise ValueError("SAMPLE_COUNT_INVALID")
        if not self.observation_summary:
            raise ValueError("OBSERVATION_SUMMARY_REQUIRED")


@dataclass(frozen=True, slots=True)
class ResearchHypothesisV1:
    research_hypothesis_id: str
    schema_version: str
    title: str
    hypothesis_kind: ResearchHypothesisKind
    source_finding_ids: tuple[str, ...]
    claim: str
    treatment: ComponentMutationSpec
    control: ComponentMutationSpec
    primary_metric: str
    expected_direction: str
    falsification: FalsificationCriterion
    knowledge_footprint: ResearchKnowledgeFootprint
    mechanism: str | None = None
    secondary_metrics: tuple[str, ...] = ()
    guardrails: tuple[GuardrailCriterion, ...] = ()
    target_kind: str | None = None
    horizon_ns: int | None = None
    mode: str | None = None
    scenario_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.research_hypothesis_id or not self.title or not self.claim:
            raise ValueError("HYPOTHESIS_FIELDS_INCOMPLETE")
        if not self.source_finding_ids:
            raise ValueError("SOURCE_FINDINGS_REQUIRED")
        if not self.primary_metric or not self.expected_direction:
            raise ValueError("PRIMARY_METRIC_AND_DIRECTION_REQUIRED")
        if self.treatment.identity_key == self.control.identity_key:
            raise ValueError("TREATMENT_EQUALS_CONTROL")


@dataclass(frozen=True, slots=True)
class ExperimentManifestV1:
    experiment_id: str
    schema_version: str
    research_hypothesis_id: str
    experiment_kind: ExperimentKind
    treatment: ComponentMutationSpec
    control: ComponentMutationSpec
    data_spec: DataSpecification
    metric_plan: MetricPlan
    success_criteria: str
    falsification: FalsificationCriterion
    knowledge_footprint: ResearchKnowledgeFootprint
    validation_requirements: ValidationRequirements = field(
        default_factory=ValidationRequirements
    )
    guardrails: tuple[GuardrailCriterion, ...] = ()
    search_space: SearchSpaceSpec | None = None
    seed_policy: SeedPolicy | None = None
    complexity_budget: ComplexityBudget = ComplexityBudget.SAME_COMPLEXITY
    resource_budget: ResourceBudget | None = None
    allowed_changes: tuple[str, ...] = ()
    forbidden_changes: tuple[str, ...] = ()
    evaluation_spec_id: str | None = None
    implementation_version: str = RESEARCH_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.research_hypothesis_id:
            raise ValueError("EXPERIMENT_FIELDS_INCOMPLETE")
        if not self.success_criteria:
            raise ValueError("SUCCESS_CRITERIA_REQUIRED")
        if self.treatment.identity_key == self.control.identity_key:
            raise ValueError("TREATMENT_EQUALS_CONTROL")
        if not self.metric_plan.primary_metric:
            raise ValueError("METRIC_PLAN_REQUIRED")


@dataclass(frozen=True, slots=True)
class ResearchLifecycleEventV1:
    event_id: str
    schema_version: str
    entity_kind: ResearchEntityKind
    entity_id: str
    lifecycle_state: ResearchLifecycleState
    recorded_at_ns: int
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.entity_id:
            raise ValueError("LIFECYCLE_EVENT_INCOMPLETE")
        if self.recorded_at_ns < 0:
            raise ValueError("RECORDED_AT_INVALID")


__all__ = [
    "ComplexityBudget",
    "ComponentMutationSpec",
    "DataSpecification",
    "EvidenceTier",
    "ExperimentKind",
    "ExperimentManifestV1",
    "FalsificationCriterion",
    "GuardrailCriterion",
    "MetricObservation",
    "MetricPlan",
    "RESEARCH_IMPLEMENTATION_VERSION",
    "ResearchEntityKind",
    "ResearchFindingType",
    "ResearchFindingV1",
    "ResearchHypothesisKind",
    "ResearchHypothesisV1",
    "ResearchKnowledgeFootprint",
    "ResearchLifecycleEventV1",
    "ResearchLifecycleState",
    "ResourceBudget",
    "SearchSpaceSpec",
    "SeedPolicy",
    "ValidationRequirements",
]
