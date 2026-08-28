"""OF-01 authoritative ledger writer with process lock and idempotency."""

from __future__ import annotations

import atexit
import os
import queue
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cas import LocalCAS
from .commands import (
    AppendAttemptTransition,
    CommandEnvelope,
    CommitReceipt,
    LedgerCommand,
    PreparedArtifactToken,
    RegisterArtifact,
    build_commit_hash,
    command_record_plan,
    command_type_name,
    require_same_hash,
    validate_command_envelope,
)
from .errors import OF01Error, OF01ErrorCode
from .ids import new_uuid
from .records import AuthoritativeRecord, record_primary_id
from .sqlite_store import SQLiteAuthorityStore, allocate_commit_id
from .state_machine import validate_command_preconditions, validate_relationship


@dataclass(frozen=True, slots=True)
class WriterConfig:
    queue_capacity: int = 64
    busy_timeout_ms: int = 5000


class WriterProcessLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._fd: int | None = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._fd, str(os.getpid()).encode("ascii"))
        except FileExistsError as exc:
            raise OF01Error(
                OF01ErrorCode.MULTIPLE_WRITERS,
                "another writer process holds the lock",
                {"lock_path": str(self.lock_path)},
            ) from exc

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> WriterProcessLock:
        self.acquire()
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()


