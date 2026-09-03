from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.evaluation import RuleEvaluationResult
from squeeze_core.evaluation import RuleCategory, RuleOutcome

from .diagnostics import ResearchDiagnostic, sort_diagnostics


class CandidateCaseType(StrEnum):
    ORIGINAL_PLATFORM_SURFACED = "ORIGINAL_PLATFORM_SURFACED"
    ORIGINAL_PLATFORM_NOT_SURFACED = "ORIGINAL_PLATFORM_NOT_SURFACED"
    ORIGINAL_PLATFORM_STATUS_UNKNOWN = "ORIGINAL_PLATFORM_STATUS_UNKNOWN"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"


class CandidateCaseStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EVALUATION_ONLY = "EVALUATION_ONLY"
    OUTCOME_ONLY = "OUTCOME_ONLY"
    ARTIFACT_DISCOVERY_ONLY = "ARTIFACT_DISCOVERY_ONLY"
    BLOCKED_MISSING_DETECTION_TIME = "BLOCKED_MISSING_DETECTION_TIME"
    BLOCKED_MISSING_EVALUATION_INPUTS = "BLOCKED_MISSING_EVALUATION_INPUTS"
    BLOCKED_MISSING_OUTCOME_DATA = "BLOCKED_MISSING_OUTCOME_DATA"
    BLOCKED_CONFLICTING_IDENTITY = "BLOCKED_CONFLICTING_IDENTITY"


class OriginalPlatformStatus(StrEnum):
    SURFACED = "SURFACED"
    NOT_SURFACED = "NOT_SURFACED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FixtureClassification(StrEnum):
    SANITIZED_PUBLIC_HISTORICAL_DATA = "SANITIZED_PUBLIC_HISTORICAL_DATA"
    SANITIZED_LOCAL_ARTIFACT = "SANITIZED_LOCAL_ARTIFACT"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"
    MIXED_PROVENANCE = "MIXED_PROVENANCE"


class DetectionStatus(StrEnum):
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    UNEVALUABLE = "UNEVALUABLE"


class OutcomeLabel(StrEnum):
    SUBSTANTIAL_UPWARD_MOVE = "SUBSTANTIAL_UPWARD_MOVE"
    NO_SUBSTANTIAL_UPWARD_MOVE = "NO_SUBSTANTIAL_UPWARD_MOVE"
    SUBSTANTIAL_DOWNWARD_MOVE = "SUBSTANTIAL_DOWNWARD_MOVE"
    MIXED_OR_VOLATILE = "MIXED_OR_VOLATILE"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    OUTCOME_INSUFFICIENT_DATA = "OUTCOME_INSUFFICIENT_DATA"


class OutcomeCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class ResearchCaseClassification(StrEnum):
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    TRUE_NEGATIVE = "TRUE_NEGATIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    UNEVALUABLE = "UNEVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OrderingPolicy(StrEnum):
    REQUEST_ORDER = "REQUEST_ORDER"
    CANONICAL_CASE_ID = "CANONICAL_CASE_ID"


class DetectionPredicatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    policy_version: str
    required_rule_ids: tuple[str, ...]
    allowed_pass_outcomes: tuple[str, ...] = ("PASS",)
    unknown_handling: str = "UNEVALUABLE"
    conflict_handling: str = "UNEVALUABLE"
    insufficient_data_handling: str = "UNEVALUABLE"
    not_applicable_handling: str = "UNEVALUABLE"
    provisional: bool
    rationale_code: str

    @model_validator(mode="after")
    def unique_required_rules(self) -> "DetectionPredicatePolicy":
        if len(set(self.required_rule_ids)) != len(self.required_rule_ids):
            raise ValueError("detection policy contains duplicate required rule IDs")
        return self


class OutcomeLabelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    policy_version: str
    reference_price_policy: str
    horizon: str
    upward_threshold_percent: Decimal
    downward_threshold_percent: Decimal
    provisional: bool
    rationale_code: str


