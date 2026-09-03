from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .diagnostics import AnalysisDiagnostic, sort_analysis_diagnostics


class AnalysisCohortType(StrEnum):
    HISTORICAL_COMPLETED_CASES = "HISTORICAL_COMPLETED_CASES"
    SYNTHETIC_CASES = "SYNTHETIC_CASES"
    ALL_REGISTERED_CASES = "ALL_REGISTERED_CASES"
    PARTIAL_OR_BLOCKED_CASES = "PARTIAL_OR_BLOCKED_CASES"
    MIXED_PROVENANCE_CASES = "MIXED_PROVENANCE_CASES"


class AnalysisUnit(StrEnum):
    CASE_BOUNDARY = "CASE_BOUNDARY"
    UNIQUE_SYMBOL = "UNIQUE_SYMBOL"
    UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY = "UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY"


class BoundarySelectionPolicy(StrEnum):
    ALL_CASE_BOUNDARIES = "all_case_boundaries.v1"
    EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL = "earliest_detection_boundary_per_symbol.v1"


class IntervalMethod(StrEnum):
    WILSON_SCORE = "WILSON_SCORE"


class SampleSizeState(StrEnum):
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    ONE_OBSERVATION = "ONE_OBSERVATION"
    VERY_SMALL = "VERY_SMALL"
    SMALL = "SMALL"
    LIMITED = "LIMITED"
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
    ADEQUATE_FOR_ESTIMATION_NOT_VALIDATION = "ADEQUATE_FOR_ESTIMATION_NOT_VALIDATION"


class AnalysisProvenanceClassification(StrEnum):
    SANITIZED_PUBLIC_HISTORICAL_DATA = "SANITIZED_PUBLIC_HISTORICAL_DATA"
    SANITIZED_LOCAL_ARTIFACT = "SANITIZED_LOCAL_ARTIFACT"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"
    MIXED_PROVENANCE = "MIXED_PROVENANCE"
    DERIVED_DETERMINISTIC_ANALYSIS = "DERIVED_DETERMINISTIC_ANALYSIS"


class UndefinedReason(StrEnum):
    ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
    NOT_BINOMIAL = "NOT_BINOMIAL"
    INTERVAL_NOT_REQUESTED = "INTERVAL_NOT_REQUESTED"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def assign_deterministic_id(self):
        if (
            "deterministic_id" in type(self).model_fields
            and getattr(self, "deterministic_id") is None
        ):
            from .identifiers import deterministic_analysis_id

            identity = self.model_dump(mode="python", exclude={"deterministic_id"})
            object.__setattr__(self, "deterministic_id", deterministic_analysis_id({
                "result_type": type(self).__name__,
                **identity,
            }))
        return self


class DescriptiveStatisticsPolicy(_FrozenModel):
    schema_version: str = "1.0.0"
    policy_version: str
    allowed_statistics: tuple[str, ...]
    forbidden_statistics: tuple[str, ...]
    provisional: bool
    optimized: bool

    @field_validator("allowed_statistics", "forbidden_statistics")
    @classmethod
    def sort_statistics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class ConfidenceIntervalPolicy(_FrozenModel):
    schema_version: str = "1.0.0"
    policy_version: str
    method: IntervalMethod
    confidence_level: Decimal
    z_value: Decimal
    decimal_precision: int = Field(gt=0)
    serialization_quantum: Decimal = Field(gt=0)
    rounding: str
    supported_proportion_type: str
    random_sampling_allowed: bool


class SampleSizePolicy(_FrozenModel):
    schema_version: str = "1.0.0"
    policy_version: str
    thresholds: tuple[tuple[int, str], ...]
    validation_state_declared: bool
    reserved_states: tuple[str, ...] = ()


class BoundarySelectionPolicyDefinition(_FrozenModel):
    schema_version: str = "1.0.0"
    policy_version: BoundarySelectionPolicy
    selection_fields: tuple[str, ...]
    tie_break_fields: tuple[str, ...]
    outcome_blind: bool
    preserve_excluded_case_ids: bool
    preserve_boundary_count: bool