class SQLiteAuthoritativeLedgerWriter:
    def __init__(
        self,
        store: SQLiteAuthorityStore,
        *,
        cas: LocalCAS | None = None,
        config: WriterConfig | None = None,
        process_lock: WriterProcessLock | None = None,
        commit_id_allocator: Callable[[], str] | None = None,
        recorded_at_ns_allocator: Callable[[], int] | None = None,
        close_store_on_close: bool = False,
    ) -> None:
        self._store = store
        self._cas = cas
        self._config = config or WriterConfig()
        self._process_lock = process_lock
        self._commit_id_allocator = commit_id_allocator or allocate_commit_id
        self._recorded_at_ns_allocator = recorded_at_ns_allocator or time.time_ns
        self._close_store_on_close = close_store_on_close
        self._queue: queue.Queue[tuple[CommandEnvelope, Mapping[str, PreparedArtifactToken], threading.Event, list]] = (
            queue.Queue(maxsize=self._config.queue_capacity)
        )
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._closed = False
        self._worker.start()
        if self._process_lock is not None:
            atexit.register(self.close)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put((_SENTINEL, {}, threading.Event(), []))  # type: ignore[arg-type]
        self._worker.join(timeout=30)
        if self._process_lock is not None:
            self._process_lock.release()
        if self._close_store_on_close:
            self._store.close()

    def submit(
        self,
        envelope: CommandEnvelope,
        prepared_artifacts: Mapping[str, PreparedArtifactToken] | None = None,
    ) -> CommitReceipt:
        if self._closed:
            raise OF01Error(
                OF01ErrorCode.SHUTDOWN_IN_PROGRESS,
                "writer is shut down",
                {},
            )
        validate_command_envelope(envelope)
        existing = self._store.receipt(envelope.command_id)
        if existing is not None:
            return require_same_hash(existing, envelope.command_hash)
        tokens = prepared_artifacts or {}
        self._validate_prepared_artifacts(envelope, tokens)
        self._publish_artifacts(envelope, tokens)
        done = threading.Event()
        result_box: list[CommitReceipt | BaseException] = []
        try:
            self._queue.put((envelope, tokens, done, result_box), timeout=30)
        except queue.Full as exc:
            ambiguous = self._store.receipt(envelope.command_id)
            if ambiguous is not None:
                return require_same_hash(ambiguous, envelope.command_hash)
            raise OF01Error(
                OF01ErrorCode.ADMISSION_BACKPRESSURE,
                "writer queue is full",
                {},
            ) from exc
        if not done.wait(timeout=60):
            ambiguous = self._store.receipt(envelope.command_id)
            if ambiguous is not None:
                return require_same_hash(ambiguous, envelope.command_hash)
            raise OF01Error(
                OF01ErrorCode.AMBIGUOUS_COMMIT,
                "command timed out before acknowledgement",
                {"command_id": envelope.command_id},
            )
        if not result_box:
            ambiguous = self._store.receipt(envelope.command_id)
            if ambiguous is not None:
                return require_same_hash(ambiguous, envelope.command_hash)
            raise OF01Error(
                OF01ErrorCode.AMBIGUOUS_COMMIT,
                "command completed without result",
                {"command_id": envelope.command_id},
            )
        result = result_box[0]
        if isinstance(result, BaseException):
            raise result
        return result

    def resolve_command(self, command_id: str) -> CommitReceipt | None:
        return self._store.receipt(command_id)

    def _worker_loop(self) -> None:
        while True:
            envelope, tokens, done, result_box = self._queue.get()
            if envelope is _SENTINEL:
                done.set()
                break
            try:
                receipt = self._commit_command(envelope, tokens)
                result_box.append(receipt)
            except BaseException as exc:
                result_box.append(exc)
            finally:
                done.set()

    def _validate_prepared_artifacts(
        self,
        envelope: CommandEnvelope,
        tokens: Mapping[str, PreparedArtifactToken],
    ) -> None:
        if isinstance(envelope.command, RegisterArtifact):
            token = tokens.get(envelope.command.artifact.artifact_id)
            if token is None:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "missing prepared artifact token",
                    {"artifact_id": envelope.command.artifact.artifact_id},
                )
            artifact = envelope.command.artifact
            if token.content_hash != artifact.content_hash:
                raise OF01Error(
                    OF01ErrorCode.CAS_HASH_MISMATCH,
                    "artifact token hash mismatch",
                    {},
                )
            if token.byte_size != artifact.byte_size:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "artifact token size mismatch",
                    {},
                )

    def _publish_artifacts(
        self,
        envelope: CommandEnvelope,
        tokens: Mapping[str, PreparedArtifactToken],
    ) -> None:
        if self._cas is None:
            if tokens:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "CAS store required for artifact commands",
                    {},
                )
            return
        if isinstance(envelope.command, RegisterArtifact):
            token = tokens[envelope.command.artifact.artifact_id]
            from .cas import PreparedObject

            prepared = PreparedObject(
                temp_path=Path(token.temp_path),
                content_hash=token.content_hash,
                byte_size=token.byte_size,
                operation_id=token.operation_id,
            )
            self._cas.publish(prepared)

    def _commit_command(
        self,
        envelope: CommandEnvelope,
        tokens: Mapping[str, PreparedArtifactToken],
    ) -> CommitReceipt:
        existing = self._store.receipt(envelope.command_id)
        if existing is not None:
            return require_same_hash(existing, envelope.command_hash)
        records = command_record_plan(envelope.command)
        self._preflight_domain_ids(records)
        with self._store.write_transaction() as conn:
            existing = self._store.receipt(envelope.command_id, conn=conn)
            if existing is not None:
                return require_same_hash(existing, envelope.command_hash)
            validate_command_preconditions(
                conn,
                envelope.command,
                get_run_state=self._store.get_run_state,
                get_latest_run_transition_id=self._store.get_latest_run_transition_id,
                get_attempt_phase=self._store.get_attempt_phase,
                count_nonterminal_attempts=self._store.count_nonterminal_attempts,
                record_exists=self._store.record_exists,
            )
            self._validate_in_transaction(conn, envelope.command, records, tokens)
            commit_id = self._commit_id_allocator()
            commit_sequence = self._store.next_commit_sequence(conn)
            recorded_at_ns = self._recorded_at_ns_allocator()
            commit_hash_value = build_commit_hash(
                ledger_authority_id=self._store.ledger_authority_id,
                command_id=envelope.command_id,
                command_hash=envelope.command_hash,
                command_type=command_type_name(envelope.command),
                commit_id=commit_id,
                commit_sequence=commit_sequence,
                recorded_at_ns=recorded_at_ns,
                records=records,
            )
            return self._store.insert_commit(
                conn,
                command_id=envelope.command_id,
                command_hash=envelope.command_hash,
                command_type=command_type_name(envelope.command),
                commit_id=commit_id,
                commit_sequence=commit_sequence,
                recorded_at_ns=recorded_at_ns,
                commit_hash_value=commit_hash_value,
                records=records,
            )

    def _preflight_domain_ids(self, records: tuple[AuthoritativeRecord, ...]) -> None:
        for rec in records:
            rec_id = record_primary_id(rec)
            if self._store.record_exists(self._store.connection, rec.record_type, rec_id):
                raise OF01Error(
                    OF01ErrorCode.DOMAIN_ID_CONFLICT,
                    "domain record id already exists",
                    {"record_type": rec.record_type, "record_id": rec_id},
                )

    def _validate_in_transaction(
        self,
        conn,
        command: LedgerCommand,
        records: tuple[AuthoritativeRecord, ...],
        tokens: Mapping[str, PreparedArtifactToken] | None = None,
    ) -> None:
        from .records import RelationshipRecord
        from .commands import AttachProvenanceReference, AttachSourceAttribution
        from .source_attribution import (
            validate_attach_provenance_reference,
            validate_attach_source_attribution,
        )

        if isinstance(command, AttachSourceAttribution):
            validate_attach_source_attribution(command, tokens or {})
        if isinstance(command, AttachProvenanceReference):
            validate_attach_provenance_reference(command)

        for rec in records:
            if isinstance(rec, RelationshipRecord):
                validate_relationship(
                    relation_type=rec.relation_type.value,
                    source_record_type=rec.source_record_type,
                    target_record_type=rec.target_record_type,
                )
        if isinstance(command, AppendAttemptTransition) and command.expected_parallel_active_count is not None:
            from .records import AttemptRecord

            attempt_id = command.transition.attempt_id
            row = conn.execute(
                "SELECT run_id FROM attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise OF01Error(
                    OF01ErrorCode.MISSING_REFERENCE,
                    "attempt does not exist",
                    {"attempt_id": attempt_id},
                )
            run_row = conn.execute(
                "SELECT attempt_concurrency, parallel_capacity FROM runs WHERE run_id = ?",
                (str(row["run_id"]),),
            ).fetchone()
            if run_row is None:
                raise OF01Error(
                    OF01ErrorCode.MISSING_REFERENCE,
                    "run does not exist",
                    {},
                )
            from .state_machine import validate_sequential_attempt_capacity

            validate_sequential_attempt_capacity(
                conn,
                run_id=str(row["run_id"]),
                attempt_concurrency=str(run_row["attempt_concurrency"]),
                parallel_capacity=(
                    int(run_row["parallel_capacity"])
                    if run_row["parallel_capacity"] is not None
                    else None
                ),
                expected_parallel_active_count=command.expected_parallel_active_count,
                count_nonterminal_attempts=self._store.count_nonterminal_attempts,
            )


_SENTINEL = object()


def open_writer(
    db_path: Path,
    *,
    ledger_authority_id: str,
    cas_root: Path | None = None,
    lock_path: Path | None = None,
    config: WriterConfig | None = None,
    acquire_lock: bool = True,
    **allocator_kwargs: Any,
) -> SQLiteAuthoritativeLedgerWriter:
    from .migrations import open_authority

    conn = open_authority(
        db_path,
        ledger_authority_id=ledger_authority_id,
        busy_timeout_ms=(config.busy_timeout_ms if config else WriterConfig().busy_timeout_ms),
    )
    store = SQLiteAuthorityStore(conn, ledger_authority_id=ledger_authority_id)
    cas = LocalCAS(cas_root) if cas_root is not None else None
    process_lock = None
    if acquire_lock:
        lock_file = lock_path or (db_path.parent / f"{ledger_authority_id}.writer.lock")
        process_lock = WriterProcessLock(lock_file)
        process_lock.acquire()
    return SQLiteAuthoritativeLedgerWriter(
        store,
        cas=cas,
        config=config,
        process_lock=process_lock,
        close_store_on_close=True,
        **allocator_kwargs,
    )
