"""Typed OF-01 ledger readers and commit stream."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .canonical import RECORD_PROFILE, record_hash_from_obj
from .errors import OF01Error, OF01ErrorCode
from .protocols import (
    AttemptView,
    CommitBundle,
    DispositionScope,
    DispositionSelectionPolicyV1,
    LedgerCommit,
    RunView,
)
from .records import (
    ActionCategory,
    ActorType,
    ArtifactRecord,
    AttemptConcurrency,
    AttemptPhase,
    AttemptRecord,
    AttemptTransitionRecord,
    AuthoritativeRecord,
    Completeness,
    ConsequenceProfile,
    DispositionRecord,
    EvidenceStrength,
    FailureReasonFamily,
    InitiatorClass,
    OutcomeRecord,
    OutcomeValidity,
    ProvenanceQualifier,
    ProvenanceReferenceRecord,
    RedactionState,
    ReferenceKind,
    RelationType,
    AcyclicityClass,
    ReproducibilityClass,
    RelationshipRecord,
    RunRecord,
    RunState,
    RunTransitionRecord,
    SensitivityClass,
    SourceAttributionRecord,
    SourceState,
    TerminalResult,
    TriggerType,
    UseRestriction,
    ValidationState,
    record_hash,
)
from .sqlite_store import SQLiteAuthorityStore


def _row_get(row: sqlite3.Row, key: str) -> Any:
    return row[key]


def _load_run(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=str(row["run_id"]),
        operation_class=str(row["operation_class"]),
        objective=str(row["objective"]),
        consequence_profile=ConsequenceProfile(str(row["consequence_profile"])),
        reproducibility_class=ReproducibilityClass(str(row["reproducibility_class"])),
        evidence_strength=EvidenceStrength(str(row["evidence_strength"])),
        initiator_class=InitiatorClass(str(row["initiator_class"])),
        initiator_ref=row["initiator_ref"],
        trigger_type=TriggerType(str(row["trigger_type"])) if row["trigger_type"] else None,
        trigger_ref=row["trigger_ref"],
        registered_at_ns=int(row["registered_at_ns"]),
        attempt_concurrency=AttemptConcurrency(str(row["attempt_concurrency"])),
        parallel_capacity=int(row["parallel_capacity"]) if row["parallel_capacity"] is not None else None,
        provenance_qualifier=ProvenanceQualifier(str(row["provenance_qualifier"])),
        retention_class=str(row["retention_class"]),
        sensitivity_class=SensitivityClass(str(row["sensitivity_class"])),
        evaluation_protocol_ref=row["evaluation_protocol_ref"],
        temporal_cutoff_bundle_ref=row["temporal_cutoff_bundle_ref"],
    )


def _load_record(conn: sqlite3.Connection, record_type: str, record_id: str) -> AuthoritativeRecord | None:
    table_map = {
        "RUN": ("runs", "run_id"),
        "ATTEMPT": ("attempts", "attempt_id"),
        "RUN_TRANSITION": ("run_transitions", "transition_id"),
        "ATTEMPT_TRANSITION": ("attempt_transitions", "transition_id"),
        "OUTCOME": ("outcomes", "outcome_id"),
        "DISPOSITION": ("dispositions", "disposition_id"),
        "ARTIFACT": ("artifacts", "artifact_id"),
        "RELATIONSHIP": ("relationships", "relationship_id"),
        "SOURCE_ATTRIBUTION": ("source_attributions", "source_attribution_id"),
        "PROVENANCE_REFERENCE": ("provenance_references", "provenance_ref_id"),
    }
    spec = table_map.get(record_type)
    if spec is None:
        return None
    table, pk = spec
    row = conn.execute(f"SELECT * FROM {table} WHERE {pk} = ?", (record_id,)).fetchone()
    if row is None:
        return None
    if record_type == "RUN":
        return _load_run(row)
    if record_type == "ATTEMPT":
        return AttemptRecord(
            attempt_id=str(row["attempt_id"]),
            run_id=str(row["run_id"]),
            attempt_sequence=int(row["attempt_sequence"]),
            invocation_ref=str(row["invocation_ref"]),
            environment_ref=str(row["environment_ref"]),
            predecessor_attempt_id=row["predecessor_attempt_id"],
            checkpoint_ref_id=row["checkpoint_ref_id"],
            parallel_group=row["parallel_group"],
            expected_start_after_ns=row["expected_start_after_ns"],
            expected_end_before_ns=row["expected_end_before_ns"],
            retention_class=str(row["retention_class"]),
            sensitivity_class=SensitivityClass(str(row["sensitivity_class"])),
        )
    if record_type == "RUN_TRANSITION":
        return RunTransitionRecord(
            transition_id=str(row["transition_id"]),
            run_id=str(row["run_id"]),
            predecessor_transition_id=row["predecessor_transition_id"],
            from_state=RunState(str(row["from_state"])) if row["from_state"] else None,
            to_state=RunState(str(row["to_state"])),
            effective_at_ns=int(row["effective_at_ns"]),
            actor_type=ActorType(str(row["actor_type"])),
            actor_ref=row["actor_ref"],
            policy_ref=row["policy_ref"],
            reason_code=str(row["reason_code"]),
            terminal_disposition_id=row["terminal_disposition_id"],
        )
    if record_type == "SOURCE_ATTRIBUTION":
        return SourceAttributionRecord(
            source_attribution_id=str(row["source_attribution_id"]),
            run_id=str(row["run_id"]),
            repository_identity=str(row["repository_identity"]),
            root_identity=str(row["root_identity"]),
            base_revision=row["base_revision"],
            source_state=SourceState(str(row["source_state"])),
            scope_manifest_artifact_id=row["scope_manifest_artifact_id"],
            capsule_artifact_id=row["capsule_artifact_id"],
            outside_scope_proof_artifact_id=row["outside_scope_proof_artifact_id"],
            limitations=row["limitations"],
        )
    if record_type == "PROVENANCE_REFERENCE":
        return ProvenanceReferenceRecord(
            provenance_ref_id=str(row["provenance_ref_id"]),
            run_id=str(row["run_id"]),
            attempt_id=row["attempt_id"],
            reference_kind=ReferenceKind(str(row["reference_kind"])),
            canonical_identity=str(row["canonical_identity"]),
            canonical_version=row["canonical_version"],
            canonical_hash=row["canonical_hash"],
            available_at_ns=row["available_at_ns"],
            coverage_start_ns=row["coverage_start_ns"],
            coverage_end_ns=row["coverage_end_ns"],
            artifact_id=row["artifact_id"],
            limitations=row["limitations"],
        )
    if record_type == "DISPOSITION":
        return DispositionRecord(
            disposition_id=str(row["disposition_id"]),
            run_id=str(row["run_id"]),
            outcome_id=row["outcome_id"],
            decision_at_ns=int(row["decision_at_ns"]),
            authority_type=ActorType(str(row["authority_type"])),
            authority_ref=str(row["authority_ref"]),
            policy_ref=row["policy_ref"],
            action_category=ActionCategory(str(row["action_category"])),
            domain_code=str(row["domain_code"]),
            prior_disposition_id=row["prior_disposition_id"],
            limitations=row["limitations"],
            retention_class=str(row["retention_class"]),
            sensitivity_class=SensitivityClass(str(row["sensitivity_class"])),
        )
  # Additional record types loaded on demand in integrity checks via commit items.
    return None


def select_current_disposition(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    policy: DispositionSelectionPolicyV1,
) -> str | None:
    query = """
        SELECT disposition_id, outcome_id, authority_type, action_category, prior_disposition_id
        FROM dispositions
        WHERE run_id = ?
        ORDER BY decision_at_ns, disposition_id
    """
    rows = conn.execute(query, (run_id,)).fetchall()
    filtered = []
    for row in rows:
        if policy.scope == DispositionScope.OUTCOME.value and row["outcome_id"] is None:
            continue
        if row["authority_type"] not in policy.allowed_authority_types:
            continue
        if row["action_category"] not in policy.allowed_action_categories:
            continue
        filtered.append(row)
    named_as_prior = {
        str(r["prior_disposition_id"])
        for r in filtered
        if r["prior_disposition_id"] is not None
    }
    heads = [r for r in filtered if str(r["disposition_id"]) not in named_as_prior]
    if len(heads) == 0:
        return None
    if len(heads) > 1:
        raise OF01Error(
            OF01ErrorCode.DISPOSITION_AMBIGUOUS,
            "multiple disposition heads for policy",
            {"run_id": run_id},
        )
    return str(heads[0]["disposition_id"])


class SQLiteLedgerReader:
    def __init__(self, store: SQLiteAuthorityStore) -> None:
        self._store = store

    @contextmanager
    def read_snapshot(self) -> Iterator[sqlite3.Connection]:
        self._store.connection.execute("BEGIN")
        try:
            yield self._store.connection
        finally:
            self._store.connection.execute("ROLLBACK")

    def get_record(self, record_type: str, record_id: str) -> AuthoritativeRecord | None:
        with self.read_snapshot() as conn:
            return _load_record(conn, record_type, record_id)

    def get_run(
        self,
        run_id: str,
        disposition_policy: DispositionSelectionPolicyV1,
    ) -> RunView | None:
        with self.read_snapshot() as conn:
            run = _load_record(conn, "RUN", run_id)
            if run is None:
                return None
            current_state = self._store.get_run_state(conn, run_id)
            seq_row = conn.execute(
                "SELECT MAX(commit_sequence) FROM ledger_commits"
            ).fetchone()
            as_of = int(seq_row[0]) if seq_row and seq_row[0] is not None else 0
            current_disposition = select_current_disposition(
                conn, run_id=run_id, policy=disposition_policy
            )
            return RunView(
                run_id=run_id,
                as_of_commit_sequence=as_of,
                current_state=current_state,
                disposition_policy=disposition_policy,
                current_disposition_id=current_disposition,
            )

    def get_attempt(self, attempt_id: str) -> AttemptView | None:
        with self.read_snapshot() as conn:
            attempt = _load_record(conn, "ATTEMPT", attempt_id)
            if attempt is None or not isinstance(attempt, AttemptRecord):
                return None
            phase = self._store.get_attempt_phase(conn, attempt_id)
            seq_row = conn.execute(
                "SELECT MAX(commit_sequence) FROM ledger_commits"
            ).fetchone()
            as_of = int(seq_row[0]) if seq_row and seq_row[0] is not None else 0
            return AttemptView(
                attempt_id=attempt_id,
                run_id=attempt.run_id,
                current_phase=phase,
                as_of_commit_sequence=as_of,
            )

    def get_commit(self, commit_sequence: int) -> LedgerCommit | None:
        with self.read_snapshot() as conn:
            row = conn.execute(
                """
                SELECT commit_sequence, commit_id, commit_hash, command_id, command_hash,
                       command_type, recorded_at_ns, record_count
                FROM ledger_commits
                WHERE commit_sequence = ?
                """,
                (commit_sequence,),
            ).fetchone()
            if row is None:
                return None
            return LedgerCommit(
                commit_sequence=int(row["commit_sequence"]),
                commit_id=str(row["commit_id"]),
                commit_hash=str(row["commit_hash"]),
                command_id=str(row["command_id"]),
                command_hash=str(row["command_hash"]),
                command_type=str(row["command_type"]),
                recorded_at_ns=int(row["recorded_at_ns"]),
                record_count=int(row["record_count"]),
            )

    def stream_commits(
        self,
        after_sequence: int,
        through_sequence: int | None = None,
    ) -> Iterator[CommitBundle]:
        if after_sequence < 0:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "after_sequence must be nonnegative",
                {"after_sequence": after_sequence},
            )
        bundles: list[CommitBundle] = []
        with self.read_snapshot() as conn:
            high_row = conn.execute("SELECT MAX(commit_sequence) FROM ledger_commits").fetchone()
            high = int(high_row[0]) if high_row and high_row[0] is not None else 0
            end = high if through_sequence is None else through_sequence
            if end < after_sequence:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "commit range inversion",
                    {"after_sequence": after_sequence, "through_sequence": through_sequence},
                )
            rows = conn.execute(
                """
                SELECT commit_sequence, commit_id, commit_hash, command_id, command_hash,
                       command_type, recorded_at_ns
                FROM ledger_commits
                WHERE commit_sequence > ? AND commit_sequence <= ?
                ORDER BY commit_sequence
                """,
                (after_sequence, end),
            ).fetchall()
            for row in rows:
                items = conn.execute(
                    """
                    SELECT record_type, record_id
                    FROM ledger_commit_items
                    WHERE commit_sequence = ?
                    ORDER BY item_ordinal
                    """,
                    (int(row["commit_sequence"]),),
                ).fetchall()
                records: list[AuthoritativeRecord] = []
                for item in items:
                    rec = _load_record(conn, str(item["record_type"]), str(item["record_id"]))
                    if rec is not None:
                        records.append(rec)
                bundles.append(
                    CommitBundle(
                        commit_sequence=int(row["commit_sequence"]),
                        commit_id=str(row["commit_id"]),
                        commit_hash=str(row["commit_hash"]),
                        command_id=str(row["command_id"]),
                        command_hash=str(row["command_hash"]),
                        command_type=str(row["command_type"]),
                        recorded_at_ns=int(row["recorded_at_ns"]),
                        records=tuple(records),
                    )
                )
        yield from bundles
