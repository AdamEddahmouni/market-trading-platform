from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.of01.commands import (
    CommandEnvelope,
    RegisterRun,
    compute_command_hash,
)
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
    TriggerType,
)
from market_platform_foundation.of01.writer import open_writer

FIXTURE = Path(__file__).parent / "fixtures" / "golden_v1.json"
AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _golden_register_run() -> RegisterRun:
    fixture = load_json_strict(FIXTURE)
    assert isinstance(fixture, dict)
    run_data = fixture["command"]["run"]
    transition_data = fixture["command"]["initial_transition"]
    run = RunRecord(
        run_id=run_data["run_id"],
        operation_class=run_data["operation_class"],
        objective=run_data["objective"],
        consequence_profile=ConsequenceProfile(run_data["consequence_profile"]),
        reproducibility_class=ReproducibilityClass(run_data["reproducibility_class"]),
        evidence_strength=EvidenceStrength(run_data["evidence_strength"]),
        initiator_class=InitiatorClass(run_data["initiator_class"]),
        initiator_ref=run_data["initiator_ref"],
        trigger_type=TriggerType(run_data["trigger_type"]),
        trigger_ref=run_data["trigger_ref"],
        registered_at_ns=run_data["registered_at_ns"],
        attempt_concurrency=AttemptConcurrency(run_data["attempt_concurrency"]),
        parallel_capacity=run_data["parallel_capacity"],
        provenance_qualifier=ProvenanceQualifier(run_data["provenance_qualifier"]),
        retention_class=run_data["retention_class"],
        sensitivity_class=SensitivityClass(run_data["sensitivity_class"]),
        evaluation_protocol_ref=run_data["evaluation_protocol_ref"],
        temporal_cutoff_bundle_ref=run_data["temporal_cutoff_bundle_ref"],
    )
    transition = RunTransitionRecord(
        transition_id=transition_data["transition_id"],
        run_id=transition_data["run_id"],
        predecessor_transition_id=transition_data["predecessor_transition_id"],
        from_state=None,
        to_state=RunState(transition_data["to_state"]),
        effective_at_ns=transition_data["effective_at_ns"],
        actor_type=ActorType(transition_data["actor_type"]),
        actor_ref=transition_data["actor_ref"],
        policy_ref=transition_data["policy_ref"],
        reason_code=transition_data["reason_code"],
        terminal_disposition_id=transition_data["terminal_disposition_id"],
    )
    return RegisterRun(run=run, initial_transition=transition)


def _golden_envelope() -> CommandEnvelope:
    fixture = load_json_strict(FIXTURE)
    assert isinstance(fixture, dict)
    command = _golden_register_run()
    return CommandEnvelope(
        command_id=fixture["commit"]["command_id"],
        command_type="RegisterRun",
        command_schema_version=1,
        command_canonicalization_profile="imp-of01-command-canonical-json-v1",
        command_hash=fixture["command_hash"],
        command=command,
    )


class TestWriterAtomicity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "ledger.sqlite3"
        self.writer = open_writer(
            self.db_path,
            ledger_authority_id=AUTHORITY_ID,
            acquire_lock=False,
            commit_id_allocator=lambda: "33333333-3333-4333-8333-333333333333",
            recorded_at_ns_allocator=lambda: 1787923201000000000,
        )

    def tearDown(self) -> None:
        self.writer.close()

    def test_register_run_commits_golden_hash(self) -> None:
        fixture = load_json_strict(FIXTURE)
        assert isinstance(fixture, dict)
        receipt = self.writer.submit(_golden_envelope())
        self.assertFalse(receipt.was_existing)
        self.assertEqual(receipt.commit_sequence, 1)
        self.assertEqual(receipt.commit_hash, fixture["commit_hash"])
        self.assertEqual(len(receipt.records), 2)

    def test_idempotent_retry_returns_same_receipt(self) -> None:
        envelope = _golden_envelope()
        first = self.writer.submit(envelope)
        second = self.writer.submit(envelope)
        self.assertTrue(second.was_existing)
        self.assertEqual(first.commit_id, second.commit_id)
        self.assertEqual(first.commit_hash, second.commit_hash)

    def test_resolve_command_after_commit(self) -> None:
        envelope = _golden_envelope()
        receipt = self.writer.submit(envelope)
        resolved = self.writer.resolve_command(envelope.command_id)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.commit_id, receipt.commit_id)


if __name__ == "__main__":
    unittest.main()
