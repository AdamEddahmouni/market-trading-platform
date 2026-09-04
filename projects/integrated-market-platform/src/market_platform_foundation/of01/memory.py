"""In-memory contract test double for OF-01 writer semantics."""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from .commands import (
    CommandEnvelope,
    CommitReceipt,
    PreparedArtifactToken,
    build_commit_hash,
    command_record_plan,
    committed_refs_from_records,
    require_same_hash,
    validate_command,
)
from .errors import OF01Error, OF01ErrorCode
from .ids import new_uuid, validate_uuid
from .protocols import (
    AttemptView,
    CommitBundle,
    DispositionSelectionPolicyV1,
    LedgerCommit,
    RunView,
)
from .records import AuthoritativeRecord, RunRecord, record_primary_id


@dataclass
class _StoredCommit:
    receipt: CommitReceipt
    records: tuple[AuthoritativeRecord, ...]
    recorded_at_ns: int
    command_type: str


class InMemoryLedger:
    def __init__(self, ledger_authority_id: str) -> None:
        validate_uuid(ledger_authority_id, field="ledger_authority_id")
        self.ledger_authority_id = ledger_authority_id
        self._commits: list[_StoredCommit] = []
        self._receipts: dict[str, CommitReceipt] = {}
        self._record_index: dict[tuple[str, str], AuthoritativeRecord] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        envelope: CommandEnvelope,
        prepared_artifacts: Mapping[str, PreparedArtifactToken] | None = None,
    ) -> CommitReceipt:
        del prepared_artifacts
        validate_command(envelope)
        with self._lock:
            existing = self._receipts.get(envelope.command_id)
            if existing is not None:
                return require_same_hash(existing, envelope.command_hash)
            records = command_record_plan(envelope.command)
            for record in records:
                key = (record.record_type, record_primary_id(record))
                if key in self._record_index:
                    raise OF01Error(
                        OF01ErrorCode.DOMAIN_ID_CONFLICT,
                        "domain id already exists",
                        {"record_type": key[0], "record_id": key[1]},
                    )
            commit_sequence = len(self._commits) + 1
            commit_id = new_uuid()
            recorded_at_ns = commit_sequence
            commit_hash = build_commit_hash(
                ledger_authority_id=self.ledger_authority_id,
                command_id=envelope.command_id,
                command_hash=envelope.command_hash,
                command_type=envelope.command_type,
                commit_id=commit_id,
                commit_sequence=commit_sequence,
                recorded_at_ns=recorded_at_ns,
                records=records,
            )
            receipt = CommitReceipt(
                ledger_authority_id=self.ledger_authority_id,
                command_id=envelope.command_id,
                command_hash=envelope.command_hash,
                commit_id=commit_id,
                commit_sequence=commit_sequence,
                commit_hash=commit_hash,
                records=committed_refs_from_records(records),
                was_existing=False,
            )
            stored = _StoredCommit(
                receipt=receipt,
                records=records,
                recorded_at_ns=recorded_at_ns,
                command_type=envelope.command_type,
            )
            self._commits.append(stored)
            self._receipts[envelope.command_id] = receipt
            for record in records:
                self._record_index[(record.record_type, record_primary_id(record))] = record
            return receipt

    def resolve_command(self, command_id: str) -> CommitReceipt | None:
        with self._lock:
            receipt = self._receipts.get(command_id)
            if receipt is None:
                return None
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

    def get_record(self, record_type: str, record_id: str) -> AuthoritativeRecord | None:
        with self._lock:
            return self._record_index.get((record_type, record_id))

    def get_run(
        self,
        run_id: str,
        disposition_policy: DispositionSelectionPolicyV1,
    ) -> RunView | None:
        with self._lock:
            record = self._record_index.get(("RUN", run_id))
            if record is None or not isinstance(record, RunRecord):
                return None
            return RunView(
                run_id=run_id,
                as_of_commit_sequence=len(self._commits),
                current_state="REGISTERED",
                disposition_policy=disposition_policy,
                current_disposition_id=None,
            )

    def get_attempt(self, attempt_id: str) -> AttemptView | None:
        with self._lock:
            record = self._record_index.get(("ATTEMPT", attempt_id))
            if record is None:
                return None
            run_id = getattr(record, "run_id", "")
            return AttemptView(
                attempt_id=attempt_id,
                run_id=run_id,
                current_phase="PENDING",
                as_of_commit_sequence=len(self._commits),
            )

    def get_commit(self, commit_sequence: int) -> LedgerCommit | None:
        with self._lock:
            if commit_sequence < 1 or commit_sequence > len(self._commits):
                return None
            stored = self._commits[commit_sequence - 1]
            return LedgerCommit(
                commit_sequence=stored.receipt.commit_sequence,
                commit_id=stored.receipt.commit_id,
                commit_hash=stored.receipt.commit_hash,
                command_id=stored.receipt.command_id,
                command_hash=stored.receipt.command_hash,
                command_type=stored.command_type,
                recorded_at_ns=stored.recorded_at_ns,
                record_count=len(stored.records),
            )

    def stream_commits(
        self,
        after_sequence: int,
        through_sequence: int | None = None,
    ) -> Iterator[CommitBundle]:
        with self._lock:
            if after_sequence < 0:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "after_sequence must be nonnegative",
                    {"after_sequence": after_sequence},
                )
            end = len(self._commits) if through_sequence is None else through_sequence
            if end < after_sequence:
                raise OF01Error(
                    OF01ErrorCode.INVALID_COMMAND,
                    "commit range inversion",
                    {"after_sequence": after_sequence, "through_sequence": through_sequence},
                )
            for sequence in range(after_sequence + 1, end + 1):
                stored = self._commits[sequence - 1]
                yield CommitBundle(
                    commit_sequence=stored.receipt.commit_sequence,
                    commit_id=stored.receipt.commit_id,
                    commit_hash=stored.receipt.commit_hash,
                    command_id=stored.receipt.command_id,
                    command_hash=stored.receipt.command_hash,
                    command_type=stored.command_type,
                    recorded_at_ns=stored.recorded_at_ns,
                    records=stored.records,
                )
