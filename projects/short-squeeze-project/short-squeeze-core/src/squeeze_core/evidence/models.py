from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import Observation
from squeeze_core.contracts.validation import require_aware_utc


class CoverageDomain(StrEnum):
    CANDIDATE_SNAPSHOT = "CANDIDATE_SNAPSHOT"
    BORROW_FEE = "BORROW_FEE"
    BORROW_AVAILABILITY = "BORROW_AVAILABILITY"
    PUBLISHED_SHORT_INTEREST = "PUBLISHED_SHORT_INTEREST"
    SEC_FILINGS = "SEC_FILINGS"
    TRADING_HALTS = "TRADING_HALTS"
    NEWS = "NEWS"
    MARKET_BARS = "MARKET_BARS"
    TRADES = "TRADES"
    QUOTES = "QUOTES"


class CoverageState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    STALE = "STALE"
    DELAYED = "DELAYED"
    UNKNOWN_FRESHNESS = "UNKNOWN_FRESHNESS"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"
    PARTIAL = "PARTIAL"


class EvidenceDiagnosticCode(StrEnum):
    EVIDENCE_STALE_SOURCE = "EVIDENCE_STALE_SOURCE"
    EVIDENCE_DELAYED_SOURCE = "EVIDENCE_DELAYED_SOURCE"
    EVIDENCE_UNKNOWN_FRESHNESS = "EVIDENCE_UNKNOWN_FRESHNESS"
    EVIDENCE_MISSING_SOURCE_DOMAIN = "EVIDENCE_MISSING_SOURCE_DOMAIN"
    EVIDENCE_FIELD_CONFLICT = "EVIDENCE_FIELD_CONFLICT"
    EVIDENCE_DUPLICATE_CONFLICT = "EVIDENCE_DUPLICATE_CONFLICT"
    EVIDENCE_TEMPORAL_DIFFERENCE = "EVIDENCE_TEMPORAL_DIFFERENCE"
    EVIDENCE_EXCLUDED_AFTER_AS_OF = "EVIDENCE_EXCLUDED_AFTER_AS_OF"
    EVIDENCE_EXCLUDED_RECEIVED_AFTER_AS_OF = "EVIDENCE_EXCLUDED_RECEIVED_AFTER_AS_OF"
    EVIDENCE_INCOMPATIBLE_SEMANTICS = "EVIDENCE_INCOMPATIBLE_SEMANTICS"
    EVIDENCE_PARTIAL_COVERAGE = "EVIDENCE_PARTIAL_COVERAGE"
    EVIDENCE_SYMBOL_MISMATCH = "EVIDENCE_SYMBOL_MISMATCH"
    EVIDENCE_POLICY_EXCLUDED = "EVIDENCE_POLICY_EXCLUDED"
    EVIDENCE_SHORT_INTEREST_NOT_YET_PUBLISHED = (
        "EVIDENCE_SHORT_INTEREST_NOT_YET_PUBLISHED"
    )
    EVIDENCE_SHORT_INTEREST_NOT_YET_RECEIVED = (
        "EVIDENCE_SHORT_INTEREST_NOT_YET_RECEIVED"
    )
    EVIDENCE_SHORT_INTEREST_SETTLEMENT_ONLY = "EVIDENCE_SHORT_INTEREST_SETTLEMENT_ONLY"
    EVIDENCE_SHORT_INTEREST_STALE_REPORTING_PERIOD = (
        "EVIDENCE_SHORT_INTEREST_STALE_REPORTING_PERIOD"
    )
    EVIDENCE_SHORT_INTEREST_CORRECTION_AVAILABLE = (
        "EVIDENCE_SHORT_INTEREST_CORRECTION_AVAILABLE"
    )
    EVIDENCE_SHORT_INTEREST_REVISION_SUPERSEDES = (
        "EVIDENCE_SHORT_INTEREST_REVISION_SUPERSEDES"
    )
    EVIDENCE_SHORT_INTEREST_REVISION_NOT_YET_AVAILABLE = (
        "EVIDENCE_SHORT_INTEREST_REVISION_NOT_YET_AVAILABLE"
    )
    EVIDENCE_MISSING_PUBLISHED_SHORT_INTEREST = (
        "EVIDENCE_MISSING_PUBLISHED_SHORT_INTEREST"
    )
    EVIDENCE_SHORT_INTEREST_PROVIDER_CONFLICT = (
        "EVIDENCE_SHORT_INTEREST_PROVIDER_CONFLICT"
    )
    EVIDENCE_SHORT_INTEREST_TEMPORAL_DIFFERENCE = (
        "EVIDENCE_SHORT_INTEREST_TEMPORAL_DIFFERENCE"
    )
    EVIDENCE_SEC_FILING_NOT_YET_ACCEPTED = "EVIDENCE_SEC_FILING_NOT_YET_ACCEPTED"
    EVIDENCE_SEC_FILING_NOT_YET_RECEIVED = "EVIDENCE_SEC_FILING_NOT_YET_RECEIVED"
    EVIDENCE_SEC_FILING_UNKNOWN_AVAILABILITY = "EVIDENCE_SEC_FILING_UNKNOWN_AVAILABILITY"
    EVIDENCE_SEC_FILING_DATE_ONLY_AVAILABILITY = "EVIDENCE_SEC_FILING_DATE_ONLY_AVAILABILITY"
    EVIDENCE_SEC_FILING_AMENDMENT_AVAILABLE = "EVIDENCE_SEC_FILING_AMENDMENT_AVAILABLE"
    EVIDENCE_SEC_FILING_AMENDMENT_NOT_YET_AVAILABLE = "EVIDENCE_SEC_FILING_AMENDMENT_NOT_YET_AVAILABLE"
    EVIDENCE_SEC_FILING_DUPLICATE = "EVIDENCE_SEC_FILING_DUPLICATE"
    EVIDENCE_SEC_FILING_CONFLICT = "EVIDENCE_SEC_FILING_CONFLICT"
    EVIDENCE_SEC_FILING_TEMPORAL_DIFFERENCE = "EVIDENCE_SEC_FILING_TEMPORAL_DIFFERENCE"
    EVIDENCE_MISSING_SEC_FILINGS = "EVIDENCE_MISSING_SEC_FILINGS"
    EVIDENCE_SEC_FILING_PARTIAL_COVERAGE = "EVIDENCE_SEC_FILING_PARTIAL_COVERAGE"
    EVIDENCE_HALT_NOT_YET_PUBLISHED = "EVIDENCE_HALT_NOT_YET_PUBLISHED"
    EVIDENCE_HALT_NOT_YET_RECEIVED = "EVIDENCE_HALT_NOT_YET_RECEIVED"
    EVIDENCE_HALT_UNKNOWN_AVAILABILITY = "EVIDENCE_HALT_UNKNOWN_AVAILABILITY"
    EVIDENCE_HALT_ACTIVE = "EVIDENCE_HALT_ACTIVE"
    EVIDENCE_QUOTE_RESUMPTION_SCHEDULED = "EVIDENCE_QUOTE_RESUMPTION_SCHEDULED"
    EVIDENCE_QUOTES_RESUMED = "EVIDENCE_QUOTES_RESUMED"
    EVIDENCE_TRADE_RESUMPTION_SCHEDULED = "EVIDENCE_TRADE_RESUMPTION_SCHEDULED"
    EVIDENCE_TRADING_RESUMED = "EVIDENCE_TRADING_RESUMED"
    EVIDENCE_HALT_CONFLICT = "EVIDENCE_HALT_CONFLICT"
    EVIDENCE_HALT_TEMPORAL_DIFFERENCE = "EVIDENCE_HALT_TEMPORAL_DIFFERENCE"
    EVIDENCE_HALT_REVISION_AVAILABLE = "EVIDENCE_HALT_REVISION_AVAILABLE"
    EVIDENCE_HALT_REVISION_NOT_YET_AVAILABLE = "EVIDENCE_HALT_REVISION_NOT_YET_AVAILABLE"
    EVIDENCE_MISSING_TRADING_HALTS = "EVIDENCE_MISSING_TRADING_HALTS"
    EVIDENCE_HALT_PARTIAL_COVERAGE = "EVIDENCE_HALT_PARTIAL_COVERAGE"
    EVIDENCE_NEWS_NOT_YET_PUBLISHED = "EVIDENCE_NEWS_NOT_YET_PUBLISHED"
    EVIDENCE_NEWS_NOT_YET_AVAILABLE = "EVIDENCE_NEWS_NOT_YET_AVAILABLE"
    EVIDENCE_NEWS_NOT_YET_RECEIVED = "EVIDENCE_NEWS_NOT_YET_RECEIVED"
    EVIDENCE_NEWS_SYMBOL_NOT_ASSOCIATED = "EVIDENCE_NEWS_SYMBOL_NOT_ASSOCIATED"
    EVIDENCE_NEWS_UNKNOWN_AVAILABILITY = "EVIDENCE_NEWS_UNKNOWN_AVAILABILITY"
    EVIDENCE_NEWS_UPDATE_AVAILABLE = "EVIDENCE_NEWS_UPDATE_AVAILABLE"
    EVIDENCE_NEWS_UPDATE_NOT_YET_AVAILABLE = "EVIDENCE_NEWS_UPDATE_NOT_YET_AVAILABLE"
    EVIDENCE_NEWS_WITHDRAWAL_AVAILABLE = "EVIDENCE_NEWS_WITHDRAWAL_AVAILABLE"
    EVIDENCE_NEWS_DUPLICATE = "EVIDENCE_NEWS_DUPLICATE"
    EVIDENCE_NEWS_CONFLICT = "EVIDENCE_NEWS_CONFLICT"
    EVIDENCE_NEWS_SYNDICATION = "EVIDENCE_NEWS_SYNDICATION"
    EVIDENCE_MISSING_NEWS = "EVIDENCE_MISSING_NEWS"
    EVIDENCE_NEWS_PARTIAL_COVERAGE = "EVIDENCE_NEWS_PARTIAL_COVERAGE"
    EVIDENCE_BAR_NOT_YET_PUBLISHED = "EVIDENCE_BAR_NOT_YET_PUBLISHED"
    EVIDENCE_BAR_NOT_YET_RECEIVED = "EVIDENCE_BAR_NOT_YET_RECEIVED"
    EVIDENCE_BAR_UNKNOWN_AVAILABILITY = "EVIDENCE_BAR_UNKNOWN_AVAILABILITY"
    EVIDENCE_BAR_PARTIAL = "EVIDENCE_BAR_PARTIAL"
    EVIDENCE_BAR_COMPLETED = "EVIDENCE_BAR_COMPLETED"
    EVIDENCE_BAR_CORRECTION_AVAILABLE = "EVIDENCE_BAR_CORRECTION_AVAILABLE"
    EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE = "EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE"
    EVIDENCE_BAR_CONFLICT = "EVIDENCE_BAR_CONFLICT"
    EVIDENCE_BAR_INTERVAL_MISMATCH = "EVIDENCE_BAR_INTERVAL_MISMATCH"
    EVIDENCE_BAR_SESSION_MISMATCH = "EVIDENCE_BAR_SESSION_MISMATCH"
    EVIDENCE_BAR_EXPECTED_INTERVAL_MISSING = "EVIDENCE_BAR_EXPECTED_INTERVAL_MISSING"
    EVIDENCE_BAR_SESSION_CLOSED = "EVIDENCE_BAR_SESSION_CLOSED"
    EVIDENCE_BAR_OVERLAPPING_INTERVAL = "EVIDENCE_BAR_OVERLAPPING_INTERVAL"
    EVIDENCE_MISSING_MARKET_BARS = "EVIDENCE_MISSING_MARKET_BARS"
    EVIDENCE_MARKET_BARS_PARTIAL_COVERAGE = "EVIDENCE_MARKET_BARS_PARTIAL_COVERAGE"
    EVIDENCE_TRADE_QUOTE_NOT_YET_PUBLISHED = "EVIDENCE_TRADE_QUOTE_NOT_YET_PUBLISHED"
    EVIDENCE_TRADE_QUOTE_NOT_YET_RECEIVED = "EVIDENCE_TRADE_QUOTE_NOT_YET_RECEIVED"
    EVIDENCE_TRADE_QUOTE_FUTURE_EVENT = "EVIDENCE_TRADE_QUOTE_FUTURE_EVENT"
    EVIDENCE_TRADE_QUOTE_REVISION_AVAILABLE = "EVIDENCE_TRADE_QUOTE_REVISION_AVAILABLE"
    EVIDENCE_TRADE_QUOTE_REVISION_NOT_YET_AVAILABLE = "EVIDENCE_TRADE_QUOTE_REVISION_NOT_YET_AVAILABLE"
    EVIDENCE_TRADE_QUOTE_CONFLICT = "EVIDENCE_TRADE_QUOTE_CONFLICT"
    EVIDENCE_MISSING_TRADES = "EVIDENCE_MISSING_TRADES"
    EVIDENCE_MISSING_QUOTES = "EVIDENCE_MISSING_QUOTES"
    EVIDENCE_TRADES_PARTIAL_COVERAGE = "EVIDENCE_TRADES_PARTIAL_COVERAGE"
    EVIDENCE_QUOTES_PARTIAL_COVERAGE = "EVIDENCE_QUOTES_PARTIAL_COVERAGE"


class EvidenceSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ConflictClassification(StrEnum):
    VALUE_CONFLICT = "VALUE_CONFLICT"
    DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"
    TEMPORAL_DIFFERENCE = "TEMPORAL_DIFFERENCE"
    INCOMPATIBLE_SEMANTICS = "INCOMPATIBLE_SEMANTICS"


class EvidenceDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: EvidenceDiagnosticCode
    severity: EvidenceSeverity
    message: str
    observation_id: str | None = None
    domain: CoverageDomain | None = None


class SourceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: CoverageDomain
    state: CoverageState
    observation_ids: tuple[str, ...] = ()


class EvidenceConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conflict_id: str
    symbol: str
    semantic_field: str
    observation_ids: tuple[str, ...]
    values: tuple[Any, ...]
    units: tuple[str, ...]
    sources: tuple[str, ...]
    effective_timestamps: tuple[datetime, ...]
    received_timestamps: tuple[datetime, ...]
    absolute_difference: Decimal | None = None
    relative_difference: Decimal | None = None
    classification: ConflictClassification
    comparison_period: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    status: str = "UNRESOLVED"

    @field_validator("effective_timestamps", "received_timestamps")
    @classmethod
    def normalize_timestamps(cls, values: tuple[datetime, ...]) -> tuple[datetime, ...]:
        return tuple(require_aware_utc(value) for value in values)


class FreshnessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    live_count: int = Field(default=0, ge=0)
    delayed_count: int = Field(default=0, ge=0)
    historical_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    stale_count: int = Field(default=0, ge=0)


class CompletenessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    included_observation_count: int = Field(ge=0)
    excluded_observation_count: int = Field(ge=0)
    present_domain_count: int = Field(ge=0)
    missing_domain_count: int = Field(ge=0)


class ObservationAge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    availability_age_ms: int = Field(ge=0)
    event_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    reporting_period_age_days: int | None = Field(default=None, ge=0)
    filing_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    announcement_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    halt_event_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    resumption_event_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    publication_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    update_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    capture_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    interval_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )
    correction_age_ms: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )


class HaltState(StrEnum):
    NOT_OBSERVED = "NOT_OBSERVED"
    HALT_ANNOUNCED = "HALT_ANNOUNCED"
    HALTED = "HALTED"
    QUOTE_RESUMPTION_SCHEDULED = "QUOTE_RESUMPTION_SCHEDULED"
    QUOTES_RESUMED = "QUOTES_RESUMED"
    TRADE_RESUMPTION_SCHEDULED = "TRADE_RESUMPTION_SCHEDULED"
    TRADING_RESUMED = "TRADING_RESUMED"
    CANCELLED = "CANCELLED"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class HaltStateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: HaltState
    halt_event_keys: tuple[str, ...] = ()
    supporting_observation_ids: tuple[str, ...] = ()
    conflict_ids: tuple[str, ...] = ()


class RevisionRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: str
    prior_observation_id: str
    revision_observation_id: str
    status: str


class NewsRelationshipKind(StrEnum):
    REVISION = "REVISION"
    CORRECTION = "CORRECTION"
    WITHDRAWAL = "WITHDRAWAL"
    DELETION = "DELETION"
    SYNDICATED = "SYNDICATED"


class NewsRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: str
    kind: NewsRelationshipKind
    observation_ids: tuple[str, str]
    provider_record_ids: tuple[str, str]
    canonical_url: str | None = None


class PointInTimeEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str
    symbol: str
    as_of: datetime
    observations: tuple[Observation, ...]
    diagnostics: tuple[EvidenceDiagnostic, ...]
    source_coverage: tuple[SourceCoverage, ...]
    conflicts: tuple[EvidenceConflict, ...]
    freshness_summary: FreshnessSummary
    completeness_summary: CompletenessSummary
    observation_ages: tuple[ObservationAge, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    revision_relationships: tuple[RevisionRelationship, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    news_relationships: tuple[NewsRelationship, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    halt_state: HaltStateSummary | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    def hash_content(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude={"bundle_hash"})
