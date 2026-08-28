"""Immutable OF-01 typed command envelopes and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .canonical import (
    COMMAND_PROFILE,
    COMMIT_PROFILE,
    HASH_PROFILE,
    command_hash_from_obj,
    commit_hash_from_obj,
)
from .errors import OF01Error, OF01ErrorCode
from .ids import validate_hash, validate_uuid
from .records import (
    ArtifactRecord,
    AttemptRecord,
    AttemptTransitionRecord,
    AuthoritativeRecord,
    DispositionRecord,
    OutcomeRecord,
    ProvenanceReferenceRecord,
    RelationshipRecord,
    RunRecord,
    RunTransitionRecord,
    SourceAttributionRecord,
    record_hash,
    record_primary_id,
)

COMMAND_SCHEMA_VERSION = 1
COMMIT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class RegisterRun:
    run: RunRecord
    initial_transition: RunTransitionRecord


@dataclass(frozen=True, slots=True)
class RegisterAttempt:
    attempt: AttemptRecord
    initial_transition: AttemptTransitionRecord
    expected_run_transition_id: str


@dataclass(frozen=True, slots=True)
class AppendRunTransition:
    transition: RunTransitionRecord
    expected_predecessor_transition_id: str | None


@dataclass(frozen=True, slots=True)
class AppendAttemptTransition:
    transition: AttemptTransitionRecord
    expected_predecessor_transition_id: str | None
    expected_parallel_active_count: int | None = None


@dataclass(frozen=True, slots=True)
class RecordOutcome:
    outcome: OutcomeRecord
    relationship: RelationshipRecord | None = None


@dataclass(frozen=True, slots=True)
class AppendDisposition:
    disposition: DispositionRecord
    expected_prior_disposition_id: str | None


@dataclass(frozen=True, slots=True)
class CloseRun:
    disposition: DispositionRecord
    terminal_transition: RunTransitionRecord
    expected_run_transition_id: str


@dataclass(frozen=True, slots=True)
class RegisterArtifact:
    artifact: ArtifactRecord


@dataclass(frozen=True, slots=True)
class AttachArtifact:
    relationship: RelationshipRecord


@dataclass(frozen=True, slots=True)
class CreateRelationship:
    relationship: RelationshipRecord


@dataclass(frozen=True, slots=True)
class AttachSourceAttribution:
    source_attribution: SourceAttributionRecord
    scope_manifest_artifacts: tuple[ArtifactRecord, ...] = ()
    capsule_artifacts: tuple[ArtifactRecord, ...] = ()
    proof_artifacts: tuple[ArtifactRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class AttachProvenanceReference:
    provenance_reference: ProvenanceReferenceRecord
    relationship: RelationshipRecord | None = None


LedgerCommand = (
    RegisterRun
    | RegisterAttempt
    | AppendRunTransition
    | AppendAttemptTransition
    | RecordOutcome
    | AppendDisposition
    | CloseRun
    | RegisterArtifact
    | AttachArtifact
    | CreateRelationship
    | AttachSourceAttribution
    | AttachProvenanceReference
)


COMMAND_TYPES = {
    RegisterRun: "RegisterRun",
    RegisterAttempt: "RegisterAttempt",
    AppendRunTransition: "AppendRunTransition",
    AppendAttemptTransition: "AppendAttemptTransition",
    RecordOutcome: "RecordOutcome",
    AppendDisposition: "AppendDisposition",
    CloseRun: "CloseRun",
    RegisterArtifact: "RegisterArtifact",
    AttachArtifact: "AttachArtifact",
    CreateRelationship: "CreateRelationship",
    AttachSourceAttribution: "AttachSourceAttribution",
    AttachProvenanceReference: "AttachProvenanceReference",
}


def command_type_name(command: LedgerCommand) -> str:
    return COMMAND_TYPES[type(command)]


def _command_body_to_canonical(command: LedgerCommand) -> dict[str, Any]:
    command_type = command_type_name(command)
    body: dict[str, Any] = {
        "command_canonicalization_profile": COMMAND_PROFILE,
        "command_schema_version": COMMAND_SCHEMA_VERSION,
        "command_type": command_type,
    }
    if isinstance(command, RegisterRun):
        body["run"] = _run_command_fields(command.run)
        body["initial_transition"] = _run_transition_command_fields(command.initial_transition)
    elif isinstance(command, RegisterAttempt):
        body["attempt"] = _attempt_command_fields(command.attempt)
        body["initial_transition"] = _attempt_transition_command_fields(command.initial_transition)
        body["expected_run_transition_id"] = command.expected_run_transition_id
    elif isinstance(command, AppendRunTransition):
        body["transition"] = _run_transition_command_fields(command.transition)
        body["expected_predecessor_transition_id"] = command.expected_predecessor_transition_id
    elif isinstance(command, AppendAttemptTransition):
        body["transition"] = _attempt_transition_command_fields(command.transition)
        body["expected_predecessor_transition_id"] = command.expected_predecessor_transition_id
        if command.expected_parallel_active_count is not None:
            body["expected_parallel_active_count"] = command.expected_parallel_active_count
    elif isinstance(command, RecordOutcome):
        body["outcome"] = _outcome_command_fields(command.outcome)
        body["relationship"] = (
            _relationship_command_fields(command.relationship) if command.relationship else None
        )
    elif isinstance(command, AppendDisposition):
        body["disposition"] = _disposition_command_fields(command.disposition)
        body["expected_prior_disposition_id"] = command.expected_prior_disposition_id
    elif isinstance(command, CloseRun):
        body["disposition"] = _disposition_command_fields(command.disposition)
        body["terminal_transition"] = _run_transition_command_fields(command.terminal_transition)
        body["expected_run_transition_id"] = command.expected_run_transition_id
    elif isinstance(command, RegisterArtifact):
        body["artifact"] = _artifact_command_fields(command.artifact)
    elif isinstance(command, AttachArtifact):
        body["relationship"] = _relationship_command_fields(command.relationship)
    elif isinstance(command, CreateRelationship):
        body["relationship"] = _relationship_command_fields(command.relationship)
    elif isinstance(command, AttachSourceAttribution):
        body["source_attribution"] = _source_attribution_command_fields(command.source_attribution)
    elif isinstance(command, AttachProvenanceReference):
        body["provenance_reference"] = _provenance_command_fields(command.provenance_reference)
        body["relationship"] = (
            _relationship_command_fields(command.relationship) if command.relationship else None
        )
    else:
        raise OF01Error(OF01ErrorCode.INVALID_COMMAND, "unknown command", {})
    return body


def _strip_record_envelope(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in {"record_id", "record_type", "record_schema_version", "record_canonicalization_profile"}}


def _run_command_fields(run: RunRecord) -> dict[str, Any]:
    return _strip_record_envelope(run.to_canonical())


def _run_transition_command_fields(transition: RunTransitionRecord) -> dict[str, Any]:
    return _strip_record_envelope(transition.to_canonical())


def _attempt_command_fields(attempt: AttemptRecord) -> dict[str, Any]:
    return _strip_record_envelope(attempt.to_canonical())


def _attempt_transition_command_fields(transition: AttemptTransitionRecord) -> dict[str, Any]:
    return _strip_record_envelope(transition.to_canonical())


def _outcome_command_fields(outcome: OutcomeRecord) -> dict[str, Any]:
    return _strip_record_envelope(outcome.to_canonical())


def _disposition_command_fields(disposition: DispositionRecord) -> dict[str, Any]:
    return _strip_record_envelope(disposition.to_canonical())


def _artifact_command_fields(artifact: ArtifactRecord) -> dict[str, Any]:
    return _strip_record_envelope(artifact.to_canonical())


def _relationship_command_fields(relationship: RelationshipRecord) -> dict[str, Any]:
    return _strip_record_envelope(relationship.to_canonical())


def _source_attribution_command_fields(source: SourceAttributionRecord) -> dict[str, Any]:
    return _strip_record_envelope(source.to_canonical())


def _provenance_command_fields(provenance: ProvenanceReferenceRecord) -> dict[str, Any]:
    return _strip_record_envelope(provenance.to_canonical())


def compute_command_hash(command: LedgerCommand) -> str:
    return command_hash_from_obj(_command_body_to_canonical(command))


def command_record_plan(command: LedgerCommand) -> tuple[AuthoritativeRecord, ...]:
    if isinstance(command, RegisterRun):
        return (command.run, command.initial_transition)
    if isinstance(command, RegisterAttempt):
        return (command.attempt, command.initial_transition)
    if isinstance(command, AppendRunTransition):
        return (command.transition,)
    if isinstance(command, AppendAttemptTransition):
        return (command.transition,)
    if isinstance(command, RecordOutcome):
        if command.relationship is not None:
            return (command.outcome, command.relationship)
        return (command.outcome,)
    if isinstance(command, AppendDisposition):
        return (command.disposition,)
    if isinstance(command, CloseRun):
        return (command.disposition, command.terminal_transition)
    if isinstance(command, RegisterArtifact):
        return (command.artifact,)
    if isinstance(command, AttachArtifact):
        return (command.relationship,)
    if isinstance(command, CreateRelationship):
        return (command.relationship,)
    if isinstance(command, AttachSourceAttribution):
        records: list[AuthoritativeRecord] = []
        records.extend(command.scope_manifest_artifacts)
        records.extend(command.capsule_artifacts)
        records.extend(command.proof_artifacts)
        records.append(command.source_attribution)
        return tuple(records)
    if isinstance(command, AttachProvenanceReference):
        if command.relationship is not None:
            return (command.provenance_reference, command.relationship)
        return (command.provenance_reference,)
    raise OF01Error(OF01ErrorCode.INVALID_COMMAND, "unknown command", {})


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    command_type: str
    command_schema_version: int
    command_canonicalization_profile: str
    command_hash: str
    command: LedgerCommand

    def __post_init__(self) -> None:
        validate_uuid(self.command_id, field="command_id")
        validate_hash(self.command_hash, field="command_hash")
        if self.command_schema_version != COMMAND_SCHEMA_VERSION:
            raise OF01Error(
                OF01ErrorCode.UNSUPPORTED_COMMAND_SCHEMA,
                "unsupported command schema version",
                {"version": self.command_schema_version},
            )
        if self.command_canonicalization_profile != COMMAND_PROFILE:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "unsupported command profile",
                {"profile": self.command_canonicalization_profile},
            )
        if command_type_name(self.command) != self.command_type:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "command_type mismatch",
                {"expected": command_type_name(self.command), "actual": self.command_type},
            )


@dataclass(frozen=True, slots=True)
class CommittedRecordRef:
    record_type: str
    record_id: str
    record_schema_version: int
    record_canonicalization_profile: str
    record_hash: str
    item_ordinal: int


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    ledger_authority_id: str
    command_id: str
    command_hash: str
    commit_id: str
    commit_sequence: int
    commit_hash: str
    records: tuple[CommittedRecordRef, ...]
    was_existing: bool


@dataclass(frozen=True, slots=True)
class PreparedArtifactToken:
    artifact_id: str
    temp_path: str
    content_hash: str
    byte_size: int
    operation_id: str


def validate_command(envelope: CommandEnvelope) -> None:
    computed = compute_command_hash(envelope.command)
    if computed != envelope.command_hash:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "command_hash mismatch",
            {"expected": computed, "actual": envelope.command_hash},
        )


validate_command_envelope = validate_command


def build_commit_hash(
    *,
    ledger_authority_id: str,
    command_id: str,
    command_hash: str,
    command_type: str,
    commit_id: str,
    commit_sequence: int,
    recorded_at_ns: int,
    records: tuple[AuthoritativeRecord, ...],
) -> str:
    items = []
    for ordinal, rec in enumerate(records):
        items.append(
            {
                "item_ordinal": ordinal,
                "record_canonicalization_profile": rec.to_canonical()["record_canonicalization_profile"],
                "record_hash": record_hash(rec),
                "record_id": record_primary_id(rec),
                "record_schema_version": rec.to_canonical()["record_schema_version"],
                "record_type": rec.record_type,
            }
        )
    commit_obj = {
        "command_canonicalization_profile": COMMAND_PROFILE,
        "command_hash": command_hash,
        "command_id": command_id,
        "command_schema_version": COMMAND_SCHEMA_VERSION,
        "command_type": command_type,
        "commit_canonicalization_profile": COMMIT_PROFILE,
        "commit_id": commit_id,
        "commit_schema_version": COMMIT_SCHEMA_VERSION,
        "commit_sequence": commit_sequence,
        "hash_profile": HASH_PROFILE,
        "items": items,
        "ledger_authority_id": ledger_authority_id,
        "record_count": len(records),
        "recorded_at_ns": recorded_at_ns,
    }
    return commit_hash_from_obj(commit_obj)


def require_same_hash(receipt: CommitReceipt, command_hash: str) -> CommitReceipt:
    if receipt.command_hash != command_hash:
        raise OF01Error(
            OF01ErrorCode.COMMAND_ID_CONFLICT,
            "command_id reused with different hash",
            {"command_id": receipt.command_id},
        )
    return CommitReceipt(
        ledger_authority_id=receipt.ledger_authority_id,
        command_id=receipt.command_id,
        command_hash=receipt.command_hash,
        commit_id=receipt.commit_id,
        commit_sequence=receipt.commit_sequence,
        commit_hash=receipt.commit_hash,
        records=receipt.records,
        was_existing=True,
    )


def committed_refs_from_records(
    records: tuple[AuthoritativeRecord, ...],
) -> tuple[CommittedRecordRef, ...]:
    refs: list[CommittedRecordRef] = []
    for ordinal, record in enumerate(records):
        canonical = record.to_canonical()
        refs.append(
            CommittedRecordRef(
                record_type=record.record_type,
                record_id=record_primary_id(record),
                record_schema_version=canonical["record_schema_version"],
                record_canonicalization_profile=canonical["record_canonicalization_profile"],
                record_hash=record_hash(record),
                item_ordinal=ordinal,
            )
        )
    return tuple(refs)
