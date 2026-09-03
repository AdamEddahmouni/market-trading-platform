from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.commands import (
    AppendRunTransition,
    CommandEnvelope,
    RegisterRun,
    compute_command_hash,
)
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
from market_platform_foundation.of01.state_machine import validate_run_transition
from market_platform_foundation.of01.writer import open_writer

AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _register_run(run_id: str | None = None) -> tuple[RegisterRun, str]:
    run_id = run_id or new_uuid()
    transition_id = new_uuid()
    run = RunRecord(
        run_id=run_id,
        operation_class="VALIDATION",
        objective="lifecycle test",
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
    return RegisterRun(run=run, initial_transition=transition), transition_id


def _envelope(command, command_id: str | None = None) -> CommandEnvelope:
    command_id = command_id or new_uuid()
    return CommandEnvelope(
        command_id=command_id,
        command_type=type(command).__name__,
        command_schema_version=1,
        command_canonicalization_profile="imp-of01-command-canonical-json-v1",
        command_hash=compute_command_hash(command),
        command=command,
    )

class TestRunAttemptLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "ledger.sqlite3"
        self.writer = open_writer(
            self.db_path,
            ledger_authority_id=AUTHORITY_ID,
            acquire_lock=False,
        )

    def tearDown(self) -> None:
        self.writer.close()
        self.tmp.cleanup()

    def test_run_registered_to_active(self) -> None:
        register, initial_transition_id = _register_run()
        self.writer.submit(_envelope(register))
        active_transition_id = new_uuid()
        append = AppendRunTransition(
            transition=RunTransitionRecord(
                transition_id=active_transition_id,
                run_id=register.run.run_id,
                predecessor_transition_id=initial_transition_id,
                from_state=RunState.REGISTERED,
                to_state=RunState.ACTIVE,
                effective_at_ns=2,
                actor_type=ActorType.SYSTEM,
                actor_ref="test",
                policy_ref=None,
                reason_code="RUN_ACTIVE",
                terminal_disposition_id=None,
            ),
            expected_predecessor_transition_id=initial_transition_id,
        )
        receipt = self.writer.submit(_envelope(append))
        self.assertEqual(len(receipt.records), 1)

    def test_invalid_transition_rejected(self) -> None:
        with self.assertRaises(OF01Error):
            validate_run_transition(
                current_state=RunState.REGISTERED.value,
                from_state=RunState.REGISTERED.value,
                to_state=RunState.CLOSED.value,
            )

    def test_precondition_changed_on_stale_predecessor(self) -> None:
        register, initial_transition_id = _register_run()
        self.writer.submit(_envelope(register))
        active_transition_id = new_uuid()
        append = AppendRunTransition(
            transition=RunTransitionRecord(
                transition_id=active_transition_id,
                run_id=register.run.run_id,
                predecessor_transition_id=initial_transition_id,
                from_state=RunState.REGISTERED,
                to_state=RunState.ACTIVE,
                effective_at_ns=2,
                actor_type=ActorType.SYSTEM,
                actor_ref="test",
                policy_ref=None,
                reason_code="RUN_ACTIVE",
                terminal_disposition_id=None,
            ),
            expected_predecessor_transition_id=initial_transition_id,
        )
        self.writer.submit(_envelope(append))
        stale = AppendRunTransition(
            transition=RunTransitionRecord(
                transition_id=new_uuid(),
                run_id=register.run.run_id,
                predecessor_transition_id=initial_transition_id,
                from_state=RunState.REGISTERED,
                to_state=RunState.ACTIVE,
                effective_at_ns=3,
                actor_type=ActorType.SYSTEM,
                actor_ref="test",
                policy_ref=None,
                reason_code="RUN_ACTIVE",
                terminal_disposition_id=None,
            ),
            expected_predecessor_transition_id=initial_transition_id,
        )
        with self.assertRaises(OF01Error) as ctx:
            self.writer.submit(_envelope(stale))
        self.assertEqual(ctx.exception.code, OF01ErrorCode.PRECONDITION_CHANGED)


if __name__ == "__main__":
    unittest.main()
