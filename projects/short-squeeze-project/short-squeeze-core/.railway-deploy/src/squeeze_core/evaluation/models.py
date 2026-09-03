from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.evidence import CoverageDomain
from squeeze_core.metrics.models import MetricResult
from squeeze_core.metrics.normalized_models import NormalizedMetricResult
from squeeze_core.metrics.pressure_models import DaysToCoverComponents, PressureMetricResult
from squeeze_core.readiness import (
    DomainCoverageSnapshot, EvidenceConflictSummary, EvidenceReadinessSnapshot,
    InputSufficiencyResult,
)

from .diagnostics import EvaluationDiagnostic, sort_diagnostics


class RuleCategory(StrEnum):
    MOMENTUM_DISCOVERY = "MOMENTUM_DISCOVERY"
    SHORT_PRESSURE_CONFIRMATION = "SHORT_PRESSURE_CONFIRMATION"
    CATALYST_EVIDENCE = "CATALYST_EVIDENCE"
    EVIDENCE_VALIDITY = "EVIDENCE_VALIDITY"


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ThresholdOperator(StrEnum):
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    BETWEEN_INCLUSIVE = "BETWEEN_INCLUSIVE"
    EXISTS = "EXISTS"
    ABSENT = "ABSENT"
    EQUAL = "EQUAL"


class ThresholdSourceType(StrEnum):
    ORIGINAL_PLATFORM = "ORIGINAL_PLATFORM"
    ADVISOR_GUIDANCE = "ADVISOR_GUIDANCE"
    PHASE_2V_FINDING = "PHASE_2V_FINDING"
    RESEARCH_POLICY = "RESEARCH_POLICY"
    UNRESOLVED = "UNRESOLVED"


class RuleThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    threshold_id: str
    rule_id: str
    value: Decimal
    unit: str
    operator: ThresholdOperator
    policy_version: str
    source_type: ThresholdSourceType
    source_reference: str
    rationale_code: str
    provisional: bool


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    rule_version: str
    category: RuleCategory
    thresholds: tuple[RuleThreshold, ...] = ()
    required_domains: tuple[CoverageDomain, ...] = ()
    required_metrics: tuple[str, ...] = ()
    provider_scope_required: bool = False
    required_interval: BarInterval | None = None
    required_sessions: tuple[BarSession, ...] = ()
    required_history_samples: int = Field(default=0, ge=0)
    applicable_asset_classes: tuple[AssetClass, ...] = (AssetClass.EQUITY,)

    @field_validator("thresholds")
    @classmethod
    def sort_thresholds(cls, value: tuple[RuleThreshold, ...]) -> tuple[RuleThreshold, ...]:
        return tuple(sorted(value, key=lambda item: item.threshold_id))

    @field_validator("required_domains", "applicable_asset_classes")
    @classmethod
    def sort_enums(cls, value):
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator("required_sessions")
    @classmethod
    def sort_required_sessions(cls, value: tuple[BarSession, ...]) -> tuple[BarSession, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator("required_metrics")
    @classmethod
    def sort_metrics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class CandidateEvaluationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    policy_version: str
    evaluation_version: str
    enabled_rule_ids: tuple[str, ...]
    rules: tuple[RuleDefinition, ...]

    @field_validator("enabled_rule_ids")
    @classmethod
    def sort_enabled(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("rules")
    @classmethod
    def sort_rules(cls, value: tuple[RuleDefinition, ...]) -> tuple[RuleDefinition, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @model_validator(mode="after")
    def rule_inventory_matches_enabled(self) -> "CandidateEvaluationPolicy":
        rule_ids = tuple(item.rule_id for item in self.rules)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("policy contains duplicate rule IDs")
        if tuple(sorted(rule_ids)) != self.enabled_rule_ids:
            raise ValueError("enabled_rule_ids must exactly match policy rule IDs")
        if any(threshold.policy_version != self.policy_version
               for rule in self.rules for threshold in rule.thresholds):
            raise ValueError("threshold policy version does not match policy")
        return self


EvaluationMetric = MetricResult | NormalizedMetricResult | PressureMetricResult | DaysToCoverComponents
EvaluationReadiness = (
    DomainCoverageSnapshot | EvidenceConflictSummary | InputSufficiencyResult |
    EvidenceReadinessSnapshot
)


class RuleEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    policy_version: str
    enabled_rule_ids: tuple[str, ...]
    provider_scope: tuple[str, ...] = ()
    market_interval: BarInterval | None = None
    market_session: tuple[BarSession, ...] = ()
    volume_window: int | None = Field(default=None, gt=0)
    short_interest_provider: str | None = None
    borrow_provider: str | None = None
    news_provider: str | None = None
    input_observations: tuple[Observation, ...] = ()
    input_metrics: tuple[EvaluationMetric, ...] = ()
    input_readiness_results: tuple[EvaluationReadiness, ...] = ()
    default_substitution_fields: tuple[str, ...] = ()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator(
        "enabled_rule_ids", "provider_scope", "default_substitution_fields"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("market_session")
    @classmethod
    def sort_sessions(cls, value: tuple[BarSession, ...]) -> tuple[BarSession, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator("input_observations")
    @classmethod
    def sort_observations(cls, value: tuple[Observation, ...]) -> tuple[Observation, ...]:
        return tuple(sorted(value, key=lambda item: str(item.observation_id)))

    @field_validator("input_metrics", "input_readiness_results")
    @classmethod
    def sort_results(cls, value):
        return tuple(sorted(value, key=lambda item: str(item.deterministic_id)))


class RuleEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    rule_version: str
    category: RuleCategory
    policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    outcome: RuleOutcome
    observed_value: Decimal | None = None
    observed_unit: str | None = None
    operator: ThresholdOperator | None = None
    threshold_values: tuple[Decimal, ...] = ()
    threshold_unit: str | None = None
    provider_scope: tuple[str, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    readiness_snapshot_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[EvaluationDiagnostic, ...] = ()
    explanation_code: str
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator(
        "provider_scope", "input_observation_ids", "input_metric_ids", "readiness_snapshot_ids"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[EvaluationDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "RuleEvaluationResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_evaluation_id, rule_result_identity
            object.__setattr__(self, "deterministic_id",
                               deterministic_evaluation_id(rule_result_identity(self)))
        return self


class CategoryEvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RuleCategory
    pass_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    conflicted_count: int = Field(default=0, ge=0)
    insufficient_data_count: int = Field(default=0, ge=0)
    not_applicable_count: int = Field(default=0, ge=0)


class CandidateEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_version: str
    policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    enabled_rule_ids: tuple[str, ...]
    rule_results: tuple[RuleEvaluationResult, ...]
    results_by_category: tuple[CategoryEvaluationSummary, ...]
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    readiness_snapshot_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[EvaluationDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator(
        "enabled_rule_ids", "input_observation_ids", "input_metric_ids", "readiness_snapshot_ids"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("rule_results")
    @classmethod
    def sort_rule_results(cls, value: tuple[RuleEvaluationResult, ...]):
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @field_validator("results_by_category")
    @classmethod
    def sort_summaries(cls, value: tuple[CategoryEvaluationSummary, ...]):
        order = {item: index for index, item in enumerate(RuleCategory)}
        return tuple(sorted(value, key=lambda item: order[item.category]))

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(cls, value: tuple[EvaluationDiagnostic, ...]):
        return sort_diagnostics(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "CandidateEvaluationResult":
        if self.deterministic_id is None:
            from .identifiers import candidate_evaluation_identity, deterministic_evaluation_id
            object.__setattr__(self, "deterministic_id",
                               deterministic_evaluation_id(candidate_evaluation_identity(self)))
        return self


__all__ = [
    "CandidateEvaluationPolicy", "CandidateEvaluationResult", "CategoryEvaluationSummary", "RuleCategory",
    "RuleDefinition", "RuleEvaluationRequest", "RuleEvaluationResult", "RuleOutcome",
    "RuleThreshold", "ThresholdOperator", "ThresholdSourceType",
]
