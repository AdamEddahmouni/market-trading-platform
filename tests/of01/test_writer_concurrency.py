from __future__ import annotations

import multiprocessing
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.commands import CommandEnvelope, RegisterRun, compute_command_hash
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.records import (
    ActorType,
    AttemptConcurrency,
    ConsequenceProfile,
    EvidenceStrength,
    InitiatorClass,
    ProvenanceQualifier,
    ReproducibilityClass,
    RunRecord,
    RunState,
    RunTransitionRecord,
    SensitivityClass,
)
from market_platform_foundation.of01.writer import WriterProcessLock, open_writer

AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _make_register_run(run_id: str | None = None) -> RegisterRun:
    run_id = run_id or new_uuid()
    transition_id = new_uuid()
    run = RunRecord(
        run_id=run_id,
        operation_class="VALIDATION",
        objective="concurrency test",
        consequence_profile=ConsequenceProfile.C1_OPERATIONAL,
        reproducibility_class=ReproducibilityClass.R1_OBSERVATION_ONLY,
        evidence_strength=EvidenceStrength.E1_DIAGNOSTIC,
        initiator_class=InitiatorClass.SYSTEM,
        initiator_ref="test",
        trigger_type=None,
        trigger_ref=None,
        registered_at_ns=1,
        attempt_concurrency=AttemptConcurrency.SEQUENTIAL,
        parallel_capacity=None,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        retention_class="RET_OPERATIONAL",
        sensitivity_class=SensitivityClass.INTERNAL,
        evaluation_protocol_ref=None,
        temporal_cutoff_bundle_ref=None,
    )
    transition = RunTransitionRecord(
        transition_id=transition_id,
        run_id=run_id,
        predecessor_transition_id=None,
        from_state=None,
        to_state=RunState.REGISTERED,
        effective_at_ns=1,
        actor_type=ActorType.SYSTEM,
        actor_ref="test",
        policy_ref=None,
        reason_code="RUN_REGISTERED",
        terminal_disposition_id=None,
    )
    return RegisterRun(run=run, initial_transition=transition)


def _envelope(command: RegisterRun, command_id: str | None = None) -> CommandEnvelope:
    command_id = command_id or new_uuid()
    return CommandEnvelope(
        command_id=command_id,
        command_type="RegisterRun",
        command_schema_version=1,
        command_canonicalization_profile="imp-of01-command-canonical-json-v1",
        command_hash=compute_command_hash(command),
        command=command,
    )


class TestWriterConcurrency(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "ledger.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_concurrent_same_command_returns_same_receipt(self) -> None:
        writer = open_writer(
            self.db_path,
            ledger_authority_id=AUTHORITY_ID,
            acquire_lock=False,
        )
        try:
            command = _make_register_run()
            envelope = _envelope(command)
            first = writer.submit(envelope)
            second = writer.submit(envelope)
            self.assertEqual(first.commit_id, second.commit_id)
        finally:
            writer.close()

    def test_command_id_conflict_on_different_hash(self) -> None:
        writer = open_writer(
            self.db_path,
            ledger_authority_id=AUTHORITY_ID,
            acquire_lock=False,
        )
        try:
            command_a = _make_register_run()
            command_id = new_uuid()
            writer.submit(_envelope(command_a, command_id=command_id))
            command_b = _make_register_run(run_id=new_uuid())
            envelope_b = CommandEnvelope(
                command_id=command_id,
                command_type="RegisterRun",
                command_schema_version=1,
                command_canonicalization_profile="imp-of01-command-canonical-json-v1",
                command_hash=compute_command_hash(command_b),
                command=command_b,
            )
            with self.assertRaises(OF01Error) as ctx:
                writer.submit(envelope_b)
            self.assertEqual(ctx.exception.code, OF01ErrorCode.COMMAND_ID_CONFLICT)
        finally:
            writer.close()


def _second_writer_worker(lock_path: str, result_queue: multiprocessing.Queue) -> None:
    try:
        lock = WriterProcessLock(Path(lock_path))
        lock.acquire()
        result_queue.put("acquired")
        lock.release()
    except OF01Error as exc:
        result_queue.put(exc.code.value)


class TestProcessLock(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lock_path = self.root / "writer.lock"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_second_lock_denied(self) -> None:
        first = WriterProcessLock(self.lock_path)
        first.acquire()
        second = WriterProcessLock(self.lock_path)
        with self.assertRaises(OF01Error) as ctx:
            second.acquire()
        self.assertEqual(ctx.exception.code, OF01ErrorCode.MULTIPLE_WRITERS)
        first.release()

    def test_subprocess_cannot_acquire_existing_lock(self) -> None:
        first = WriterProcessLock(self.lock_path)
        first.acquire()
        try:
            ctx = multiprocessing.get_context("spawn")
            result_queue: multiprocessing.Queue = ctx.Queue()
            proc = ctx.Process(
                target=_second_writer_worker,
                args=(str(self.lock_path), result_queue),
            )
            proc.start()
            proc.join(timeout=30)
            code = result_queue.get(timeout=5)
            self.assertEqual(code, OF01ErrorCode.MULTIPLE_WRITERS.value)
        finally:
            first.release()


if __name__ == "__main__":
    unittest.main()
