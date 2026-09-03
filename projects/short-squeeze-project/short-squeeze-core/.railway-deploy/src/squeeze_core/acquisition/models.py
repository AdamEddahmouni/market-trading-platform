from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AcquisitionPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    PREREGISTERED = "PREREGISTERED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


class DiscoverySourceClass(StrEnum):
    ORIGINAL_PLATFORM_EXPORT = "ORIGINAL_PLATFORM_EXPORT"
    ORIGINAL_PLATFORM_SCREENSHOT = "ORIGINAL_PLATFORM_SCREENSHOT"
    ORIGINAL_PLATFORM_LOG = "ORIGINAL_PLATFORM_LOG"
    ARCHIVED_PROVIDER_RESPONSE = "ARCHIVED_PROVIDER_RESPONSE"
    ARCHIVED_MARKET_SCANNER = "ARCHIVED_MARKET_SCANNER"
    PUBLIC_MARKET_EVENT_FEED = "PUBLIC_MARKET_EVENT_FEED"
    PUBLIC_NEWS_FEED = "PUBLIC_NEWS_FEED"
    MANUAL_RESEARCH_LEAD = "MANUAL_RESEARCH_LEAD"
    SYNTHETIC_TEST_INPUT = "SYNTHETIC_TEST_INPUT"


class ArtifactClassification(StrEnum):
    PUBLIC_HISTORICAL_SOURCE = "PUBLIC_HISTORICAL_SOURCE"
    LOCAL_HISTORICAL_ARTIFACT = "LOCAL_HISTORICAL_ARTIFACT"
    SANITIZED_HISTORICAL_FIXTURE = "SANITIZED_HISTORICAL_FIXTURE"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"
    DERIVED_NORMALIZED_ARTIFACT = "DERIVED_NORMALIZED_ARTIFACT"
    DERIVED_CURATED_CASE = "DERIVED_CURATED_CASE"
    MIXED_PROVENANCE = "MIXED_PROVENANCE"
    RESTRICTED_LOCAL_ARTIFACT = "RESTRICTED_LOCAL_ARTIFACT"


class HistoricalOrCurrent(StrEnum):
    HISTORICAL = "HISTORICAL"
    CURRENT = "CURRENT"


