"""Frozen, deterministic contracts for Batch 07 operation-specific readiness.

These models express a strictly narrower question than the Batch 04 *global*
preflight: "can this frozen detection-context evidence be used for THIS exact
operation under explicitly stated constraints?" They never assert global
readiness, never carry an outcome/score/ranking/recommendation field, and reuse
the acquisition ``_FrozenAcquisitionModel`` base so identity is a UUIDv5 over
canonical JSON of frozen, pre-outcome inputs only.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from ..models import _FrozenAcquisitionModel, _aware_utc

SCHEMA_VERSION = "1.0.0"
OPERATION_READINESS_POLICY_VERSION = "phase_3d_operation_readiness_policy.v1"
# The Batch 06 resolution this batch consumes (docs/batch-06-*.md). Provenance only.
SEMANTIC_RESOLUTION_POLICY_VERSION = "phase_3d_ibkr_semantics_resolution.v1"
TIMESTAMP_UNCERTAINTY_POLICY = "bidirectional_1min_envelope.v1"
BAR_INTERVAL_SECONDS = 60


class AdmissibilityStatus(StrEnum):
    """Closed deterministic vocabulary. ``UNKNOWN`` is never collapsed into a FAIL;
    missing evidence is never treated as zero."""

    ADMISSIBLE = "ADMISSIBLE"
    ADMISSIBLE_WITH_CONSTRAINTS = "ADMISSIBLE_WITH_CONSTRAINTS"
    BLOCKED_MISSING_SEMANTICS = "BLOCKED_MISSING_SEMANTICS"
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    BLOCKED_ALIGNMENT = "BLOCKED_ALIGNMENT"
    BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Phase3ARequestReadiness(StrEnum):
    PHASE3A_REQUEST_READY = "PHASE3A_REQUEST_READY"
    PHASE3A_REQUEST_BLOCKED = "PHASE3A_REQUEST_BLOCKED"
    PHASE3A_REQUEST_SCHEMA_REVIEW_REQUIRED = "PHASE3A_REQUEST_SCHEMA_REVIEW_REQUIRED"


class OperationKind(StrEnum):
    PRICE_ONLY_RATIO = "PRICE_ONLY_RATIO"
    PRICE_ONLY_ABSOLUTE_LEVEL = "PRICE_ONLY_ABSOLUTE_LEVEL"
    MARKET_BAR_AVAILABILITY = "MARKET_BAR_AVAILABILITY"
    VOLUME_DEPENDENT = "VOLUME_DEPENDENT"
    EVIDENCE_META = "EVIDENCE_META"
    NON_MARKET_BAR_DOMAIN = "NON_MARKET_BAR_DOMAIN"


class ReasonCode(StrEnum):
    """Deterministic reason codes explaining an admissibility status."""

    MARKET_BARS_PRESENT = "MARKET_BARS_PRESENT"
    FINAL_BAR_DEFINITELY_COMPLETED = "FINAL_BAR_DEFINITELY_COMPLETED"
    PRICE_RATIO_SPLIT_INVARIANT = "PRICE_RATIO_SPLIT_INVARIANT"
    DIVIDEND_ADJUSTMENT_NOT_APPLIED = "DIVIDEND_ADJUSTMENT_NOT_APPLIED"
    BOUNDARY_BARS_MUST_BE_COMPLETED = "BOUNDARY_BARS_MUST_BE_COMPLETED"
    PRICE_ABSOLUTE_LEVEL_CORPORATE_ACTION_UNCONFIRMED = (
        "PRICE_ABSOLUTE_LEVEL_CORPORATE_ACTION_UNCONFIRMED"
    )
    VOLUME_UNIT_UNRESOLVED = "VOLUME_UNIT_UNRESOLVED"
    VOLUME_CORPORATE_ACTION_UNKNOWN = "VOLUME_CORPORATE_ACTION_UNKNOWN"
    VOLUME_FILTER_STATIONARITY_UNPROVEN = "VOLUME_FILTER_STATIONARITY_UNPROVEN"
    TIMESTAMP_BOUNDARY_UNKNOWN = "TIMESTAMP_BOUNDARY_UNKNOWN"
    TIMESTAMP_ALIGNMENT_STRADDLE = "TIMESTAMP_ALIGNMENT_STRADDLE"
    SESSION_COMPLETENESS_UNEVIDENCED = "SESSION_COMPLETENESS_UNEVIDENCED"
    PROVIDER_FILTERED_FEED = "PROVIDER_FILTERED_FEED"
    REQUIRED_DOMAIN_ABSENT = "REQUIRED_DOMAIN_ABSENT"
    OPERATION_INDEPENDENT_OF_THIS_EVIDENCE = "OPERATION_INDEPENDENT_OF_THIS_EVIDENCE"


class SemanticDependency(_FrozenAcquisitionModel):
    """Which unresolved/resolved IBKR semantic fields materially affect an operation.

    Purely declarative; no formula logic. A flag being ``True`` means the operation's
    correctness genuinely depends on that field -- not that the field happens to exist.
    """

    schema_version: str = SCHEMA_VERSION
    price_adjustment_absolute: bool = False
    price_adjustment_ratio: bool = False
    dividend_adjustment: bool = False
    volume_unit: bool = False
    volume_corporate_action: bool = False
    volume_filter_stationarity: bool = False
    timestamp_boundary: bool = False
    session_completeness: bool = False


class OperationDependency(_FrozenAcquisitionModel):
    """Declarative dependency contract for one Phase 2 operation or Phase 3A rule input."""

    schema_version: str = SCHEMA_VERSION
    operation: str = Field(min_length=1)
    kind: OperationKind
    required_domains: tuple[str, ...] = ()
    required_metric_names: tuple[str, ...] = ()
    requires_trailing_window: bool = False
    touches_detection_context_bars: bool = False
    semantic_dependency: SemanticDependency = SemanticDependency()

    @field_validator("required_domains", "required_metric_names")
    @classmethod
    def _sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


class OperationAdmissibility(_FrozenAcquisitionModel):
    """The admissibility verdict for one operation against the detection-context bars."""

    schema_version: str = SCHEMA_VERSION
    operation: str = Field(min_length=1)
    kind: OperationKind
    status: AdmissibilityStatus
    reason_codes: tuple[ReasonCode, ...] = ()
    constraints: tuple[str, ...] = ()

    @field_validator("reason_codes")
    @classmethod
    def _sort_reasons(cls, value: tuple[ReasonCode, ...]) -> tuple[ReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class TimestampUncertaintyEnvelope(_FrozenAcquisitionModel):
    """Explicit bidirectional interpretation of one bar timestamp; never mutates it."""

    schema_version: str = SCHEMA_VERSION
    event_timestamp: datetime
    bar_interval_seconds: int = Field(gt=0)
    # interpretation A: timestamp is interval START -> completion at t + interval
    # interpretation B: timestamp is interval END   -> completion at t
    earliest_possible_completion: datetime
    latest_possible_completion: datetime
    boundary: datetime
    definitely_completed_before_boundary: bool
    straddles_boundary: bool

    @field_validator(
        "event_timestamp",
        "earliest_possible_completion",
        "latest_possible_completion",
        "boundary",
    )
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class ArtifactCoverage(_FrozenAcquisitionModel):
    """Coverage facts from frozen provenance metadata only -- never OHLCV values."""

    schema_version: str = SCHEMA_VERSION
    requested_window_start: datetime
    requested_window_end: datetime
    observed_coverage_start: datetime
    observed_coverage_end: datetime
    bar_count: int = Field(ge=0)
    bar_interval: str = Field(min_length=1)
    max_possible_final_bar_completion: datetime
    gap_seconds_from_definitely_completed_to_boundary: int = Field(ge=0)

    @field_validator(
        "requested_window_start",
        "requested_window_end",
        "observed_coverage_start",
        "observed_coverage_end",
        "max_possible_final_bar_completion",
    )
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class Phase3ARuleDependencyRecord(_FrozenAcquisitionModel):
    """Dependency-readiness for one Phase 3A rule. Never a PASS/FAIL evaluation."""

    schema_version: str = SCHEMA_VERSION
    rule_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    required_domains: tuple[str, ...] = ()
    required_metric_names: tuple[str, ...] = ()
    required_semantic_fields: tuple[str, ...] = ()
    touches_detection_context_bars: bool
    admissibility_status: AdmissibilityStatus
    reason_codes: tuple[ReasonCode, ...] = ()

    @field_validator("required_domains", "required_metric_names", "required_semantic_fields")
    @classmethod
    def _sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("reason_codes")
    @classmethod
    def _sort_reasons(cls, value: tuple[ReasonCode, ...]) -> tuple[ReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class CaseOperationReadiness(_FrozenAcquisitionModel):
    """Per-case readiness record. Contains no outcome, score, ranking, or recommendation.

    ``association_id`` and ``deterministic_id`` are UUIDv5 over frozen pre-outcome inputs.
    """

    schema_version: str = SCHEMA_VERSION
    operation_readiness_policy_version: str = OPERATION_READINESS_POLICY_VERSION
    semantic_resolution_policy_version: str = SEMANTIC_RESOLUTION_POLICY_VERSION
    case_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    frozen_boundary_id: str = Field(min_length=1)
    detection_context_artifact_sha256: str = Field(min_length=64, max_length=64)
    artifact_byte_length: int = Field(ge=0)
    coverage: ArtifactCoverage
    bar_interval: str = Field(min_length=1)
    timestamp_representation: str
    timestamp_interval_semantics: str
    timestamp_uncertainty_policy: str
    price_adjustment_semantics: str
    volume_adjustment_semantics: str
    volume_unit_semantics: str
    session_request_policy: str
    provider_filtering_disclosure: str
    final_bar_uncertainty: TimestampUncertaintyEnvelope
    price_operation_readiness: tuple[OperationAdmissibility, ...]
    volume_operation_readiness: tuple[OperationAdmissibility, ...]
    temporal_alignment_readiness: OperationAdmissibility
    phase2_metric_readiness: tuple[OperationAdmissibility, ...]
    phase3a_rule_dependency_readiness: tuple[Phase3ARuleDependencyRecord, ...]
    phase3a_request_readiness: Phase3ARequestReadiness
    blocking_reason_codes: tuple[ReasonCode, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    supporting_semantic_resolution_ids: tuple[str, ...] = ()
    association_id: str | None = None
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("detection_context_artifact_sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("sha256 must be 64 hexadecimal characters")
        return normalized

    @field_validator("blocking_reason_codes")
    @classmethod
    def _sort_reasons(cls, value: tuple[ReasonCode, ...]) -> tuple[ReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator("supporting_evidence_ids", "supporting_semantic_resolution_ids")
    @classmethod
    def _sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("phase3a_rule_dependency_readiness")
    @classmethod
    def _sort_rules(
        cls, value: tuple[Phase3ARuleDependencyRecord, ...]
    ) -> tuple[Phase3ARuleDependencyRecord, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))


class ReadinessFrequencySummary(_FrozenAcquisitionModel):
    """Descriptive counts with explicit denominators -- never accuracy/performance."""

    schema_version: str = SCHEMA_VERSION
    label: str = Field(min_length=1)
    denominator: int = Field(ge=0)
    counts: tuple[tuple[str, int], ...] = ()

    @field_validator("counts")
    @classmethod
    def _sort_counts(cls, value: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(value, key=lambda item: item[0]))


class OperationReadinessReport(_FrozenAcquisitionModel):
    """Top-level Batch 07 readiness report. Global preflight verdict is echoed unchanged."""

    schema_version: str = SCHEMA_VERSION
    operation_readiness_policy_version: str = OPERATION_READINESS_POLICY_VERSION
    semantic_resolution_policy_version: str = SEMANTIC_RESOLUTION_POLICY_VERSION
    timestamp_uncertainty_policy: str = TIMESTAMP_UNCERTAINTY_POLICY
    frozen_boundary_id: str = Field(min_length=1)
    global_preflight_verdict: str = "PREFLIGHT_REJECTED"
    global_preflight_unchanged: bool = True
    operation_dependency_matrix: tuple[OperationDependency, ...]
    phase3a_rule_dependency_matrix: tuple[Phase3ARuleDependencyRecord, ...]
    cases: tuple[CaseOperationReadiness, ...]
    summaries: tuple[ReadinessFrequencySummary, ...] = ()
    deterministic_id: str | None = None

    @field_validator("phase3a_rule_dependency_matrix")
    @classmethod
    def _sort_rules(
        cls, value: tuple[Phase3ARuleDependencyRecord, ...]
    ) -> tuple[Phase3ARuleDependencyRecord, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @model_validator(mode="after")
    def _no_outcome_leak(self) -> "OperationReadinessReport":
        # Structural guard: this report type has no field that could carry an outcome.
        forbidden = {"outcome", "score", "rank", "ranking", "recommendation", "pnl", "return"}
        present = set(type(self).model_fields)
        overlap = forbidden & present
        if overlap:
            raise ValueError(f"outcome-like fields are forbidden: {sorted(overlap)}")
        return self


__all__ = [
    "SCHEMA_VERSION",
    "OPERATION_READINESS_POLICY_VERSION",
    "SEMANTIC_RESOLUTION_POLICY_VERSION",
    "TIMESTAMP_UNCERTAINTY_POLICY",
    "BAR_INTERVAL_SECONDS",
    "AdmissibilityStatus",
    "Phase3ARequestReadiness",
    "OperationKind",
    "ReasonCode",
    "SemanticDependency",
    "OperationDependency",
    "OperationAdmissibility",
    "TimestampUncertaintyEnvelope",
    "ArtifactCoverage",
    "Phase3ARuleDependencyRecord",
    "CaseOperationReadiness",
    "ReadinessFrequencySummary",
    "OperationReadinessReport",
]
