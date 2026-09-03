from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.contracts import AssetClass, Quality
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.evidence import ConflictClassification, CoverageDomain

from .diagnostics import ReadinessDiagnostic


def _sorted_str_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(value))


def _sorted_domain_tuple(value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
    return tuple(sorted(value, key=lambda item: item.value))


class DomainCoverageState(StrEnum):
    """Phase 2D's own domain-presence vocabulary -- deliberately distinct from
    squeeze_core.evidence.CoverageState (docs/phase-2d-design.md Section 5). Freshness
    (STALE/DELAYED/UNKNOWN_FRESHNESS in the Phase 1 vocabulary) is folded into PRESENT
    here because staleness is an age fact (EvidenceAgeAlignment), never a presence
    fact or a threshold judgment."""

    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICTED = "CONFLICTED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class StructuralState(StrEnum):
    """An input-contract state, not a candidate or trading-readiness label (docs/
    phase-2d-design.md Section 1). Exactly these four members exist; no PRIME/
    SUBPRIME/STRONG/WEAK/BULLISH/BEARISH member is ever added."""

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"


class AgeDimension(StrEnum):
    """Only two members: the only two age concepts squeeze_core.metrics.source_age
    already computes deterministically (docs/phase-2d-design.md Section 4)."""

    AVAILABILITY_AGE = "AVAILABILITY_AGE"
    REPORTING_PERIOD_AGE = "REPORTING_PERIOD_AGE"


class MissingnessCategory(StrEnum):
    MISSING_DOMAIN = "MISSING_DOMAIN"
    MISSING_REQUIRED_METRIC = "MISSING_REQUIRED_METRIC"
    UNKNOWN_AVAILABILITY = "UNKNOWN_AVAILABILITY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class DomainRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    required: bool


class OperationRequirementPolicy(BaseModel):
    """Purely declarative input contract for one already-implemented Phase 2A/2B/2C
    operation. Contains no formula logic and no trading threshold (docs/phase-2d-
    design.md Section 10)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str
    policy_version: str
    required_domains: tuple[CoverageDomain, ...] = ()
    optional_domains: tuple[CoverageDomain, ...] = ()
    required_metric_names: tuple[str, ...] = ()
    required_units: tuple[str, ...] = ()
    requires_trailing_window: bool = False
    required_provider_scope: str | None = None
    required_session_scope: tuple[str, ...] = ()
    required_interval_scope: str | None = None
    required_age_dimensions: tuple[AgeDimension, ...] = ()
    allow_conflicts: bool = False
    allow_unknown_availability: bool = False

    @field_validator("required_domains", "optional_domains")
    @classmethod
    def sort_domains(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator("required_metric_names", "required_units", "required_session_scope")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def domains_disjoint(self) -> "OperationRequirementPolicy":
        overlap = set(self.required_domains) & set(self.optional_domains)
        if overlap:
            raise ValueError(
                f"domains cannot be both required and optional: {sorted(d.value for d in overlap)}"
            )
        return self


class DomainCoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    state: DomainCoverageState
    observation_ids: tuple[str, ...] = ()
    availability_time: datetime | None = None
    availability_age_seconds: int | None = Field(default=None, ge=0)
    reporting_period_end: date | None = None
    reporting_period_age_seconds: int | None = Field(default=None, ge=0)
    conflict_ids: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()

    @field_validator("observation_ids", "conflict_ids", "missing_fields", "diagnostic_codes")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("availability_time")
    @classmethod
    def normalize_availability_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class DomainCoverageSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    requested_domains: tuple[CoverageDomain, ...]
    present_domains: tuple[CoverageDomain, ...] = ()
    missing_domains: tuple[CoverageDomain, ...] = ()
    unavailable_domains: tuple[CoverageDomain, ...] = ()
    conflicted_domains: tuple[CoverageDomain, ...] = ()
    cancelled_domains: tuple[CoverageDomain, ...] = ()
    partial_domains: tuple[CoverageDomain, ...] = ()
    unknown_domains: tuple[CoverageDomain, ...] = ()
    coverage_by_domain: tuple[DomainCoverageEntry, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator(
        "requested_domains",
        "present_domains",
        "missing_domains",
        "unavailable_domains",
        "conflicted_domains",
        "cancelled_domains",
        "partial_domains",
        "unknown_domains",
    )
    @classmethod
    def sort_domains(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator("input_observation_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("coverage_by_domain")
    @classmethod
    def sort_coverage_entries(
        cls, value: tuple[DomainCoverageEntry, ...]
    ) -> tuple[DomainCoverageEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.domain.value))

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "DomainCoverageSnapshot":
        if self.deterministic_id is None:
            from .identifiers import coverage_snapshot_identity, deterministic_readiness_id

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(coverage_snapshot_identity(self)),
            )
        return self


class DomainAgeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    age_seconds: int | None = Field(default=None, ge=0)
    observation_id: str | None = None


class EvidenceAgeAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    age_dimension: AgeDimension
    domain_ages: tuple[DomainAgeEntry, ...] = ()
    youngest_age_seconds: int | None = Field(default=None, ge=0)
    oldest_age_seconds: int | None = Field(default=None, ge=0)
    age_spread_seconds: int | None = Field(default=None, ge=0)
    mean_age_seconds: Decimal | None = None
    domain_count: int = Field(ge=0)
    missing_age_domains: tuple[CoverageDomain, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("domain_ages")
    @classmethod
    def sort_domain_ages(cls, value: tuple[DomainAgeEntry, ...]) -> tuple[DomainAgeEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.domain.value))

    @field_validator("missing_age_domains")
    @classmethod
    def sort_missing(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator("input_observation_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "EvidenceAgeAlignment":
        if self.deterministic_id is None:
            from .identifiers import age_alignment_identity, deterministic_readiness_id

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(age_alignment_identity(self)),
            )
        return self


class ReportingPeriodEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    reporting_period_end: date | None = None
    reporting_period_age_seconds: int | None = Field(default=None, ge=0)
    observation_id: str | None = None


class ReportingPeriodAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    reporting_period_by_domain: tuple[ReportingPeriodEntry, ...] = ()
    earliest_reporting_period_end: date | None = None
    latest_reporting_period_end: date | None = None
    reporting_period_spread_seconds: int | None = Field(default=None, ge=0)
    missing_reporting_period_domains: tuple[CoverageDomain, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("reporting_period_by_domain")
    @classmethod
    def sort_entries(
        cls, value: tuple[ReportingPeriodEntry, ...]
    ) -> tuple[ReportingPeriodEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.domain.value))

    @field_validator("missing_reporting_period_domains")
    @classmethod
    def sort_missing(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator("input_observation_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "ReportingPeriodAlignment":
        if self.deterministic_id is None:
            from .identifiers import deterministic_readiness_id, reporting_alignment_identity

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(reporting_alignment_identity(self)),
            )
        return self


class DomainConflictEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    conflict_ids: tuple[str, ...] = ()

    @field_validator("conflict_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)


class EvidenceConflictSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    conflict_count: int = Field(ge=0)
    conflicts_by_domain: tuple[DomainConflictEntry, ...] = ()
    conflict_ids: tuple[str, ...] = ()
    affected_observation_ids: tuple[str, ...] = ()
    affected_metric_ids: tuple[str, ...] = ()
    conflict_categories: tuple[ConflictClassification, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("conflicts_by_domain")
    @classmethod
    def sort_by_domain(
        cls, value: tuple[DomainConflictEntry, ...]
    ) -> tuple[DomainConflictEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.domain.value))

    @field_validator(
        "conflict_ids", "affected_observation_ids", "affected_metric_ids", "input_observation_ids"
    )
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("conflict_categories")
    @classmethod
    def sort_categories(
        cls, value: tuple[ConflictClassification, ...]
    ) -> tuple[ConflictClassification, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "EvidenceConflictSummary":
        if self.deterministic_id is None:
            from .identifiers import conflict_summary_identity, deterministic_readiness_id

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(conflict_summary_identity(self)),
            )
        return self


class DomainMissingnessEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    categories: tuple[MissingnessCategory, ...] = ()

    @field_validator("categories")
    @classmethod
    def sort_categories(
        cls, value: tuple[MissingnessCategory, ...]
    ) -> tuple[MissingnessCategory, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class EvidenceMissingnessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    asset_class: AssetClass
    as_of: datetime
    operation: str | None = None
    missing_domain_count: int = Field(ge=0)
    missing_field_count: int = Field(ge=0)
    missing_by_domain: tuple[DomainMissingnessEntry, ...] = ()
    missing_required_inputs: tuple[str, ...] = ()
    unknown_by_domain: tuple[CoverageDomain, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("missing_by_domain")
    @classmethod
    def sort_by_domain(
        cls, value: tuple[DomainMissingnessEntry, ...]
    ) -> tuple[DomainMissingnessEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.domain.value))

    @field_validator("unknown_by_domain")
    @classmethod
    def sort_unknown(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator(
        "missing_required_inputs", "input_observation_ids", "input_metric_ids"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "EvidenceMissingnessSummary":
        if self.deterministic_id is None:
            from .identifiers import deterministic_readiness_id, missingness_summary_identity

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(missingness_summary_identity(self)),
            )
        return self


class InputSufficiencyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str
    policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    required_domains: tuple[CoverageDomain, ...] = ()
    required_metrics: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    invalid_inputs: tuple[str, ...] = ()
    conflicted_inputs: tuple[str, ...] = ()
    incompatible_inputs: tuple[str, ...] = ()
    insufficient_history_inputs: tuple[str, ...] = ()
    point_in_time_failures: tuple[str, ...] = ()
    structural_state: StructuralState
    referenced_metric_ids: tuple[str, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("required_domains")
    @classmethod
    def sort_domains(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator(
        "required_metrics",
        "missing_inputs",
        "invalid_inputs",
        "conflicted_inputs",
        "incompatible_inputs",
        "insufficient_history_inputs",
        "point_in_time_failures",
        "referenced_metric_ids",
        "input_observation_ids",
        "input_metric_ids",
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "InputSufficiencyResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_readiness_id, sufficiency_result_identity

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(sufficiency_result_identity(self)),
            )
        return self


class EvidenceReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str
    policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    structural_state: StructuralState
    required_domains: tuple[CoverageDomain, ...] = ()
    required_metrics: tuple[str, ...] = ()
    coverage_snapshot_id: str
    age_alignment_id: str | None = None
    reporting_alignment_id: str | None = None
    conflict_summary_id: str
    missingness_summary_id: str
    sufficiency_result_id: str
    missing_inputs: tuple[str, ...] = ()
    conflicted_inputs: tuple[str, ...] = ()
    incompatible_inputs: tuple[str, ...] = ()
    insufficient_history_inputs: tuple[str, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ReadinessDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("required_domains")
    @classmethod
    def sort_domains(cls, value: tuple[CoverageDomain, ...]) -> tuple[CoverageDomain, ...]:
        return _sorted_domain_tuple(value)

    @field_validator(
        "required_metrics",
        "missing_inputs",
        "conflicted_inputs",
        "incompatible_inputs",
        "insufficient_history_inputs",
        "input_observation_ids",
        "input_metric_ids",
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "EvidenceReadinessSnapshot":
        if self.deterministic_id is None:
            from .identifiers import deterministic_readiness_id, readiness_snapshot_identity

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_readiness_id(readiness_snapshot_identity(self)),
            )
        return self


__all__ = [
    "AgeDimension",
    "DomainAgeEntry",
    "DomainConflictEntry",
    "DomainCoverageEntry",
    "DomainCoverageSnapshot",
    "DomainCoverageState",
    "DomainMissingnessEntry",
    "DomainRequirement",
    "EvidenceAgeAlignment",
    "EvidenceConflictSummary",
    "EvidenceMissingnessSummary",
    "EvidenceReadinessSnapshot",
    "InputSufficiencyResult",
    "MissingnessCategory",
    "OperationRequirementPolicy",
    "ReportingPeriodAlignment",
    "ReportingPeriodEntry",
    "StructuralState",
]
