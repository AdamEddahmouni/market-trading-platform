"""Immutable OF-01 domain record schemas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .canonical import RECORD_PROFILE, record_hash_from_obj
from .errors import OF01Error, OF01ErrorCode
from .ids import validate_uuid

RECORD_SCHEMA_VERSION = 1

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_.:-]*$")


class ActorType(StrEnum):
    HUMAN = "HUMAN"
    CI = "CI"
    SCHEDULER = "SCHEDULER"
    SYSTEM = "SYSTEM"
    WORKFLOW = "WORKFLOW"
    AGENT = "AGENT"
    PROVIDER_EVENT = "PROVIDER_EVENT"
    RECONCILER = "RECONCILER"


class TriggerType(StrEnum):
    OPERATOR_REQUEST = "OPERATOR_REQUEST"
    SCHEDULE = "SCHEDULE"
    PULL_REQUEST = "PULL_REQUEST"
    WORKFLOW_RUN = "WORKFLOW_RUN"
    POLICY_DECISION = "POLICY_DECISION"
    PRIOR_RUN = "PRIOR_RUN"
    PROVIDER_EVENT = "PROVIDER_EVENT"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class ConsequenceProfile(StrEnum):
    C0_EPHEMERAL = "C0_EPHEMERAL"
    C1_OPERATIONAL = "C1_OPERATIONAL"
    C2_GOVERNED = "C2_GOVERNED"
    C3_EVIDENCE_CRITICAL = "C3_EVIDENCE_CRITICAL"
    C4_AUTHORITY_CRITICAL = "C4_AUTHORITY_CRITICAL"


class ReproducibilityClass(StrEnum):
    R5_BIT_EXACT = "R5_BIT_EXACT"
    R4_DETERMINISTIC_REPLAY = "R4_DETERMINISTIC_REPLAY"
    R3_INPUT_REPLAYABLE = "R3_INPUT_REPLAYABLE"
    R2_ATTRIBUTABLE_NONDETERMINISTIC = "R2_ATTRIBUTABLE_NONDETERMINISTIC"
    R1_OBSERVATION_ONLY = "R1_OBSERVATION_ONLY"
    R0_NON_REPRODUCIBLE_DECLARED = "R0_NON_REPRODUCIBLE_DECLARED"


class EvidenceStrength(StrEnum):
    E3_DOMAIN_ADMITTED = "E3_DOMAIN_ADMITTED"
    E2_GOVERNED_SYNTHETIC = "E2_GOVERNED_SYNTHETIC"
    E1_DIAGNOSTIC = "E1_DIAGNOSTIC"
    E0_UNDECLARED = "E0_UNDECLARED"


class InitiatorClass(StrEnum):
    HUMAN = "HUMAN"
    CI = "CI"
    SCHEDULER = "SCHEDULER"
    SYSTEM = "SYSTEM"
    WORKFLOW = "WORKFLOW"
    AGENT = "AGENT"
    PROVIDER_EVENT = "PROVIDER_EVENT"


class ProvenanceQualifier(StrEnum):
    NATIVE = "NATIVE"
    LEGACY_PARTIAL = "LEGACY_PARTIAL"
    RETROSPECTIVE_INDEX = "RETROSPECTIVE_INDEX"


class SensitivityClass(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"


class AttemptConcurrency(StrEnum):
    SEQUENTIAL = "SEQUENTIAL"
    EXPLICIT_PARALLEL = "EXPLICIT_PARALLEL"


class RunState(StrEnum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class AttemptPhase(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


class TerminalResult(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"
    LOST = "LOST"
    NOT_STARTED = "NOT_STARTED"


class FailureReasonFamily(StrEnum):
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    TIMEOUT = "TIMEOUT"
    CANCELLATION = "CANCELLATION"
    INTERRUPTION = "INTERRUPTION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INTEGRITY_DEFECT = "INTEGRITY_DEFECT"
    POLICY_BLOCK = "POLICY_BLOCK"
    UNCLASSIFIED_FAILURE = "UNCLASSIFIED_FAILURE"


class OutcomeValidity(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ActionCategory(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    RETRY = "RETRY"
    INVALIDATE = "INVALIDATE"
    CANCEL = "CANCEL"
    ABANDON = "ABANDON"
    SUPERSEDE = "SUPERSEDE"
    NO_ACTION = "NO_ACTION"


class Completeness(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    UNKNOWN = "UNKNOWN"


class ValidationState(StrEnum):
    NOT_VALIDATED = "NOT_VALIDATED"
    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


class UseRestriction(StrEnum):
    UNRESTRICTED = "UNRESTRICTED"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PROHIBITED = "PROHIBITED"


class RedactionState(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REDACTED_BEFORE_WRITE = "REDACTED_BEFORE_WRITE"
    RESTRICTED_REFERENCE_ONLY = "RESTRICTED_REFERENCE_ONLY"


class RelationType(StrEnum):
    PARENT_OF = "PARENT_OF"
    TRIGGERED_BY = "TRIGGERED_BY"
    RESUMES_FROM = "RESUMES_FROM"
    SUPERSEDES = "SUPERSEDES"
    PRODUCES_ARTIFACT = "PRODUCES_ARTIFACT"
    CONSUMES_ARTIFACT = "CONSUMES_ARTIFACT"
    HAS_ARTIFACT = "HAS_ARTIFACT"
    CORRECTS = "CORRECTS"
    RELATED_TO = "RELATED_TO"


class AcyclicityClass(StrEnum):
    ACYCLIC = "ACYCLIC"
    CYCLES_ALLOWED = "CYCLES_ALLOWED"


class SourceState(StrEnum):
    CLEAN_COMMITTED = "CLEAN_COMMITTED"
    DIRTY_ATTRIBUTABLE = "DIRTY_ATTRIBUTABLE"
    UNATTRIBUTABLE = "UNATTRIBUTABLE"


class ReferenceKind(StrEnum):
    CONFIGURATION = "CONFIGURATION"
    DATA = "DATA"
    MODEL = "MODEL"
    POLICY = "POLICY"
    ENVIRONMENT = "ENVIRONMENT"
    CHECKPOINT = "CHECKPOINT"
    GRAPH = "GRAPH"
    RETRIEVAL_SNAPSHOT = "RETRIEVAL_SNAPSHOT"
    TEMPORAL_CUTOFF = "TEMPORAL_CUTOFF"


RECORD_TYPES = frozenset(
    {
        "RUN",
        "ATTEMPT",
        "RUN_TRANSITION",
        "ATTEMPT_TRANSITION",
        "OUTCOME",
        "DISPOSITION",
        "ARTIFACT",
        "RELATIONSHIP",
        "SOURCE_ATTRIBUTION",
        "PROVENANCE_REFERENCE",
    }
)


def _validate_code(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _CODE_RE.fullmatch(value):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid code for {field}",
            {"field": field},
        )
    return value


def _base_record_fields(record_id: str, record_type: str) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "record_type": record_type,
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "record_canonicalization_profile": RECORD_PROFILE,
    }


def record_hash(record: "AuthoritativeRecord") -> str:
    return record_hash_from_obj(record.to_canonical())


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    operation_class: str
    objective: str
    consequence_profile: ConsequenceProfile
    reproducibility_class: ReproducibilityClass
    evidence_strength: EvidenceStrength
    initiator_class: InitiatorClass
    initiator_ref: str | None
    trigger_type: TriggerType | None
    trigger_ref: str | None
    registered_at_ns: int
    attempt_concurrency: AttemptConcurrency
    parallel_capacity: int | None
    provenance_qualifier: ProvenanceQualifier
    retention_class: str
    sensitivity_class: SensitivityClass
    evaluation_protocol_ref: str | None
    temporal_cutoff_bundle_ref: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.run_id, field="run_id")
        _validate_code(self.operation_class, field="operation_class")
        if (self.trigger_type is None) != (self.trigger_ref is None):
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "trigger_type and trigger_ref must be paired",
                {},
            )
        if self.attempt_concurrency == AttemptConcurrency.SEQUENTIAL:
            if self.parallel_capacity is not None:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "parallel_capacity must be null for SEQUENTIAL",
                    {},
                )
        elif self.parallel_capacity is None or self.parallel_capacity < 1:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "parallel_capacity required for EXPLICIT_PARALLEL",
                {},
            )

    @property
    def record_type(self) -> str:
        return "RUN"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.run_id, "RUN"),
            "run_id": self.run_id,
            "operation_class": self.operation_class,
            "objective": self.objective,
            "consequence_profile": self.consequence_profile.value,
            "reproducibility_class": self.reproducibility_class.value,
            "evidence_strength": self.evidence_strength.value,
            "initiator_class": self.initiator_class.value,
            "initiator_ref": self.initiator_ref,
            "trigger_type": self.trigger_type.value if self.trigger_type else None,
            "trigger_ref": self.trigger_ref,
            "registered_at_ns": self.registered_at_ns,
            "attempt_concurrency": self.attempt_concurrency.value,
            "parallel_capacity": self.parallel_capacity,
            "provenance_qualifier": self.provenance_qualifier.value,
            "retention_class": self.retention_class,
            "sensitivity_class": self.sensitivity_class.value,
            "evaluation_protocol_ref": self.evaluation_protocol_ref,
            "temporal_cutoff_bundle_ref": self.temporal_cutoff_bundle_ref,
        }


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_id: str
    run_id: str
    attempt_sequence: int
    invocation_ref: str
    environment_ref: str
    predecessor_attempt_id: str | None
    checkpoint_ref_id: str | None
    parallel_group: str | None
    expected_start_after_ns: int | None
    expected_end_before_ns: int | None
    retention_class: str
    sensitivity_class: SensitivityClass

    def __post_init__(self) -> None:
        validate_uuid(self.attempt_id, field="attempt_id")
        validate_uuid(self.run_id, field="run_id")
        if self.attempt_sequence < 1:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "attempt_sequence must be >= 1",
                {},
            )
        if self.predecessor_attempt_id is not None:
            validate_uuid(self.predecessor_attempt_id, field="predecessor_attempt_id")

    @property
    def record_type(self) -> str:
        return "ATTEMPT"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.attempt_id, "ATTEMPT"),
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "attempt_sequence": self.attempt_sequence,
            "invocation_ref": self.invocation_ref,
            "environment_ref": self.environment_ref,
            "predecessor_attempt_id": self.predecessor_attempt_id,
            "checkpoint_ref_id": self.checkpoint_ref_id,
            "parallel_group": self.parallel_group,
            "expected_start_after_ns": self.expected_start_after_ns,
            "expected_end_before_ns": self.expected_end_before_ns,
            "retention_class": self.retention_class,
            "sensitivity_class": self.sensitivity_class.value,
        }


@dataclass(frozen=True, slots=True)
class RunTransitionRecord:
    transition_id: str
    run_id: str
    predecessor_transition_id: str | None
    from_state: RunState | None
    to_state: RunState
    effective_at_ns: int
    actor_type: ActorType
    actor_ref: str | None
    policy_ref: str | None
    reason_code: str
    terminal_disposition_id: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.transition_id, field="transition_id")
        validate_uuid(self.run_id, field="run_id")
        if self.predecessor_transition_id is not None:
            validate_uuid(self.predecessor_transition_id, field="predecessor_transition_id")
        if self.to_state == RunState.CLOSED and self.terminal_disposition_id is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "terminal_disposition_id required for CLOSED",
                {},
            )
        if self.to_state != RunState.CLOSED and self.terminal_disposition_id is not None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "terminal_disposition_id only allowed for CLOSED",
                {},
            )
        _validate_code(self.reason_code, field="reason_code")

    @property
    def record_type(self) -> str:
        return "RUN_TRANSITION"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.transition_id, "RUN_TRANSITION"),
            "transition_id": self.transition_id,
            "run_id": self.run_id,
            "predecessor_transition_id": self.predecessor_transition_id,
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "effective_at_ns": self.effective_at_ns,
            "actor_type": self.actor_type.value,
            "actor_ref": self.actor_ref,
            "policy_ref": self.policy_ref,
            "reason_code": self.reason_code,
            "terminal_disposition_id": self.terminal_disposition_id,
        }


@dataclass(frozen=True, slots=True)
class AttemptTransitionRecord:
    transition_id: str
    attempt_id: str
    predecessor_transition_id: str | None
    from_phase: AttemptPhase | None
    to_phase: AttemptPhase
    terminal_result: TerminalResult | None
    reason_family: FailureReasonFamily | None
    reason_code: str
    started_at_ns: int | None
    ended_at_ns: int | None
    actor_type: ActorType
    actor_ref: str | None
    evidence_ref: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.transition_id, field="transition_id")
        validate_uuid(self.attempt_id, field="attempt_id")
        if self.predecessor_transition_id is not None:
            validate_uuid(self.predecessor_transition_id, field="predecessor_transition_id")
        if self.to_phase == AttemptPhase.TERMINAL and self.terminal_result is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "terminal_result required for TERMINAL",
                {},
            )
        if self.to_phase == AttemptPhase.RUNNING and self.started_at_ns is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "started_at_ns required for RUNNING",
                {},
            )
        if self.to_phase == AttemptPhase.TERMINAL and self.ended_at_ns is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "ended_at_ns required for TERMINAL",
                {},
            )
        _validate_code(self.reason_code, field="reason_code")

    @property
    def record_type(self) -> str:
        return "ATTEMPT_TRANSITION"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.transition_id, "ATTEMPT_TRANSITION"),
            "transition_id": self.transition_id,
            "attempt_id": self.attempt_id,
            "predecessor_transition_id": self.predecessor_transition_id,
            "from_phase": self.from_phase.value if self.from_phase else None,
            "to_phase": self.to_phase.value,
            "terminal_result": self.terminal_result.value if self.terminal_result else None,
            "reason_family": self.reason_family.value if self.reason_family else None,
            "reason_code": self.reason_code,
            "started_at_ns": self.started_at_ns,
            "ended_at_ns": self.ended_at_ns,
            "actor_type": self.actor_type.value,
            "actor_ref": self.actor_ref,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    outcome_id: str
    run_id: str
    attempt_id: str | None
    outcome_type: str
    result_ref: str
    validity: OutcomeValidity
    evaluated_at_ns: int
    effective_at_ns: int | None
    protocol_ref: str | None
    supersedes_outcome_id: str | None
    limitations: str | None
    retention_class: str
    sensitivity_class: SensitivityClass

    def __post_init__(self) -> None:
        validate_uuid(self.outcome_id, field="outcome_id")
        validate_uuid(self.run_id, field="run_id")
        if self.attempt_id is not None:
            validate_uuid(self.attempt_id, field="attempt_id")
        _validate_code(self.outcome_type, field="outcome_type")

    @property
    def record_type(self) -> str:
        return "OUTCOME"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.outcome_id, "OUTCOME"),
            "outcome_id": self.outcome_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "outcome_type": self.outcome_type,
            "result_ref": self.result_ref,
            "validity": self.validity.value,
            "evaluated_at_ns": self.evaluated_at_ns,
            "effective_at_ns": self.effective_at_ns,
            "protocol_ref": self.protocol_ref,
            "supersedes_outcome_id": self.supersedes_outcome_id,
            "limitations": self.limitations,
            "retention_class": self.retention_class,
            "sensitivity_class": self.sensitivity_class.value,
        }


@dataclass(frozen=True, slots=True)
class DispositionRecord:
    disposition_id: str
    run_id: str
    outcome_id: str | None
    decision_at_ns: int
    authority_type: ActorType
    authority_ref: str
    policy_ref: str | None
    action_category: ActionCategory
    domain_code: str
    prior_disposition_id: str | None
    limitations: str | None
    retention_class: str
    sensitivity_class: SensitivityClass

    def __post_init__(self) -> None:
        validate_uuid(self.disposition_id, field="disposition_id")
        validate_uuid(self.run_id, field="run_id")
        if self.outcome_id is not None:
            validate_uuid(self.outcome_id, field="outcome_id")
        if self.prior_disposition_id is not None:
            validate_uuid(self.prior_disposition_id, field="prior_disposition_id")
        _validate_code(self.domain_code, field="domain_code")

    @property
    def record_type(self) -> str:
        return "DISPOSITION"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.disposition_id, "DISPOSITION"),
            "disposition_id": self.disposition_id,
            "run_id": self.run_id,
            "outcome_id": self.outcome_id,
            "decision_at_ns": self.decision_at_ns,
            "authority_type": self.authority_type.value,
            "authority_ref": self.authority_ref,
            "policy_ref": self.policy_ref,
            "action_category": self.action_category.value,
            "domain_code": self.domain_code,
            "prior_disposition_id": self.prior_disposition_id,
            "limitations": self.limitations,
            "retention_class": self.retention_class,
            "sensitivity_class": self.sensitivity_class.value,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    logical_role: str
    logical_name: str | None
    content_hash: str
    hash_profile: str
    byte_size: int
    media_type: str
    content_type: str | None
    producer_run_id: str
    producer_attempt_id: str | None
    completeness: Completeness
    producer_terminal_result: TerminalResult | None
    validation_state: ValidationState
    use_restriction: UseRestriction
    mutability_class: str
    retention_class: str
    sensitivity_class: SensitivityClass
    cas_locator_profile: str
    redaction_state: RedactionState

    def __post_init__(self) -> None:
        validate_uuid(self.artifact_id, field="artifact_id")
        validate_uuid(self.producer_run_id, field="producer_run_id")
        if self.producer_attempt_id is not None:
            validate_uuid(self.producer_attempt_id, field="producer_attempt_id")
        if self.byte_size < 0:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "byte_size must be nonnegative",
                {},
            )

    @property
    def record_type(self) -> str:
        return "ARTIFACT"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.artifact_id, "ARTIFACT"),
            "artifact_id": self.artifact_id,
            "logical_role": self.logical_role,
            "logical_name": self.logical_name,
            "content_hash": self.content_hash,
            "hash_profile": self.hash_profile,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
            "content_type": self.content_type,
            "producer_run_id": self.producer_run_id,
            "producer_attempt_id": self.producer_attempt_id,
            "completeness": self.completeness.value,
            "producer_terminal_result": (
                self.producer_terminal_result.value if self.producer_terminal_result else None
            ),
            "validation_state": self.validation_state.value,
            "use_restriction": self.use_restriction.value,
            "mutability_class": self.mutability_class,
            "retention_class": self.retention_class,
            "sensitivity_class": self.sensitivity_class.value,
            "cas_locator_profile": self.cas_locator_profile,
            "redaction_state": self.redaction_state.value,
        }


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    relationship_id: str
    source_record_type: str
    source_record_id: str
    relation_type: RelationType
    target_record_type: str
    target_record_id: str
    effective_at_ns: int | None
    acyclicity_class: AcyclicityClass
    relation_code: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.relationship_id, field="relationship_id")
        validate_uuid(self.source_record_id, field="source_record_id")
        validate_uuid(self.target_record_id, field="target_record_id")
        if self.source_record_type == "RELATIONSHIP" or self.target_record_type == "RELATIONSHIP":
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "relationship endpoints cannot be RELATIONSHIP",
                {},
            )

    @property
    def record_type(self) -> str:
        return "RELATIONSHIP"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.relationship_id, "RELATIONSHIP"),
            "relationship_id": self.relationship_id,
            "source_record_type": self.source_record_type,
            "source_record_id": self.source_record_id,
            "relation_type": self.relation_type.value,
            "target_record_type": self.target_record_type,
            "target_record_id": self.target_record_id,
            "effective_at_ns": self.effective_at_ns,
            "acyclicity_class": self.acyclicity_class.value,
            "relation_code": self.relation_code,
        }


@dataclass(frozen=True, slots=True)
class SourceAttributionRecord:
    source_attribution_id: str
    run_id: str
    repository_identity: str
    root_identity: str
    base_revision: str | None
    source_state: SourceState
    scope_manifest_artifact_id: str | None
    capsule_artifact_id: str | None
    outside_scope_proof_artifact_id: str | None
    limitations: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.source_attribution_id, field="source_attribution_id")
        validate_uuid(self.run_id, field="run_id")

    @property
    def record_type(self) -> str:
        return "SOURCE_ATTRIBUTION"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.source_attribution_id, "SOURCE_ATTRIBUTION"),
            "source_attribution_id": self.source_attribution_id,
            "run_id": self.run_id,
            "repository_identity": self.repository_identity,
            "root_identity": self.root_identity,
            "base_revision": self.base_revision,
            "source_state": self.source_state.value,
            "scope_manifest_artifact_id": self.scope_manifest_artifact_id,
            "capsule_artifact_id": self.capsule_artifact_id,
            "outside_scope_proof_artifact_id": self.outside_scope_proof_artifact_id,
            "limitations": self.limitations,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceReferenceRecord:
    provenance_ref_id: str
    run_id: str
    attempt_id: str | None
    reference_kind: ReferenceKind
    canonical_identity: str
    canonical_version: str | None
    canonical_hash: str | None
    available_at_ns: int | None
    coverage_start_ns: int | None
    coverage_end_ns: int | None
    artifact_id: str | None
    limitations: str | None

    def __post_init__(self) -> None:
        validate_uuid(self.provenance_ref_id, field="provenance_ref_id")
        validate_uuid(self.run_id, field="run_id")
        if self.attempt_id is not None:
            validate_uuid(self.attempt_id, field="attempt_id")
        if self.artifact_id is not None:
            validate_uuid(self.artifact_id, field="artifact_id")

    @property
    def record_type(self) -> str:
        return "PROVENANCE_REFERENCE"

    def to_canonical(self) -> dict[str, Any]:
        return {
            **_base_record_fields(self.provenance_ref_id, "PROVENANCE_REFERENCE"),
            "provenance_ref_id": self.provenance_ref_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "reference_kind": self.reference_kind.value,
            "canonical_identity": self.canonical_identity,
            "canonical_version": self.canonical_version,
            "canonical_hash": self.canonical_hash,
            "available_at_ns": self.available_at_ns,
            "coverage_start_ns": self.coverage_start_ns,
            "coverage_end_ns": self.coverage_end_ns,
            "artifact_id": self.artifact_id,
            "limitations": self.limitations,
        }


AuthoritativeRecord = (
    RunRecord
    | AttemptRecord
    | RunTransitionRecord
    | AttemptTransitionRecord
    | OutcomeRecord
    | DispositionRecord
    | ArtifactRecord
    | RelationshipRecord
    | SourceAttributionRecord
    | ProvenanceReferenceRecord
)


def record_primary_id(record: AuthoritativeRecord) -> str:
    if isinstance(record, RunRecord):
        return record.run_id
    if isinstance(record, AttemptRecord):
        return record.attempt_id
    if isinstance(record, RunTransitionRecord):
        return record.transition_id
    if isinstance(record, AttemptTransitionRecord):
        return record.transition_id
    if isinstance(record, OutcomeRecord):
        return record.outcome_id
    if isinstance(record, DispositionRecord):
        return record.disposition_id
    if isinstance(record, ArtifactRecord):
        return record.artifact_id
    if isinstance(record, RelationshipRecord):
        return record.relationship_id
    if isinstance(record, SourceAttributionRecord):
        return record.source_attribution_id
    if isinstance(record, ProvenanceReferenceRecord):
        return record.provenance_ref_id
    raise OF01Error(OF01ErrorCode.INVALID_COMMAND, "unknown record type", {})