class Phase3AEvaluationRequestArtifact(BaseModel):
    """Local routing envelope for invoking the unchanged Phase 3A evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    policy_version: str
    enabled_rule_ids: tuple[str, ...]
    policy_path: str
    evidence_path: str
    provider_scope: tuple[str, ...] = ()
    market_interval: str | None = None
    market_session: tuple[str, ...] = ()
    volume_window: int | None = Field(default=None, gt=0)
    short_interest_provider: str | None = None
    borrow_provider: str | None = None
    news_provider: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_request_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("as_of")
    @classmethod
    def normalize_request_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("enabled_rule_ids", "provider_scope", "market_session")
    @classmethod
    def sort_request_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


class ResearchDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    evaluation_id: str
    policy_version: str
    status: DetectionStatus
    required_rule_ids: tuple[str, ...]
    supporting_rule_result_ids: tuple[str, ...]
    diagnostics: tuple[ResearchDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("supporting_rule_result_ids")
    @classmethod
    def sort_support_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[ResearchDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_id(self) -> "ResearchDetectionResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RESEARCH_DETECTION",
                "evaluation_id": self.evaluation_id,
                "policy_version": self.policy_version,
                "status": self.status,
                "required_rule_ids": self.required_rule_ids,
                "supporting_rule_result_ids": self.supporting_rule_result_ids,
                "diagnostic_codes": tuple(item.code for item in self.diagnostics),
            }))
        return self


class RetrospectiveOutcomeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    case_id: str
    symbol: str
    detection_boundary: datetime
    reference_price_policy: str
    reference_price: Decimal | None = None
    horizon: str
    maximum_observed_move_percent: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    completeness: OutcomeCompleteness
    supporting_observation_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("detection_boundary")
    @classmethod
    def normalize_boundary(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("supporting_observation_ids", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def assign_id(self) -> "RetrospectiveOutcomeObservation":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RETROSPECTIVE_OUTCOME_OBSERVATION",
                "case_id": self.case_id,
                "symbol": self.symbol,
                "detection_boundary": self.detection_boundary,
                "reference_price_policy": self.reference_price_policy,
                "reference_price": self.reference_price,
                "horizon": self.horizon,
                "maximum_observed_move_percent": self.maximum_observed_move_percent,
                "maximum_adverse_move_percent": self.maximum_adverse_move_percent,
                "completeness": self.completeness,
                "supporting_observation_ids": self.supporting_observation_ids,
            }))
        return self


class OutcomeLabelResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    outcome_observation_id: str
    policy_version: str
    label: OutcomeLabel
    reference_price_policy: str
    detection_boundary: datetime
    horizon: str
    upward_threshold_percent: Decimal
    downward_threshold_percent: Decimal
    maximum_observed_move_percent: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    completeness: OutcomeCompleteness
    supporting_observation_ids: tuple[str, ...] = ()
    diagnostics: tuple[ResearchDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("detection_boundary")
    @classmethod
    def normalize_boundary(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("supporting_observation_ids")
    @classmethod
    def sort_support_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[ResearchDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_id(self) -> "OutcomeLabelResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_OUTCOME_LABEL",
                "outcome_observation_id": self.outcome_observation_id,
                "policy_version": self.policy_version,
                "label": self.label,
                "reference_price_policy": self.reference_price_policy,
                "detection_boundary": self.detection_boundary,
                "horizon": self.horizon,
                "thresholds": (
                    self.upward_threshold_percent, self.downward_threshold_percent,
                ),
                "maximum_observed_move_percent": self.maximum_observed_move_percent,
                "maximum_adverse_move_percent": self.maximum_adverse_move_percent,
                "completeness": self.completeness,
                "supporting_observation_ids": self.supporting_observation_ids,
            }))
        return self


class ResearchClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    case_id: str
    detection_status: DetectionStatus
    outcome_label: OutcomeLabel
    classification: ResearchCaseClassification
    detection_result_id: str
    outcome_label_result_id: str
    evaluable_pair: bool = False
    unevaluable_cause: str | None = None
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "ResearchClassificationResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RESEARCH_CLASSIFICATION",
                "case_id": self.case_id,
                "detection_status": self.detection_status,
                "outcome_label": self.outcome_label,
                "classification": self.classification,
                "detection_result_id": self.detection_result_id,
                "outcome_label_result_id": self.outcome_label_result_id,
            }))
        return self


class CandidateResearchCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    case_id: str
    symbol: str
    asset_class: AssetClass
    case_type: CandidateCaseType
    case_status: CandidateCaseStatus
    original_platform_status: OriginalPlatformStatus
    original_platform_artifact_ids: tuple[str, ...] = ()
    evaluation_as_of: datetime
    phase_3a_policy_version: str
    phase_3a_evaluation_id: str
    phase_3a_rule_results: tuple[RuleEvaluationResult, ...]
    detection_policy_version: str
    research_detection_status: DetectionStatus
    detection_result_id: str
    outcome_policy_version: str
    outcome_label: OutcomeLabel
    outcome_observation_id: str
    outcome_label_result_id: str
    outcome_reference_policy: str
    outcome_horizon: str
    maximum_observed_move_percent: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    outcome_completeness: OutcomeCompleteness
    outcome_supporting_observation_ids: tuple[str, ...] = ()
    research_classification: ResearchCaseClassification
    research_classification_id: str
    fixture_classification: FixtureClassification
    limitations: tuple[str, ...] = ()
    diagnostics: tuple[ResearchDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("evaluation_as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("phase_3a_rule_results")
    @classmethod
    def sort_rules(cls, value: tuple[RuleEvaluationResult, ...]):
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @field_validator(
        "original_platform_artifact_ids", "limitations", "outcome_supporting_observation_ids"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[ResearchDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_id(self) -> "CandidateResearchCase":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_CANDIDATE_RESEARCH_CASE",
                "case_id": self.case_id,
                "symbol": self.symbol,
                "asset_class": self.asset_class,
                "case_type": self.case_type,
                "case_status": self.case_status,
                "evaluation_as_of": self.evaluation_as_of,
                "phase_3a_evaluation_id": self.phase_3a_evaluation_id,
                "detection_policy_version": self.detection_policy_version,
                "research_detection_status": self.research_detection_status,
                "outcome_policy_version": self.outcome_policy_version,
                "outcome_label": self.outcome_label,
                "outcome_observation_id": self.outcome_observation_id,
                "research_classification": self.research_classification,
                "original_platform_status": self.original_platform_status,
                "supporting_artifact_ids": self.original_platform_artifact_ids,
                "limitations": self.limitations,
            }))
        return self


class DatasetProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str
    generated_from_case_registry_id: str
    phase_3a_policy_version: str
    research_detection_policy_version: str
    outcome_policy_version: str
    case_ids: tuple[str, ...]
    row_ids: tuple[str, ...]
    source_fixture_ids: tuple[str, ...]
    fixture_classification_counts: tuple[tuple[str, int], ...]
    limitations: tuple[str, ...]
    deterministic_id: str | None = None

    @field_validator("source_fixture_ids", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("fixture_classification_counts")
    @classmethod
    def sort_counts(cls, value: tuple[tuple[str, int], ...]):
        return tuple(sorted(value))

    @model_validator(mode="after")
    def assign_id(self) -> "DatasetProvenance":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_DATASET_PROVENANCE",
                "dataset_version": self.dataset_version,
                "generated_from_case_registry_id": self.generated_from_case_registry_id,
                "policy_versions": (
                    self.phase_3a_policy_version,
                    self.research_detection_policy_version,
                    self.outcome_policy_version,
                ),
                "case_ids": self.case_ids,
                "row_ids": self.row_ids,
                "source_fixture_ids": self.source_fixture_ids,
                "fixture_classification_counts": self.fixture_classification_counts,
            }))
        return self


class ResearchDatasetRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str
    case_id: str
    symbol: str
    asset_class: AssetClass
    case_type: CandidateCaseType
    case_status: CandidateCaseStatus
    evaluation_as_of: datetime
    phase_3a_policy_version: str
    research_detection_policy_version: str
    outcome_policy_version: str
    original_platform_status: OriginalPlatformStatus
    research_detection_status: DetectionStatus
    outcome_label: OutcomeLabel
    research_classification: ResearchCaseClassification
    phase_3a_evaluation_id: str
    outcome_observation_id: str
    rule_outcomes: dict[str, str]
    rule_observed_values: dict[str, Decimal | None]
    rule_threshold_values: dict[str, tuple[Decimal, ...]]
    rule_diagnostic_codes: dict[str, tuple[str, ...]]
    category_counts: dict[str, dict[str, int]]
    missing_domains: tuple[str, ...]
    conflicted_rules: tuple[str, ...]
    insufficient_rules: tuple[str, ...]
    outcome_reference_policy: str
    outcome_horizon: str
    maximum_observed_move_percent: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    fixture_classification: FixtureClassification
    source_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    row_id: str

    @field_validator("evaluation_as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator(
        "missing_domains", "conflicted_rules", "insufficient_rules", "source_ids", "limitations"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class ResearchDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    dataset_version: str
    rows: tuple[ResearchDatasetRow, ...]
    provenance: DatasetProvenance
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "ResearchDataset":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RESEARCH_DATASET",
                "dataset_version": self.dataset_version,
                "case_ids": tuple(item.case_id for item in self.rows),
                "row_ids": tuple(item.row_id for item in self.rows),
                "provenance_id": self.provenance.deterministic_id,
            }))
        return self


class SkippedResearchCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    case_status: CandidateCaseStatus
    diagnostics: tuple[ResearchDiagnostic, ...]

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[ResearchDiagnostic, ...]):
        return sort_diagnostics(value)


class BatchEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    batch_version: str
    phase_3a_policy_version: str
    research_detection_policy_version: str
    outcome_label_policy_version: str
    case_ids: tuple[str, ...]
    case_registry_version: str
    ordering_policy: OrderingPolicy = OrderingPolicy.REQUEST_ORDER
    fail_fast: bool = False
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "BatchEvaluationRequest":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_BATCH_REQUEST",
                "batch_version": self.batch_version,
                "phase_3a_policy_version": self.phase_3a_policy_version,
                "research_detection_policy_version": self.research_detection_policy_version,
                "outcome_label_policy_version": self.outcome_label_policy_version,
                "case_ids": self.case_ids,
                "case_registry_version": self.case_registry_version,
                "ordering_policy": self.ordering_policy,
                "fail_fast": self.fail_fast,
            }))
        return self


class BatchEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    batch_version: str
    request_id: str
    case_registry_id: str
    phase_3a_policy_version: str
    research_detection_policy_version: str
    outcome_label_policy_version: str
    case_results: tuple[CandidateResearchCase, ...]
    skipped_cases: tuple[SkippedResearchCase, ...] = ()
    diagnostics: tuple[ResearchDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[ResearchDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_id(self) -> "BatchEvaluationResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_BATCH_RESULT",
                "batch_version": self.batch_version,
                "case_registry_id": self.case_registry_id,
                "phase_3a_policy_version": self.phase_3a_policy_version,
                "research_detection_policy_version": self.research_detection_policy_version,
                "outcome_label_policy_version": self.outcome_label_policy_version,
                "case_result_ids": tuple(str(item.deterministic_id) for item in self.case_results),
                "skipped_case_ids": tuple(item.case_id for item in self.skipped_cases),
            }))
        return self


class RuleOutcomeMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    evaluation_as_of: datetime
    rule_outcomes: dict[str, str]
    research_detection_status: DetectionStatus
    outcome_label: OutcomeLabel
    research_classification: ResearchCaseClassification

    @field_validator("evaluation_as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class RuleOutcomeMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    rule_ids: tuple[str, ...]
    rows: tuple[RuleOutcomeMatrixRow, ...]
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "RuleOutcomeMatrix":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RULE_OUTCOME_MATRIX",
                "rule_ids": self.rule_ids,
                "rows": tuple({
                    "case_id": row.case_id,
                    "rule_outcomes": tuple(row.rule_outcomes.items()),
                    "detection": row.research_detection_status,
                    "outcome": row.outcome_label,
                    "classification": row.research_classification,
                } for row in self.rows),
            }))
        return self


class RuleFrequency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    conflicted_count: int = Field(ge=0)
    insufficient_data_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    total_case_count: int = Field(ge=0)
    evaluable_case_count: int = Field(ge=0)
    pass_rate_among_evaluable: Decimal | None = None
    fail_rate_among_evaluable: Decimal | None = None
    unknown_rate: Decimal | None = None
    conflict_rate: Decimal | None = None
    insufficient_data_rate: Decimal | None = None


class RuleFrequencySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rules: tuple[RuleFrequency, ...]
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "RuleFrequencySummary":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_RULE_FREQUENCY_SUMMARY",
                "rules": tuple(item.model_dump(mode="json") for item in self.rules),
            }))
        return self


class OutcomeConditionedRuleGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome_label: OutcomeLabel
    rules: tuple[RuleFrequency, ...]


class OutcomeConditionedRuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    groups: tuple[OutcomeConditionedRuleGroup, ...]
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "OutcomeConditionedRuleSummary":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_OUTCOME_CONDITIONED_RULE_SUMMARY",
                "groups": tuple(item.model_dump(mode="json") for item in self.groups),
            }))
        return self


class CategoryFrequency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RuleCategory
    rule_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    conflicted_count: int = Field(ge=0)
    insufficient_data_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    cases_with_any_pass: int = Field(ge=0)
    cases_with_all_required_rules_pass: int = Field(ge=0)
    cases_with_any_unknown: int = Field(ge=0)
    cases_with_any_conflict: int = Field(ge=0)


class CategoryFrequencySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    categories: tuple[CategoryFrequency, ...]
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def assign_id(self) -> "CategoryFrequencySummary":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_CATEGORY_FREQUENCY_SUMMARY",
                "categories": tuple(item.model_dump(mode="json") for item in self.categories),
            }))
        return self


class MissingnessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_domain_counts: tuple[tuple[str, int], ...]
    conflicted_rule_count: int = Field(ge=0)
    insufficient_rule_count: int = Field(ge=0)
    deterministic_id: str | None = None

    @field_validator("missing_domain_counts")
    @classmethod
    def sort_counts(cls, value: tuple[tuple[str, int], ...]):
        return tuple(sorted(value, key=lambda item: item[0]))

    @model_validator(mode="after")
    def assign_id(self) -> "MissingnessSummary":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id
            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_MISSINGNESS_SUMMARY",
                "missing_domain_counts": self.missing_domain_counts,
                "conflicted_rule_count": self.conflicted_rule_count,
                "insufficient_rule_count": self.insufficient_rule_count,
            }))
        return self


class CandidateCaseRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    case_id: str
    symbol: str
    asset_class: AssetClass
    case_type: CandidateCaseType
    case_status: CandidateCaseStatus
    original_platform_status: OriginalPlatformStatus
    detection_time_evidence_id: str | None = None
    evaluation_as_of: datetime | None = None
    evaluation_request_path: str | None = None
    evaluation_result_path: str | None = None
    outcome_observation_path: str | None = None
    original_platform_artifact_ids: tuple[str, ...] = ()
    historical_dataset_ids: tuple[str, ...] = ()
    phase_3a_policy_version: str
    limitations: tuple[str, ...] = ()
    fixture_classification: FixtureClassification
    deterministic_id: str | None = None

    @field_validator("case_id", "phase_3a_policy_version")
    @classmethod
    def require_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value is required")
        return normalized

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("evaluation_as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @field_validator(
        "original_platform_artifact_ids", "historical_dataset_ids", "limitations"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "CandidateCaseRegistryEntry":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            identity = {
                "result_type": "PHASE_3B_CASE_REGISTRY_ENTRY",
                "schema_version": self.schema_version,
                "case_id": self.case_id,
                "symbol": self.symbol,
                "asset_class": self.asset_class,
                "case_type": self.case_type,
                "case_status": self.case_status,
                "original_platform_status": self.original_platform_status,
                "detection_time_evidence_id": self.detection_time_evidence_id,
                "evaluation_as_of": self.evaluation_as_of,
                "phase_3a_policy_version": self.phase_3a_policy_version,
                "original_platform_artifact_ids": self.original_platform_artifact_ids,
                "historical_dataset_ids": self.historical_dataset_ids,
                "limitations": self.limitations,
                "fixture_classification": self.fixture_classification,
            }
            object.__setattr__(self, "deterministic_id", deterministic_research_id(identity))
        return self


class CandidateCaseRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    registry_version: str
    entries: tuple[CandidateCaseRegistryEntry, ...]
    deterministic_id: str | None = None

    @field_validator("entries")
    @classmethod
    def validate_and_sort_entries(
        cls, value: tuple[CandidateCaseRegistryEntry, ...]
    ) -> tuple[CandidateCaseRegistryEntry, ...]:
        case_ids = tuple(item.case_id for item in value)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("RESEARCH_CASE_DUPLICATE")
        semantic_ids = tuple((item.symbol, item.evaluation_as_of) for item in value)
        if len(set(semantic_ids)) != len(semantic_ids):
            raise ValueError("RESEARCH_CASE_IDENTITY_CONFLICT")
        return tuple(sorted(value, key=lambda item: item.case_id))

    @model_validator(mode="after")
    def assign_id(self) -> "CandidateCaseRegistry":
        if self.deterministic_id is None:
            from .identifiers import deterministic_research_id

            object.__setattr__(self, "deterministic_id", deterministic_research_id({
                "result_type": "PHASE_3B_CASE_REGISTRY",
                "schema_version": self.schema_version,
                "registry_version": self.registry_version,
                "entry_ids": tuple(str(item.deterministic_id) for item in self.entries),
            }))
        return self


__all__ = [
    "BatchEvaluationRequest", "BatchEvaluationResult", "CandidateCaseRegistry",
    "CandidateCaseRegistryEntry", "CandidateCaseStatus", "CandidateCaseType",
    "CandidateResearchCase",
    "DetectionPredicatePolicy", "DetectionStatus", "FixtureClassification", "OrderingPolicy",
    "OriginalPlatformStatus", "OutcomeCompleteness", "OutcomeLabel", "OutcomeLabelPolicy",
    "Phase3AEvaluationRequestArtifact",
    "OutcomeLabelResult", "ResearchCaseClassification", "ResearchClassificationResult",
    "ResearchDetectionResult", "RetrospectiveOutcomeObservation", "SkippedResearchCase",
    "CategoryFrequency", "CategoryFrequencySummary", "MissingnessSummary",
    "OutcomeConditionedRuleGroup", "OutcomeConditionedRuleSummary", "RuleFrequency",
    "RuleFrequencySummary", "RuleOutcomeMatrix", "RuleOutcomeMatrixRow",
    "DatasetProvenance", "ResearchDataset", "ResearchDatasetRow",
]
