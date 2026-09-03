"""Frozen, deterministic contracts for the Batch 08 Phase 3A request/result freeze.

These models record *what was frozen*, never an outcome of the underlying trade. There is
no score, rank, recommendation, target, or P&L field anywhere, and a structural validator
refuses any such field name. Identity is a UUIDv5 over canonical JSON of frozen
pre-outcome inputs only, reusing the acquisition ``_FrozenAcquisitionModel`` base.

Rule outcomes recorded here are *always* produced by the existing Phase 3A evaluator; no
model in this module can construct one, and nothing here assigns PASS/FAIL/UNKNOWN.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from ..models import _FrozenAcquisitionModel, _aware_utc

SCHEMA_VERSION = "1.0.0"

#: Batch 08's own policy version. Bumping it changes every request/result identity.
FREEZE_POLICY_VERSION = "phase_3d_phase3a_freeze_policy.v1"

#: The unchanged Batch 04 global preflight verdict, echoed into every record.
GLOBAL_PREFLIGHT_VERDICT = "PREFLIGHT_REJECTED"

#: Frozen Phase 3A policy/evaluation versions (cross-checked against the policy file).
PHASE3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
PHASE3A_EVALUATION_VERSION = "candidate_evaluation.v1"

#: The canonical Phase 2 metric this batch is authorised to construct.
ADMISSIBLE_METRIC_NAME = "PERCENTAGE_RETURN"

#: Batch 05 request names. Only the first may ever be opened for bar values.
DETECTION_CONTEXT_REQUEST = "DETECTION_CONTEXT_PRECEDING_24H"
FORWARD_REQUEST = "FROZEN_FORWARD_24H"


class ReceiptModelingPolicy(StrEnum):
    """How an observation's ``received_timestamp`` is modelled for the replay.

    Declared explicitly because the point-in-time engine gates on receipt and the
    application's real local receipt is after the frozen boundary (see
    docs/batch-08-phase3a-request-result-freeze-plan.md Section 8).
    """

    #: Primary: receipt is the conservative provider-availability instant of the last
    #: included bar (``max(label) + one interval``).
    PROVIDER_AVAILABILITY_AS_RECEIPT = "PROVIDER_AVAILABILITY_AS_RECEIPT.v1"
    #: Disclosed sensitivity: receipt is the real Batch 05 retrieval completion time.
    LOCAL_RETRIEVAL_RECEIPT = "LOCAL_RETRIEVAL_RECEIPT.v1"


class TimestampInterpretation(StrEnum):
    """Which end of the interval a bar's label is taken to mean.

    Both readings are evaluated; the metric value is invariant between them (proved by a
    committed test), so declaring one is a serialization convention, not a choice of
    answer.
    """

    LABEL_IS_INTERVAL_START = "LABEL_IS_INTERVAL_START"
    LABEL_IS_INTERVAL_END = "LABEL_IS_INTERVAL_END"


class FreezeStatus(StrEnum):
    """Per-case freeze status. A case is retained even when it cannot be frozen."""

    REQUEST_AND_RESULT_FROZEN = "REQUEST_AND_RESULT_FROZEN"
    REQUEST_FROZEN_RESULT_FAILED = "REQUEST_FROZEN_RESULT_FAILED"
    REQUEST_CONSTRUCTION_FAILED = "REQUEST_CONSTRUCTION_FAILED"


class BlockingReasonCode(StrEnum):
    """Why a rule received no substantive evidence. Never an outcome."""

    ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07 = "ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07"
    VOLUME_SEMANTICS_BLOCKED_BY_BATCH07 = "VOLUME_SEMANTICS_BLOCKED_BY_BATCH07"
    REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE = "REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE"
    EVIDENCE_META_RULE_NOT_BAR_DEPENDENT = "EVIDENCE_META_RULE_NOT_BAR_DEPENDENT"
    NO_DETECTION_TIME_EVIDENCE_EXISTS = "NO_DETECTION_TIME_EVIDENCE_EXISTS"


class ObservationSupplyPolicy(StrEnum):
    """Which definitely-completed bars are attached to the request itself.

    The existing point-in-time evidence builder's conflict detection is superlinear and
    does not scale to the ~1,200 bars an artifact contains; that engine is not modified.
    The metric is still computed over the *full* admissible window (the metric path is
    linear), so this bound affects only the observation-count a bar-availability rule
    reports -- never a rule outcome, and never the metric value.
    """

    #: Exactly the observations the admissible percentage metric consumed.
    ADMISSIBLE_METRIC_BOUNDARY_BARS = "ADMISSIBLE_METRIC_BOUNDARY_BARS"
    #: Every definitely-completed bar (used by small synthetic fixtures).
    ALL_DEFINITELY_COMPLETED_BARS = "ALL_DEFINITELY_COMPLETED_BARS"


class TemporalSelection(_FrozenAcquisitionModel):
    """The definitely-completed bar window actually used. Carries no price or volume."""

    schema_version: str = SCHEMA_VERSION
    timestamp_uncertainty_policy: str = Field(min_length=1)
    timestamp_interpretation: TimestampInterpretation
    observation_supply_policy: ObservationSupplyPolicy
    bar_interval: str = Field(min_length=1)
    bar_interval_seconds: int = Field(gt=0)
    boundary: datetime
    first_included_label: datetime
    last_included_label: datetime
    last_included_latest_possible_completion: datetime
    #: Definitely-completed bars observed in the artifact.
    included_bar_count: int = Field(ge=0)
    #: Definitely-completed bars actually attached to the Phase 3A request.
    supplied_observation_count: int = Field(ge=0)
    #: Bars the metric was computed over (the full admissible window).
    metric_window_bar_count: int = Field(ge=0)
    excluded_straddling_bar_count: int = Field(ge=0)
    excluded_post_boundary_bar_count: int = Field(ge=0)
    deterministic_id: str | None = None

    @field_validator(
        "boundary",
        "first_included_label",
        "last_included_label",
        "last_included_latest_possible_completion",
    )
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]


class EvidenceAssociation(_FrozenAcquisitionModel):
    """Binds one frozen case to one frozen detection-context artifact.

    Forward-artifact identity is recorded by hash/length only, proving it was left
    untouched; no forward OHLCV field exists on this model.
    """

    schema_version: str = SCHEMA_VERSION
    freeze_policy_version: str = FREEZE_POLICY_VERSION
    case_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    boundary_id: str = Field(min_length=1)
    boundary_time: datetime
    detection_context_request_name: str = DETECTION_CONTEXT_REQUEST
    detection_context_artifact_name: str = Field(min_length=1)
    detection_context_artifact_sha256: str = Field(min_length=64, max_length=64)
    detection_context_artifact_byte_length: int = Field(ge=0)
    forward_artifact_name: str = Field(min_length=1)
    forward_artifact_sha256: str = Field(min_length=64, max_length=64)
    forward_artifact_byte_length: int = Field(ge=0)
    forward_artifact_status: str = GLOBAL_PREFLIGHT_VERDICT
    forward_ohlcv_accessed: bool = False
    global_preflight_status: str = GLOBAL_PREFLIGHT_VERDICT
    batch07_readiness_record_id: str = Field(min_length=1)
    batch07_association_id: str = Field(min_length=1)
    batch07_request_readiness: str = Field(min_length=1)
    batch07_temporal_alignment_status: str = Field(min_length=1)
    price_adjustment_semantics: str = Field(min_length=1)
    observed_coverage_start: datetime
    observed_coverage_end: datetime
    observed_bar_count: int = Field(ge=0)
    association_id: str | None = None
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "detection_context_artifact_sha256", "forward_artifact_sha256"
    )
    @classmethod
    def _sha(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("sha256 must be 64 hexadecimal characters")
        return normalized

    @field_validator("boundary_time", "observed_coverage_start", "observed_coverage_end")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _forward_untouched(self) -> "EvidenceAssociation":
        if self.forward_ohlcv_accessed:
            raise ValueError("forward OHLCV must never be accessed")
        return self


class FrozenArtifactRef(_FrozenAcquisitionModel):
    """Serialized-bytes identity of one frozen artifact."""

    schema_version: str = SCHEMA_VERSION
    artifact_kind: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_length: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("sha256 must be 64 hexadecimal characters")
        return normalized


class RuleOutcomeRecord(_FrozenAcquisitionModel):
    """One rule's evaluator-produced outcome plus the inputs that supported it.

    ``outcome`` is copied verbatim from the existing evaluator's ``RuleEvaluationResult``.
    Nothing in this package computes or overrides it.
    """

    schema_version: str = SCHEMA_VERSION
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    category: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    explanation_code: str = Field(min_length=1)
    rule_result_id: str = Field(min_length=1)
    supporting_observation_ids: tuple[str, ...] = ()
    supporting_metric_ids: tuple[str, ...] = ()
    supporting_readiness_ids: tuple[str, ...] = ()
    batch07_admissibility_status: str = Field(min_length=1)
    blocking_reason_codes: tuple[BlockingReasonCode, ...] = ()

    @field_validator(
        "supporting_observation_ids", "supporting_metric_ids", "supporting_readiness_ids"
    )
    @classmethod
    def _sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("blocking_reason_codes")
    @classmethod
    def _sorted_reasons(
        cls, value: tuple[BlockingReasonCode, ...]
    ) -> tuple[BlockingReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class CaseFreezeRecord(_FrozenAcquisitionModel):
    """The per-case Batch 08 freeze record. No outcome, score, rank, or recommendation."""

    schema_version: str = SCHEMA_VERSION
    freeze_policy_version: str = FREEZE_POLICY_VERSION
    phase3a_policy_version: str = PHASE3A_POLICY_VERSION
    phase3a_evaluation_version: str = PHASE3A_EVALUATION_VERSION
    receipt_modeling_policy: ReceiptModelingPolicy
    freeze_status: FreezeStatus
    case_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    boundary_id: str = Field(min_length=1)
    boundary_time: datetime
    batch07_readiness_record_id: str = Field(min_length=1)
    detection_context_artifact_name: str = Field(min_length=1)
    detection_context_artifact_sha256: str = Field(min_length=64, max_length=64)
    detection_context_artifact_byte_length: int = Field(ge=0)
    global_preflight_status: str = GLOBAL_PREFLIGHT_VERDICT
    temporal_selection: TemporalSelection
    evidence_association_id: str = Field(min_length=1)
    admissible_evidence_ids: tuple[str, ...] = ()
    blocked_evidence_dependencies: tuple[str, ...] = ()
    metric_ids: tuple[str, ...] = ()
    readiness_ids: tuple[str, ...] = ()
    phase3a_request_id: str = Field(min_length=1)
    phase3a_request_artifact: FrozenArtifactRef
    phase3a_result_id: str = Field(min_length=1)
    phase3a_result_artifact: FrozenArtifactRef
    candidate_evaluation_id: str = Field(min_length=1)
    rule_outcomes: tuple[RuleOutcomeRecord, ...]
    leakage_audit_status: str = Field(min_length=1)
    leakage_audit_diagnostic_codes: tuple[str, ...] = ()
    blocking_reason_codes: tuple[BlockingReasonCode, ...] = ()
    outcome_accessed: bool = False
    forward_ohlcv_accessed: bool = False
    phase3b_published: bool = False
    phase3e_started: bool = False
    deterministic_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("boundary_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @field_validator("rule_outcomes")
    @classmethod
    def _ordered_rules(
        cls, value: tuple[RuleOutcomeRecord, ...]
    ) -> tuple[RuleOutcomeRecord, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @field_validator(
        "admissible_evidence_ids",
        "blocked_evidence_dependencies",
        "metric_ids",
        "readiness_ids",
    )
    @classmethod
    def _sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("blocking_reason_codes")
    @classmethod
    def _sorted_reasons(
        cls, value: tuple[BlockingReasonCode, ...]
    ) -> tuple[BlockingReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @model_validator(mode="after")
    def _isolation_invariants(self) -> "CaseFreezeRecord":
        if self.outcome_accessed:
            raise ValueError("no outcome may be accessed in Batch 08")
        if self.forward_ohlcv_accessed:
            raise ValueError("forward OHLCV must never be accessed")
        if self.phase3b_published:
            raise ValueError("Batch 08 must not publish Phase 3B")
        if self.phase3e_started:
            raise ValueError("Batch 08 must not begin Phase 3E")
        return self


class OutcomeCount(_FrozenAcquisitionModel):
    """A descriptive count with an explicit denominator. Never a performance measure."""

    schema_version: str = SCHEMA_VERSION
    label: str = Field(min_length=1)
    denominator: int = Field(ge=0)
    counts: tuple[tuple[str, int], ...] = ()

    @field_validator("counts")
    @classmethod
    def _sorted(cls, value: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(value, key=lambda item: item[0]))


class RuleOutcomeMatrixRow(_FrozenAcquisitionModel):
    """One rule's outcome distribution across the 13 cases, plus its evidence profile."""

    schema_version: str = SCHEMA_VERSION
    rule_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    batch07_admissibility_status: str = Field(min_length=1)
    outcomes_by_case: tuple[tuple[str, str], ...] = ()
    outcome_counts: tuple[tuple[str, int], ...] = ()
    evidence_used: bool = False
    metric_used: bool = False
    readiness_used: bool = False
    blocking_reason_codes: tuple[BlockingReasonCode, ...] = ()

    @field_validator("outcomes_by_case", "outcome_counts")
    @classmethod
    def _sorted_pairs(cls, value):
        return tuple(sorted(value, key=lambda item: str(item[0])))

    @field_validator("blocking_reason_codes")
    @classmethod
    def _sorted_reasons(
        cls, value: tuple[BlockingReasonCode, ...]
    ) -> tuple[BlockingReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class PublicationReadinessPreview(_FrozenAcquisitionModel):
    """Answers only whether a *future* Phase 3B revision *could* reference these paths.

    Publishes nothing, computes no outcome classification, and carries no label field.
    """

    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(min_length=1)
    has_frozen_phase3a_request: bool
    has_frozen_phase3a_result: bool
    leakage_audit_passed: bool
    outcome_complete: bool = False
    phase3b_publication_performed: bool = False
    referenceable_by_future_phase3b_revision: bool = False

    @model_validator(mode="after")
    def _never_publishes(self) -> "PublicationReadinessPreview":
        if self.phase3b_publication_performed:
            raise ValueError("the preview must never publish Phase 3B")
        if self.outcome_complete:
            raise ValueError("no case may be marked outcome-complete in Batch 08")
        return self


class SensitivitySummary(_FrozenAcquisitionModel):
    """Rule-outcome counts under an alternative receipt-modeling policy.

    Disclosed so the primary policy's influence is explicit; mints no request/result id.
    """

    schema_version: str = SCHEMA_VERSION
    receipt_modeling_policy: ReceiptModelingPolicy
    case_count: int = Field(ge=0)
    outcome_counts_over_case_rule_pairs: OutcomeCount
    rules_diverging_from_primary: tuple[str, ...] = ()

    @field_validator("rules_diverging_from_primary")
    @classmethod
    def _sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class FreezeReport(_FrozenAcquisitionModel):
    """Top-level sanitized Batch 08 report. Contains no OHLCV and no derived price."""

    schema_version: str = SCHEMA_VERSION
    freeze_policy_version: str = FREEZE_POLICY_VERSION
    phase3a_policy_version: str = PHASE3A_POLICY_VERSION
    phase3a_evaluation_version: str = PHASE3A_EVALUATION_VERSION
    receipt_modeling_policy: ReceiptModelingPolicy
    global_preflight_verdict: str = GLOBAL_PREFLIGHT_VERDICT
    global_preflight_unchanged: bool = True
    boundary_time: datetime
    requests_frozen: int = Field(ge=0)
    results_frozen: int = Field(ge=0)
    leakage_audits_passed: int = Field(ge=0)
    cases: tuple[CaseFreezeRecord, ...]
    rule_matrix: tuple[RuleOutcomeMatrixRow, ...]
    summaries: tuple[OutcomeCount, ...] = ()
    publication_readiness_preview: tuple[PublicationReadinessPreview, ...] = ()
    sensitivity: SensitivitySummary | None = None
    deterministic_id: str | None = None

    @field_validator("boundary_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @field_validator("rule_matrix")
    @classmethod
    def _ordered_rules(
        cls, value: tuple[RuleOutcomeMatrixRow, ...]
    ) -> tuple[RuleOutcomeMatrixRow, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @model_validator(mode="after")
    def _no_outcome_like_fields(self) -> "FreezeReport":
        forbidden = {"score", "rank", "ranking", "recommendation", "pnl", "target"}
        overlap = forbidden & set(type(self).model_fields)
        if overlap:
            raise ValueError(f"outcome-like fields are forbidden: {sorted(overlap)}")
        if not self.global_preflight_unchanged:
            raise ValueError("the Batch 04 global preflight must remain unchanged")
        if self.global_preflight_verdict != GLOBAL_PREFLIGHT_VERDICT:
            raise ValueError("the global preflight verdict must remain PREFLIGHT_REJECTED")
        return self


__all__ = [
    "SCHEMA_VERSION",
    "FREEZE_POLICY_VERSION",
    "GLOBAL_PREFLIGHT_VERDICT",
    "PHASE3A_POLICY_VERSION",
    "PHASE3A_EVALUATION_VERSION",
    "ADMISSIBLE_METRIC_NAME",
    "DETECTION_CONTEXT_REQUEST",
    "FORWARD_REQUEST",
    "BlockingReasonCode",
    "CaseFreezeRecord",
    "EvidenceAssociation",
    "FreezeReport",
    "FreezeStatus",
    "FrozenArtifactRef",
    "ObservationSupplyPolicy",
    "OutcomeCount",
    "PublicationReadinessPreview",
    "ReceiptModelingPolicy",
    "RuleOutcomeMatrixRow",
    "RuleOutcomeRecord",
    "SensitivitySummary",
    "TemporalSelection",
    "TimestampInterpretation",
]