class IdentityState(StrEnum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    CONFLICTED = "CONFLICTED"
    UNRESOLVED = "UNRESOLVED"


class EvidenceSufficiencyState(StrEnum):
    SUFFICIENT_FOR_PHASE_3A = "SUFFICIENT_FOR_PHASE_3A"
    SUFFICIENT_FOR_PHASE_3B_OUTCOME_ONLY = "SUFFICIENT_FOR_PHASE_3B_OUTCOME_ONLY"
    SUFFICIENT_FOR_REGISTRY_ONLY = "SUFFICIENT_FOR_REGISTRY_ONLY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    CONFLICTED = "CONFLICTED"
    UNUSABLE = "UNUSABLE"


class ExclusionCode(StrEnum):
    OUTSIDE_PREREGISTERED_DATE_RANGE = "OUTSIDE_PREREGISTERED_DATE_RANGE"
    OUTSIDE_PREREGISTERED_POPULATION = "OUTSIDE_PREREGISTERED_POPULATION"
    DUPLICATE_SYMBOL = "DUPLICATE_SYMBOL"
    DUPLICATE_DISCOVERY = "DUPLICATE_DISCOVERY"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    DETECTION_BOUNDARY_UNRESOLVED = "DETECTION_BOUNDARY_UNRESOLVED"
    MARKET_DATA_UNAVAILABLE = "MARKET_DATA_UNAVAILABLE"
    NO_COMPLETED_BAR_AT_BOUNDARY = "NO_COMPLETED_BAR_AT_BOUNDARY"
    DISCOVERY_PROVENANCE_MISSING = "DISCOVERY_PROVENANCE_MISSING"
    SOURCE_ARTIFACT_MISSING = "SOURCE_ARTIFACT_MISSING"
    SOURCE_ARTIFACT_HASH_MISMATCH = "SOURCE_ARTIFACT_HASH_MISMATCH"
    OUTCOME_LEAKAGE_DETECTED = "OUTCOME_LEAKAGE_DETECTED"
    OUTCOME_AWARE_SELECTION_SUSPECTED = "OUTCOME_AWARE_SELECTION_SUSPECTED"
    POST_EVENT_SOURCE_ONLY = "POST_EVENT_SOURCE_ONLY"
    MODERN_DATA_MISREPRESENTED_AS_HISTORICAL = "MODERN_DATA_MISREPRESENTED_AS_HISTORICAL"
    PROVIDER_SCOPE_UNRESOLVED = "PROVIDER_SCOPE_UNRESOLVED"
    CORPORATE_ACTION_UNRESOLVED = "CORPORATE_ACTION_UNRESOLVED"
    SYMBOL_REUSE_UNRESOLVED = "SYMBOL_REUSE_UNRESOLVED"
    ACQUISITION_PLAN_NOT_PREREGISTERED = "ACQUISITION_PLAN_NOT_PREREGISTERED"
    CASE_REQUIRES_FABRICATED_EVIDENCE = "CASE_REQUIRES_FABRICATED_EVIDENCE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class BoundaryRule(StrEnum):
    FIRST_OBJECTIVE_DISCOVERY_TIMESTAMP = "FIRST_OBJECTIVE_DISCOVERY_TIMESTAMP"
    FIRST_ELIGIBLE_COMPLETED_BAR_AT_OR_AFTER_DISCOVERY = "FIRST_ELIGIBLE_COMPLETED_BAR_AT_OR_AFTER_DISCOVERY"
    ORIGINAL_PLATFORM_SURFACED_TIMESTAMP = "ORIGINAL_PLATFORM_SURFACED_TIMESTAMP"
    MANUALLY_RECONSTRUCTED_WITH_EVIDENCE = "MANUALLY_RECONSTRUCTED_WITH_EVIDENCE"
    MAXIMUM_LATER_RETURN = "MAXIMUM_LATER_RETURN"


class CurationStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    ARTIFACTS_CAPTURED = "ARTIFACTS_CAPTURED"
    NORMALIZED = "NORMALIZED"
    IDENTITY_REVIEWED = "IDENTITY_REVIEWED"
    ELIGIBILITY_REVIEWED = "ELIGIBILITY_REVIEWED"
    BOUNDARY_FROZEN = "BOUNDARY_FROZEN"
    EVALUATION_FROZEN = "EVALUATION_FROZEN"
    OUTCOME_CAPTURED = "OUTCOME_CAPTURED"
    RESEARCH_EVALUATED = "RESEARCH_EVALUATED"
    REVIEWED = "REVIEWED"
    PUBLISHED = "PUBLISHED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    EXCLUDED = "EXCLUDED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class _FrozenAcquisitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def assign_deterministic_id(self):
        if (
            "deterministic_id" in type(self).model_fields
            and getattr(self, "deterministic_id") is None
        ):
            from .identifiers import deterministic_acquisition_id

            identity = self.model_dump(
                mode="python",
                exclude={"deterministic_id", "informational_created_at"},
            )
            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_acquisition_id({"result_type": type(self).__name__, **identity}),
            )
        return self