class AnalysisCohortDefinition(_FrozenModel):
    schema_version: str = "1.0.0"
    cohort_type: AnalysisCohortType
    analysis_unit: AnalysisUnit
    boundary_selection_policy_version: BoundarySelectionPolicy
    provenance_classifications: tuple[AnalysisProvenanceClassification, ...]
    required_complete_cases: bool = False

    @field_validator("provenance_classifications")
    @classmethod
    def sort_provenance(
        cls, value: tuple[AnalysisProvenanceClassification, ...]
    ) -> tuple[AnalysisProvenanceClassification, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class AnalysisCohortExclusion(_FrozenModel):
    case_id: str
    symbol: str
    reason_code: str
    fixture_classification: str
    required_evidence: tuple[str, ...] = ()

    @field_validator("required_evidence")
    @classmethod
    def sort_required_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class AnalysisCohortMembership(_FrozenModel):
    schema_version: str = "1.0.0"
    source_dataset_id: str | None = None
    source_registry_id: str | None = None
    cohort_definition: AnalysisCohortDefinition
    included_case_ids: tuple[str, ...]
    included_symbols: tuple[str, ...]
    exclusions: tuple[AnalysisCohortExclusion, ...]
    fixture_classifications: tuple[AnalysisProvenanceClassification, ...]
    deterministic_id: str | None = None

    @field_validator("included_case_ids", "included_symbols")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("exclusions")
    @classmethod
    def sort_exclusions(
        cls, value: tuple[AnalysisCohortExclusion, ...]
    ) -> tuple[AnalysisCohortExclusion, ...]:
        return tuple(sorted(value, key=lambda item: (item.case_id, item.reason_code)))

    @field_validator("fixture_classifications")
    @classmethod
    def sort_membership_provenance(
        cls, value: tuple[AnalysisProvenanceClassification, ...]
    ) -> tuple[AnalysisProvenanceClassification, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class BoundarySelectionResult(_FrozenModel):
    policy_version: BoundarySelectionPolicy
    analysis_unit: AnalysisUnit
    selected_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    boundary_count_by_symbol: tuple[tuple[str, int], ...]
    outcome_blind: bool
    rationale_code: str
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("selected_case_ids", "excluded_case_ids")
    @classmethod
    def sort_case_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("boundary_count_by_symbol")
    @classmethod
    def sort_boundary_counts(
        cls, value: tuple[tuple[str, int], ...]
    ) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(value))

    @field_validator("diagnostics")
    @classmethod
    def order_selection_diagnostics(
        cls, value: tuple[AnalysisDiagnostic, ...]
    ) -> tuple[AnalysisDiagnostic, ...]:
        return sort_analysis_diagnostics(value)


class IntervalEstimate(_FrozenModel):
    method: IntervalMethod
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    confidence_level: Decimal
    lower_bound: Decimal = Field(ge=0, le=1)
    upper_bound: Decimal = Field(ge=0, le=1)
    independence_assumption_satisfied: bool
    policy_version: str
    deterministic_id: str | None = None


class ProportionEstimate(_FrozenModel):
    metric_name: str
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    exact_fraction: str | None
    decimal_value: Decimal | None
    percentage_value: Decimal | None
    defined: bool
    undefined_reason: UndefinedReason | None
    cohort_id: str
    analysis_unit: AnalysisUnit
    interval: IntervalEstimate | None = None
    interval_policy_version: str
    confidence_level: Decimal
    sample_size_policy_version: str
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def validate_fraction(self) -> "ProportionEstimate":
        if self.numerator > self.denominator:
            raise ValueError("proportion numerator cannot exceed denominator")
        if self.denominator == 0 and self.defined:
            raise ValueError("zero-denominator proportion must be undefined")
        return self


class SampleSizeAssessment(_FrozenModel):
    sample_size: int = Field(ge=0)
    unique_symbol_count: int = Field(ge=0)
    analysis_unit: AnalysisUnit
    state: SampleSizeState
    limitations: tuple[str, ...]
    allowed_interpretation: tuple[str, ...]
    forbidden_interpretation: tuple[str, ...]
    policy_version: str
    deterministic_id: str | None = None


class ConfusionMatrixSummary(_FrozenModel):
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    true_negative_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    unevaluable_count: int = Field(ge=0)
    descriptive_rates: tuple[ProportionEstimate, ...]
    sample_size_assessment: SampleSizeAssessment
    dependence_warning: str | None = None
    deterministic_id: str | None = None


class RuleOutcomePrevalence(_FrozenModel):
    rule_id: str
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    conflicted_count: int = Field(ge=0)
    insufficient_data_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    total_case_count: int = Field(ge=0)
    evaluable_count: int = Field(ge=0)
    proportions: tuple[ProportionEstimate, ...]
    deterministic_id: str | None = None


class OutcomeConditionedRulePrevalence(_FrozenModel):
    outcome_label: str
    group_case_count: int = Field(ge=0)
    rule_prevalence: tuple[RuleOutcomePrevalence, ...]
    sample_size_assessment: SampleSizeAssessment
    dependence_warning: str | None = None
    provenance_classifications: tuple[str, ...]
    deterministic_id: str | None = None


class DomainMissingnessSummary(_FrozenModel):
    domain_id: str
    missing_count: int = Field(ge=0)
    denominator: int = Field(ge=0)
    affected_case_ids: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    cohort_id: str
    analysis_unit: AnalysisUnit
    deterministic_id: str | None = None

    @field_validator("affected_case_ids", "affected_symbols")
    @classmethod
    def sort_affected_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class PrevalenceSummary(_FrozenModel):
    dimension: str
    counts: tuple[tuple[str, int], ...]
    proportions: tuple[ProportionEstimate, ...]
    deterministic_id: str | None = None


class DetectionPrevalenceSummary(PrevalenceSummary):
    dimension: str = "RESEARCH_DETECTION_STATUS"


class OutcomePrevalenceSummary(PrevalenceSummary):
    dimension: str = "OUTCOME_LABEL"


class ClassificationPrevalenceSummary(PrevalenceSummary):
    dimension: str = "RESEARCH_CLASSIFICATION"


class SymbolDependenceSummary(_FrozenModel):
    case_count: int = Field(ge=0)
    unique_symbol_count: int = Field(ge=0)
    symbols_with_multiple_boundaries: tuple[str, ...]
    repeated_boundary_count: int = Field(ge=0)
    maximum_boundaries_per_symbol: int = Field(ge=0)
    boundary_ids_by_symbol: tuple[tuple[str, tuple[str, ...]], ...]
    dependence_detected: bool
    independence_assumption_satisfied: bool
    recommended_analysis_unit: AnalysisUnit
    limitations: tuple[str, ...]
    deterministic_id: str | None = None


class RegistryCaseQuality(_FrozenModel):
    case_id: str
    symbol: str
    case_status: str
    case_type: str
    platform_status: str
    detection_time_evidence_available: bool
    evaluation_available: bool
    outcome_available: bool
    identity_conflict: bool
    exclusion_reason: str | None
    required_evidence: tuple[str, ...]


class DataQualitySummary(_FrozenModel):
    registered_case_count: int = Field(ge=0)
    complete_case_count: int = Field(ge=0)
    synthetic_case_count: int = Field(ge=0)
    partial_case_count: int = Field(ge=0)
    blocked_case_count: int = Field(ge=0)
    conflicting_identity_count: int = Field(ge=0)
    unknown_platform_status_count: int = Field(ge=0)
    registry_cases: tuple[RegistryCaseQuality, ...]
    deterministic_id: str | None = None

    @field_validator("registry_cases")
    @classmethod
    def sort_registry_cases(
        cls, value: tuple[RegistryCaseQuality, ...]
    ) -> tuple[RegistryCaseQuality, ...]:
        return tuple(sorted(value, key=lambda item: item.case_id))


class ResearchLimitation(_FrozenModel):
    code: str
    statement: str
    affected_case_ids: tuple[str, ...] = ()
    affected_symbols: tuple[str, ...] = ()


class ResearchAnalysisRequest(_FrozenModel):
    schema_version: str = "1.0.0"
    analysis_version: str = "phase_3c_analysis.v1"
    source_dataset_id: str | None = None
    source_registry_id: str | None = None
    cohort_definition: AnalysisCohortDefinition
    analysis_unit: AnalysisUnit
    boundary_selection_policy_version: BoundarySelectionPolicy
    statistics_policy_version: str = "phase_3c_descriptive_statistics_policy.v1"
    interval_policy_version: str = "phase_3c_interval_policy.v1"
    confidence_level: Decimal = Decimal("0.95")
    sample_size_policy_version: str = "phase_3c_sample_size_policy.v1"
    included_statistics: tuple[str, ...]
    excluded_statistics: tuple[str, ...]
    deterministic_id: str | None = None

    @field_validator("included_statistics", "excluded_statistics")
    @classmethod
    def sort_statistics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_analysis_unit(self) -> "ResearchAnalysisRequest":
        if self.analysis_unit is not self.cohort_definition.analysis_unit:
            raise ValueError("request and cohort analysis units differ")
        if (
            self.analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
            and self.boundary_selection_policy_version
            is not BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
        ):
            raise ValueError("policy-selected boundary analysis requires earliest policy")
        if self.boundary_selection_policy_version is not self.cohort_definition.boundary_selection_policy_version:
            raise ValueError("request and cohort boundary policies differ")
        if self.source_dataset_id is None and self.source_registry_id is None:
            raise ValueError("at least one explicit source ID is required")
        return self


class ResearchAnalysisResult(_FrozenModel):
    schema_version: str = "1.0.0"
    analysis_version: str
    source_dataset_id: str | None = None
    source_registry_id: str | None = None
    analysis_unit: AnalysisUnit
    boundary_selection_policy_version: BoundarySelectionPolicy
    statistics_policy_version: str
    interval_policy_version: str
    confidence_level: Decimal
    sample_size_policy_version: str
    provenance_classifications: tuple[AnalysisProvenanceClassification, ...]
    request_id: str
    cohort_membership: AnalysisCohortMembership
    boundary_selection: BoundarySelectionResult | None = None
    case_count: int = Field(ge=0)
    unique_symbol_count: int = Field(ge=0)
    boundary_count: int = Field(ge=0)
    symbol_dependence_summary: SymbolDependenceSummary | None = None
    data_quality_summary: DataQualitySummary | None = None
    rule_outcome_prevalence: tuple[RuleOutcomePrevalence, ...] = ()
    domain_missingness_summary: tuple[DomainMissingnessSummary, ...] = ()
    detection_prevalence: DetectionPrevalenceSummary | None = None
    outcome_prevalence: OutcomePrevalenceSummary | None = None
    classification_prevalence: ClassificationPrevalenceSummary | None = None
    confusion_matrix: ConfusionMatrixSummary | None = None
    sample_size_assessments: tuple[SampleSizeAssessment, ...] = ()
    limitations: tuple[ResearchLimitation, ...]
    diagnostics: tuple[AnalysisDiagnostic, ...]
    deterministic_id: str | None = None

    @field_validator("diagnostics")
    @classmethod
    def order_diagnostics(
        cls, value: tuple[AnalysisDiagnostic, ...]
    ) -> tuple[AnalysisDiagnostic, ...]:
        return sort_analysis_diagnostics(value)


class ResearchAnalysisReport(_FrozenModel):
    schema_version: str = "1.0.0"
    analysis_result_id: str
    report_format: str
    section_names: tuple[str, ...]
    content_sha256: str
    deterministic_id: str | None = None


__all__ = [name for name in tuple(globals()) if not name.startswith("_")]
