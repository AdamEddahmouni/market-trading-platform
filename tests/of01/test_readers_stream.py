from __future__ import annotations

import unittest

from market_platform_foundation.of01.commands import CommandEnvelope, RegisterRun, compute_command_hash
from market_platform_foundation.of01.canonical import COMMAND_PROFILE
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.memory import InMemoryLedger
from market_platform_foundation.of01.protocols import DispositionScope, DispositionSelectionPolicyV1
from market_platform_foundation.of01.readers import SQLiteLedgerReader, select_current_disposition
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
from tests.of01.support import DisposableAuthority

COMMAND_SCHEMA_VERSION = 1


def _register_run_envelope(authority_id: str, run_id: str | None = None) -> CommandEnvelope:
    run_id = run_id or new_uuid()
    transition_id = new_uuid()
    command = RegisterRun(
        run=RunRecord(
            run_id=run_id,
            operation_class="VALIDATION",
            objective="reader test",
            consequence_profile=ConsequenceProfile.C1_OPERATIONAL,
            reproducibility_class=ReproducibilityClass.R3_INPUT_REPLAYABLE,
            evidence_strength=EvidenceStrength.E1_DIAGNOSTIC,
            initiator_class=InitiatorClass.SYSTEM,
            initiator_ref=None,
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
        ),
        initial_transition=RunTransitionRecord(
            transition_id=transition_id,
            run_id=run_id,
            predecessor_transition_id=None,
            from_state=None,
            to_state=RunState.REGISTERED,
            effective_at_ns=1,
            actor_type=ActorType.SYSTEM,
            actor_ref=None,
            policy_ref=None,
            reason_code="RUN_REGISTERED",
            terminal_disposition_id=None,
        ),
    )
    return CommandEnvelope(
        command_id=new_uuid(),
        command_type="RegisterRun",
        command_schema_version=COMMAND_SCHEMA_VERSION,
        command_canonicalization_profile=COMMAND_PROFILE,
        command_hash=compute_command_hash(command),
        command=command,
    )


class TestInMemoryStream(unittest.TestCase):
    def test_stream_commits_ordered(self) -> None:
        ledger = InMemoryLedger(new_uuid())
        ledger.submit(_register_run_envelope(ledger.ledger_authority_id))
        bundles = list(ledger.stream_commits(0))
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].commit_sequence, 1)
        self.assertEqual(len(bundles[0].records), 2)


class TestSQLiteReaders(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = DisposableAuthority()
        self.writer = self.auth.open_writer()
        self.reader = SQLiteLedgerReader(self.auth.store)

    def tearDown(self) -> None:
        self.writer.close()
        self.auth.close()

    def test_get_run_after_register(self) -> None:
        envelope = _register_run_envelope(self.auth.authority_id)
        run_id = envelope.command.run.run_id  # type: ignore[attr-defined]
        self.writer.submit(envelope)
        policy = DispositionSelectionPolicyV1(
            scope=DispositionScope.RUN.value,
            allowed_authority_types=frozenset({ActorType.SYSTEM.value}),
            allowed_action_categories=frozenset({"NO_ACTION"}),
        )
        view = self.reader.get_run(run_id, policy)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.run_id, run_id)
        self.assertEqual(view.current_state, "REGISTERED")
        self.assertGreaterEqual(view.as_of_commit_sequence, 1)

    def test_stream_rejects_inverted_range(self) -> None:
        with self.assertRaises(Exception):
            list(self.reader.stream_commits(5, 1))


if __name__ == "__main__":
    unittest.main()