class AcquisitionPlan(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    acquisition_plan_id: str
    plan_version: str
    created_from_policy_version: str
    research_question: str
    target_population: str
    date_range: tuple[date, date]
    market_session_scope: tuple[str, ...]
    symbol_universe_definition: str
    discovery_source_definitions: tuple[str, ...]
    maximum_case_count: int = Field(gt=0)
    minimum_case_count: int = Field(ge=0)
    sampling_method: str
    deduplication_policy: str
    boundary_policy: str
    inclusion_policy_version: str
    exclusion_policy_version: str
    provider_priority_policy_version: str
    artifact_requirements: tuple[str, ...]
    allowed_substitutions: tuple[str, ...]
    forbidden_substitutions: tuple[str, ...]
    outcome_blinding_state: str
    plan_status: AcquisitionPlanStatus
    informational_created_at: datetime | None = None
    deterministic_id: str | None = None

    @field_validator(
        "market_session_scope", "discovery_source_definitions", "artifact_requirements",
        "allowed_substitutions", "forbidden_substitutions",
    )
    @classmethod
    def sort_set_like_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("informational_created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_plan_bounds(self):
        if self.date_range[0] > self.date_range[1]:
            raise ValueError("plan date range is reversed")
        if self.minimum_case_count > self.maximum_case_count:
            raise ValueError("minimum case count exceeds maximum")
        return self


class DiscoveryRecord(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    discovery_record_id: str
    symbol_as_observed: str
    observed_at: datetime
    source_class: DiscoverySourceClass
    source_name: str
    source_artifact_id: str
    provider: str
    provider_scope: str
    query_or_filter_definition: str
    original_order: int = Field(ge=0)
    platform_surfaced_status: str
    discovery_reason: str
    fixture_classification: ArtifactClassification
    deterministic_id: str | None = None

    @field_validator("symbol_as_observed")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class ProviderProvenance(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    provider_provenance_id: str
    provider_name: str
    provider_product: str
    provider_dataset: str
    provider_scope: str
    access_method: str
    artifact_timestamp: datetime
    event_at: datetime | None = None
    observed_at: datetime | None = None
    effective_at: datetime | None = None
    published_at: datetime | None = None
    received_at: datetime | None = None
    timezone: str
    latency_status: str
    historical_or_current: HistoricalOrCurrent
    revision_status: str
    terms_or_license_reference: str | None = None
    source_artifact_id: str
    deterministic_id: str | None = None

    @field_validator(
        "artifact_timestamp", "event_at", "observed_at", "effective_at",
        "published_at", "received_at",
    )
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)


class ArtifactRecord(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    artifact_id: str
    file_name: str
    relative_path: str
    media_type: str
    byte_length: int = Field(ge=0)
    sha256: str
    source_class: DiscoverySourceClass
    provider_provenance_id: str
    fixture_classification: ArtifactClassification
    capture_method: str
    observed_at: datetime | None = None
    effective_at: datetime | None = None
    published_at: datetime | None = None
    content_status: str
    sensitive_content_status: str
    deterministic_id: str | None = None

    @field_validator("relative_path")
    @classmethod
    def require_stable_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute():
            raise ValueError("artifact path must be relative")
        if ".." in PurePosixPath(normalized).parts:
            raise ValueError("artifact path cannot escape intake root")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("sha256 must contain 64 hexadecimal characters")
        return normalized

    @field_validator("observed_at", "effective_at", "published_at")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)


class ArtifactManifest(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    manifest_id: str
    artifacts: tuple[ArtifactRecord, ...]
    deterministic_id: str | None = None

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(cls, value: tuple[ArtifactRecord, ...]) -> tuple[ArtifactRecord, ...]:
        identifiers = tuple(item.artifact_id for item in value)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate artifact ID")
        return tuple(sorted(value, key=lambda item: item.artifact_id))


class SourceManifest(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    manifest_id: str
    discovery_records: tuple[DiscoveryRecord, ...]
    provider_provenance: tuple[ProviderProvenance, ...]
    deterministic_id: str | None = None

    @field_validator("discovery_records")
    @classmethod
    def sort_discoveries(cls, value: tuple[DiscoveryRecord, ...]) -> tuple[DiscoveryRecord, ...]:
        identifiers = tuple(item.discovery_record_id for item in value)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate discovery record ID")
        return tuple(sorted(
            value,
            key=lambda item: (item.original_order, item.observed_at, item.discovery_record_id),
        ))

    @field_validator("provider_provenance")
    @classmethod
    def sort_provenance(
        cls, value: tuple[ProviderProvenance, ...]
    ) -> tuple[ProviderProvenance, ...]:
        identifiers = tuple(item.provider_provenance_id for item in value)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate provider provenance ID")
        return tuple(sorted(value, key=lambda item: item.provider_provenance_id))


class ArtifactVerificationResult(_FrozenAcquisitionModel):
    manifest_id: str
    valid: bool
    verified_artifact_ids: tuple[str, ...]
    diagnostic_codes: tuple[str, ...]
    deterministic_id: str | None = None

    @field_validator("verified_artifact_ids", "diagnostic_codes")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class EvidenceSufficiencyReview(_FrozenAcquisitionModel):
    state: EvidenceSufficiencyState
    present_domains: tuple[str, ...]
    missing_domains: tuple[str, ...]
    phase_3a_request_constructible: bool
    outcome_only_available: bool
    limitations: tuple[str, ...] = ()
    deterministic_id: str | None = None

    @field_validator("present_domains", "missing_domains", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class IdentityClaim(_FrozenAcquisitionModel):
    source_artifact_id: str
    symbol: str
    issuer_name: str | None = None
    exchange: str | None = None
    security_type: str | None = None
    provider_identifier: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    corporate_actions: tuple[str, ...] = ()
    symbol_reuse_risk: bool = False
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("corporate_actions")
    @classmethod
    def sort_actions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class IdentityResolution(_FrozenAcquisitionModel):
    state: IdentityState
    canonical_symbol: str | None = None
    issuer_name: str | None = None
    exchange: str | None = None
    security_type: str | None = None
    provider_identifiers: tuple[str, ...] = ()
    claims: tuple[IdentityClaim, ...]
    conflict_fields: tuple[str, ...] = ()
    risk_codes: tuple[str, ...] = ()
    deterministic_id: str | None = None

    @field_validator("provider_identifiers", "conflict_fields", "risk_codes")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("claims")
    @classmethod
    def sort_claims(cls, value: tuple[IdentityClaim, ...]) -> tuple[IdentityClaim, ...]:
        return tuple(sorted(value, key=lambda item: item.source_artifact_id))


class EligibilityContext(_FrozenAcquisitionModel):
    acquisition_plan_status: AcquisitionPlanStatus
    within_date_range: bool
    within_population: bool
    discovery_provenance_available: bool
    artifact_validation_passed: bool
    identity_resolution: IdentityResolution
    deterministic_boundary_available: bool
    objective_market_evidence_available: bool
    phase_3a_request_constructible: bool
    missing_domains: tuple[str, ...] = ()
    duplicate_symbol: bool = False
    duplicate_discovery: bool = False
    synthetic: bool = False

    @field_validator("missing_domains")
    @classmethod
    def sort_missing(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class EligibilityDecision(_FrozenAcquisitionModel):
    included: bool
    context: EligibilityContext
    satisfied_conditions: tuple[str, ...]
    missing_conditions: tuple[str, ...]
    exclusion_codes: tuple[ExclusionCode, ...]
    deterministic_id: str | None = None

    @field_validator("satisfied_conditions", "missing_conditions")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("exclusion_codes")
    @classmethod
    def sort_codes(cls, value: tuple[ExclusionCode, ...]) -> tuple[ExclusionCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class BoundaryEvidence(_FrozenAcquisitionModel):
    timestamp: datetime
    source_artifact_id: str
    completed_bar: bool = False
    original_platform_surfaced: bool = False
    manual_review_approved: bool = False
    deterministic_id: str | None = None

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class DetectionBoundaryFreeze(_FrozenAcquisitionModel):
    boundary_id: str
    case_attempt_id: str
    symbol: str
    boundary_timestamp: datetime | None = None
    boundary_timezone: str = "UTC"
    boundary_source: str | None = None
    boundary_source_artifact_id: str | None = None
    boundary_rule: BoundaryRule
    market_session: str = "UNSPECIFIED"
    eligible_bar_policy: str = "EXPLICIT"
    frozen_before_outcome_access: bool
    review_status: str
    diagnostic_codes: tuple[str, ...] = ()
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("boundary_timestamp")
    @classmethod
    def normalize_boundary_time(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @field_validator("diagnostic_codes")
    @classmethod
    def sort_diagnostics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class LeakageAuditRequest(_FrozenAcquisitionModel):
    case_attempt_id: str
    discovery_input_fields: tuple[str, ...]
    eligibility_input_fields: tuple[str, ...]
    boundary_input_fields: tuple[str, ...]
    evaluation_input_fields: tuple[str, ...]
    plan_frozen_at: datetime
    boundary_frozen_at: datetime
    evaluation_request_frozen_at: datetime
    evaluation_result_frozen_at: datetime
    outcome_captured_at: datetime
    discovery_manifest_id: str
    outcome_manifest_id: str
    plan_changed_after_outcome_access: bool
    outcome_aware_selection_indicator: bool
    maximum_return_selection_indicator: bool
    post_event_article_used_as_discovery_source: bool

    @field_validator(
        "plan_frozen_at", "boundary_frozen_at", "evaluation_request_frozen_at",
        "evaluation_result_frozen_at", "outcome_captured_at",
    )
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class LeakageAuditResult(_FrozenAcquisitionModel):
    case_attempt_id: str
    passed: bool
    publication_blocked: bool
    diagnostic_codes: tuple[str, ...]
    deterministic_id: str | None = None

    @field_validator("diagnostic_codes")
    @classmethod
    def sort_diagnostics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value == ("LEAKAGE_AUDIT_PASSED",):
            return value
        return tuple(sorted(set(value)))


class CaseAttempt(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    case_attempt_id: str
    acquisition_plan_id: str
    symbol: str
    exclusion_codes: tuple[ExclusionCode, ...] = ()
    limitations: tuple[str, ...] = ()
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class AcquisitionLedger(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    ledger_id: str
    attempts: tuple[CaseAttempt, ...]
    deterministic_id: str | None = None

    @field_validator("attempts")
    @classmethod
    def sort_attempts(cls, value: tuple[CaseAttempt, ...]) -> tuple[CaseAttempt, ...]:
        return tuple(sorted(value, key=lambda item: item.case_attempt_id))


class CuratedCaseBundle(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    curated_case_bundle_id: str
    acquisition_plan_id: str
    case_attempt_id: str
    symbol: str
    curation_status: CurationStatus
    fixture_classification: str
    discovery_record_id: str | None = None
    provider_provenance_ids: tuple[str, ...] = ()
    source_artifact_ids: tuple[str, ...] = ()
    raw_artifact_manifest_id: str | None = None
    normalized_artifact_manifest_id: str | None = None
    identity_resolution_id: str | None = None
    eligibility_decision_id: str | None = None
    detection_boundary_id: str | None = None
    leakage_audit_id: str | None = None
    leakage_audit_passed: bool | None = None
    phase_3a_request_id: str | None = None
    phase_3a_request_sha256: str | None = None
    phase_3a_result_id: str | None = None
    phase_3a_result_sha256: str | None = None
    outcome_capture_status: str = "NOT_CAPTURED"
    phase_3b_result_id: str | None = None
    review_decision: str = "PENDING"
    diagnostics: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    dependent_on_bundle_id: str | None = None
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "provider_provenance_ids", "source_artifact_ids", "diagnostics", "limitations"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class AcquisitionBatch(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    batch_id: str
    acquisition_plan: AcquisitionPlan
    source_manifest: SourceManifest
    artifact_manifest: ArtifactManifest
    ledger: AcquisitionLedger
    bundles: tuple[CuratedCaseBundle, ...]
    leakage_audit_requests: tuple[LeakageAuditRequest, ...] = ()
    leakage_audits: tuple[LeakageAuditResult, ...] = ()
    deterministic_id: str | None = None

    @field_validator("bundles")
    @classmethod
    def sort_bundles(
        cls, value: tuple[CuratedCaseBundle, ...]
    ) -> tuple[CuratedCaseBundle, ...]:
        return tuple(sorted(value, key=lambda item: item.case_attempt_id))

    @field_validator("leakage_audit_requests")
    @classmethod
    def sort_audit_requests(
        cls, value: tuple[LeakageAuditRequest, ...]
    ) -> tuple[LeakageAuditRequest, ...]:
        return tuple(sorted(value, key=lambda item: item.case_attempt_id))

    @field_validator("leakage_audits")
    @classmethod
    def sort_audits(
        cls, value: tuple[LeakageAuditResult, ...]
    ) -> tuple[LeakageAuditResult, ...]:
        return tuple(sorted(value, key=lambda item: item.case_attempt_id))


class LeakageAuditCollection(_FrozenAcquisitionModel):
    schema_version: str = "1.0.0"
    batch_id: str
    audits: tuple[LeakageAuditResult, ...]
    deterministic_id: str | None = None

    @field_validator("audits")
    @classmethod
    def sort_audits(
        cls, value: tuple[LeakageAuditResult, ...]
    ) -> tuple[LeakageAuditResult, ...]:
        return tuple(sorted(value, key=lambda item: item.case_attempt_id))


__all__ = [name for name in tuple(globals()) if not name.startswith("_")]
