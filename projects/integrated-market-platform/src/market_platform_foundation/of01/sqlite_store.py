"""OF-01 SQLite authority store."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .canonical import RECORD_PROFILE
from .commands import (
    COMMAND_SCHEMA_VERSION,
    COMMIT_SCHEMA_VERSION,
    CommitReceipt,
    CommittedRecordRef,
    build_commit_hash,
    command_type_name,
)
from .errors import OF01Error, OF01ErrorCode
from .ids import new_uuid, validate_uuid
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

DEFAULT_BUSY_TIMEOUT_MS = 5000


def open_connection(db_path: Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> sqlite3.Connection:
    if busy_timeout_ms <= 0:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "busy_timeout must be positive",
            {"busy_timeout_ms": busy_timeout_ms},
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    configure_connection(conn, busy_timeout_ms=busy_timeout_ms)
    return conn


def configure_connection(conn: sqlite3.Connection, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA trusted_schema=OFF")
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")


class SQLiteAuthorityStore:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        ledger_authority_id: str,
        lock: threading.RLock | None = None,
    ) -> None:
        self._conn = conn
        self.ledger_authority_id = ledger_authority_id
        self._lock = lock or threading.RLock()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def integrity_ok(self) -> bool:
        with self._lock:
            row = self._conn.execute("PRAGMA quick_check").fetchone()
            return bool(row) and str(row[0]) == "ok"

    def foreign_keys_ok(self) -> bool:
        with self._lock:
            rows = list(self._conn.execute("PRAGMA foreign_key_check"))
            return len(rows) == 0

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def receipt(
        self,
        command_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> CommitReceipt | None:
        db = conn or self._conn
        row = db.execute(
            """
            SELECT commit_sequence, commit_id, commit_hash, command_hash
            FROM ledger_commits
            WHERE ledger_authority_id = ? AND command_id = ?
            """,
            (self.ledger_authority_id, command_id),
        ).fetchone()
        if row is None:
            return None
        items = db.execute(
            """
            SELECT item_ordinal, record_type, record_id, record_schema_version,
                   record_canonicalization_profile, record_hash
            FROM ledger_commit_items
            WHERE commit_sequence = ?
            ORDER BY item_ordinal
            """,
            (int(row["commit_sequence"]),),
        ).fetchall()
        refs = tuple(
            CommittedRecordRef(
                record_type=str(item["record_type"]),
                record_id=str(item["record_id"]),
                record_schema_version=int(item["record_schema_version"]),
                record_canonicalization_profile=str(item["record_canonicalization_profile"]),
                record_hash=str(item["record_hash"]),
                item_ordinal=int(item["item_ordinal"]),
            )
            for item in items
        )
        return CommitReceipt(
            ledger_authority_id=self.ledger_authority_id,
            command_id=command_id,
            command_hash=str(row["command_hash"]),
            commit_id=str(row["commit_id"]),
            commit_sequence=int(row["commit_sequence"]),
            commit_hash=str(row["commit_hash"]),
            records=refs,
            was_existing=True,
        )

    def next_commit_sequence(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT MAX(commit_sequence) FROM ledger_commits").fetchone()
        if row is None or row[0] is None:
            return 1
        return int(row[0]) + 1

    def insert_commit(
        self,
        conn: sqlite3.Connection,
        *,
        command_id: str,
        command_hash: str,
        command_type: str,
        commit_id: str,
        commit_sequence: int,
        recorded_at_ns: int,
        commit_hash_value: str,
        records: tuple[AuthoritativeRecord, ...],
    ) -> CommitReceipt:
        conn.execute(
            """
            INSERT INTO ledger_commits (
              commit_sequence, ledger_authority_id, commit_id,
              commit_schema_version, commit_canonicalization_profile, hash_profile,
              command_type, command_schema_version, command_canonicalization_profile,
              command_id, command_hash, recorded_at_ns, record_count, commit_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commit_sequence,
                self.ledger_authority_id,
                commit_id,
                COMMIT_SCHEMA_VERSION,
                "imp-of01-commit-canonical-json-v1",
                "imp-sha256-uppercase-hex-v1",
                command_type,
                COMMAND_SCHEMA_VERSION,
                "imp-of01-command-canonical-json-v1",
                command_id,
                command_hash,
                recorded_at_ns,
                len(records),
                commit_hash_value,
            ),
        )
        refs: list[CommittedRecordRef] = []
        for ordinal, rec in enumerate(records):
            rec_hash = record_hash(rec)
            rec_id = record_primary_id(rec)
            conn.execute(
                """
                INSERT INTO ledger_commit_items (
                  commit_sequence, item_ordinal, record_type, record_id,
                  record_schema_version, record_canonicalization_profile, record_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_sequence,
                    ordinal,
                    rec.record_type,
                    rec_id,
                    rec.to_canonical()["record_schema_version"],
                    RECORD_PROFILE,
                    rec_hash,
                ),
            )
            self._insert_typed_record(conn, rec, commit_sequence=commit_sequence, item_ordinal=ordinal)
            refs.append(
                CommittedRecordRef(
                    record_type=rec.record_type,
                    record_id=rec_id,
                    record_schema_version=rec.to_canonical()["record_schema_version"],
                    record_canonicalization_profile=RECORD_PROFILE,
                    record_hash=rec_hash,
                    item_ordinal=ordinal,
                )
            )
        return CommitReceipt(
            ledger_authority_id=self.ledger_authority_id,
            command_id=command_id,
            command_hash=command_hash,
            commit_id=commit_id,
            commit_sequence=commit_sequence,
            commit_hash=commit_hash_value,
            records=tuple(refs),
            was_existing=False,
        )

    def _insert_typed_record(
        self,
        conn: sqlite3.Connection,
        record: AuthoritativeRecord,
        *,
        commit_sequence: int,
        item_ordinal: int,
    ) -> None:
        rec_hash = record_hash(record)
        common = (
            record.record_type,
            record.to_canonical()["record_schema_version"],
            RECORD_PROFILE,
            rec_hash,
            commit_sequence,
            item_ordinal,
        )
        if isinstance(record, RunRecord):
            conn.execute(
                """
                INSERT INTO runs (
                  run_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, operation_class, objective,
                  consequence_profile, reproducibility_class, evidence_strength,
                  initiator_class, initiator_ref, trigger_type, trigger_ref,
                  registered_at_ns, attempt_concurrency, parallel_capacity,
                  provenance_qualifier, retention_class, sensitivity_class,
                  evaluation_protocol_ref, temporal_cutoff_bundle_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    *common,
                    record.operation_class,
                    record.objective,
                    record.consequence_profile.value,
                    record.reproducibility_class.value,
                    record.evidence_strength.value,
                    record.initiator_class.value,
                    record.initiator_ref,
                    record.trigger_type.value if record.trigger_type else None,
                    record.trigger_ref,
                    record.registered_at_ns,
                    record.attempt_concurrency.value,
                    record.parallel_capacity,
                    record.provenance_qualifier.value,
                    record.retention_class,
                    record.sensitivity_class.value,
                    record.evaluation_protocol_ref,
                    record.temporal_cutoff_bundle_ref,
                ),
            )
        elif isinstance(record, AttemptRecord):
            conn.execute(
                """
                INSERT INTO attempts (
                  attempt_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, attempt_sequence,
                  invocation_ref, environment_ref, predecessor_attempt_id,
                  checkpoint_ref_id, parallel_group, expected_start_after_ns,
                  expected_end_before_ns, retention_class, sensitivity_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.attempt_id,
                    *common,
                    record.run_id,
                    record.attempt_sequence,
                    record.invocation_ref,
                    record.environment_ref,
                    record.predecessor_attempt_id,
                    record.checkpoint_ref_id,
                    record.parallel_group,
                    record.expected_start_after_ns,
                    record.expected_end_before_ns,
                    record.retention_class,
                    record.sensitivity_class.value,
                ),
            )
        elif isinstance(record, RunTransitionRecord):
            conn.execute(
                """
                INSERT INTO run_transitions (
                  transition_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, predecessor_transition_id,
                  from_state, to_state, effective_at_ns, actor_type, actor_ref,
                  policy_ref, reason_code, terminal_disposition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.transition_id,
                    *common,
                    record.run_id,
                    record.predecessor_transition_id,
                    record.from_state.value if record.from_state else None,
                    record.to_state.value,
                    record.effective_at_ns,
                    record.actor_type.value,
                    record.actor_ref,
                    record.policy_ref,
                    record.reason_code,
                    record.terminal_disposition_id,
                ),
            )
        elif isinstance(record, AttemptTransitionRecord):
            conn.execute(
                """
                INSERT INTO attempt_transitions (
                  transition_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, attempt_id, predecessor_transition_id,
                  from_phase, to_phase, terminal_result, reason_family, reason_code,
                  started_at_ns, ended_at_ns, actor_type, actor_ref, evidence_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.transition_id,
                    *common,
                    record.attempt_id,
                    record.predecessor_transition_id,
                    record.from_phase.value if record.from_phase else None,
                    record.to_phase.value,
                    record.terminal_result.value if record.terminal_result else None,
                    record.reason_family.value if record.reason_family else None,
                    record.reason_code,
                    record.started_at_ns,
                    record.ended_at_ns,
                    record.actor_type.value,
                    record.actor_ref,
                    record.evidence_ref,
                ),
            )
        elif isinstance(record, OutcomeRecord):
            conn.execute(
                """
                INSERT INTO outcomes (
                  outcome_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, attempt_id, outcome_type,
                  result_ref, validity, evaluated_at_ns, effective_at_ns,
                  protocol_ref, supersedes_outcome_id, limitations,
                  retention_class, sensitivity_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.outcome_id,
                    *common,
                    record.run_id,
                    record.attempt_id,
                    record.outcome_type,
                    record.result_ref,
                    record.validity.value,
                    record.evaluated_at_ns,
                    record.effective_at_ns,
                    record.protocol_ref,
                    record.supersedes_outcome_id,
                    record.limitations,
                    record.retention_class,
                    record.sensitivity_class.value,
                ),
            )
        elif isinstance(record, DispositionRecord):
            conn.execute(
                """
                INSERT INTO dispositions (
                  disposition_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, outcome_id,
                  decision_at_ns, authority_type, authority_ref, policy_ref,
                  action_category, domain_code, prior_disposition_id,
                  limitations, retention_class, sensitivity_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.disposition_id,
                    *common,
                    record.run_id,
                    record.outcome_id,
                    record.decision_at_ns,
                    record.authority_type.value,
                    record.authority_ref,
                    record.policy_ref,
                    record.action_category.value,
                    record.domain_code,
                    record.prior_disposition_id,
                    record.limitations,
                    record.retention_class,
                    record.sensitivity_class.value,
                ),
            )
        elif isinstance(record, ArtifactRecord):
            conn.execute(
                """
                INSERT INTO artifacts (
                  artifact_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, logical_role, logical_name,
                  content_hash, hash_profile, byte_size, media_type, content_type,
                  producer_run_id, producer_attempt_id, completeness,
                  producer_terminal_result, validation_state, use_restriction,
                  mutability_class, retention_class, sensitivity_class,
                  cas_locator_profile, redaction_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    *common,
                    record.logical_role,
                    record.logical_name,
                    record.content_hash,
                    record.hash_profile,
                    record.byte_size,
                    record.media_type,
                    record.content_type,
                    record.producer_run_id,
                    record.producer_attempt_id,
                    record.completeness.value,
                    record.producer_terminal_result.value if record.producer_terminal_result else None,
                    record.validation_state.value,
                    record.use_restriction.value,
                    record.mutability_class,
                    record.retention_class,
                    record.sensitivity_class.value,
                    record.cas_locator_profile,
                    record.redaction_state.value,
                ),
            )
        elif isinstance(record, RelationshipRecord):
            conn.execute(
                """
                INSERT INTO relationships (
                  relationship_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, source_record_type,
                  source_record_id, relation_type, target_record_type,
                  target_record_id, effective_at_ns, acyclicity_class, relation_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.relationship_id,
                    *common,
                    record.source_record_type,
                    record.source_record_id,
                    record.relation_type.value,
                    record.target_record_type,
                    record.target_record_id,
                    record.effective_at_ns,
                    record.acyclicity_class.value,
                    record.relation_code,
                ),
            )
        elif isinstance(record, SourceAttributionRecord):
            conn.execute(
                """
                INSERT INTO source_attributions (
                  source_attribution_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, repository_identity,
                  root_identity, base_revision, source_state,
                  scope_manifest_artifact_id, capsule_artifact_id,
                  outside_scope_proof_artifact_id, limitations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_attribution_id,
                    *common,
                    record.run_id,
                    record.repository_identity,
                    record.root_identity,
                    record.base_revision,
                    record.source_state.value,
                    record.scope_manifest_artifact_id,
                    record.capsule_artifact_id,
                    record.outside_scope_proof_artifact_id,
                    record.limitations,
                ),
            )
        elif isinstance(record, ProvenanceReferenceRecord):
            conn.execute(
                """
                INSERT INTO provenance_references (
                  provenance_ref_id, record_type, record_schema_version,
                  record_canonicalization_profile, record_hash,
                  commit_sequence, item_ordinal, run_id, attempt_id,
                  reference_kind, canonical_identity, canonical_version,
                  canonical_hash, available_at_ns, coverage_start_ns,
                  coverage_end_ns, artifact_id, limitations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.provenance_ref_id,
                    *common,
                    record.run_id,
                    record.attempt_id,
                    record.reference_kind.value,
                    record.canonical_identity,
                    record.canonical_version,
                    record.canonical_hash,
                    record.available_at_ns,
                    record.coverage_start_ns,
                    record.coverage_end_ns,
                    record.artifact_id,
                    record.limitations,
                ),
            )
        else:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "unsupported record type for insert",
                {"record_type": getattr(record, "record_type", "unknown")},
            )

    def record_exists(
        self,
        conn: sqlite3.Connection,
        record_type: str,
        record_id: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1 FROM ledger_commit_items
            WHERE record_type = ? AND record_id = ?
            """,
            (record_type, record_id),
        ).fetchone()
        return row is not None

    def get_run_state(self, conn: sqlite3.Connection, run_id: str) -> str | None:
        row = conn.execute(
            """
            SELECT to_state FROM run_transitions
            WHERE run_id = ?
            ORDER BY commit_sequence DESC, item_ordinal DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def get_latest_run_transition_id(self, conn: sqlite3.Connection, run_id: str) -> str | None:
        row = conn.execute(
            """
            SELECT transition_id FROM run_transitions
            WHERE run_id = ?
            ORDER BY commit_sequence DESC, item_ordinal DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def get_attempt_phase(self, conn: sqlite3.Connection, attempt_id: str) -> str | None:
        row = conn.execute(
            """
            SELECT to_phase FROM attempt_transitions
            WHERE attempt_id = ?
            ORDER BY commit_sequence DESC, item_ordinal DESC
            LIMIT 1
            """,
            (attempt_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def count_nonterminal_attempts(self, conn: sqlite3.Connection, run_id: str) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM attempts a
            WHERE a.run_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM attempt_transitions t
                WHERE t.attempt_id = a.attempt_id AND t.to_phase = 'TERMINAL'
              )
            """,
            (run_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def allocate_commit_id() -> str:
    return new_uuid()
