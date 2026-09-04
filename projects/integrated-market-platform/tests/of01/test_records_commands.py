from __future__ import annotations

import unittest

from market_platform_foundation.of01.commands import CloseRun, command_record_plan
from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.records import (
    ActionCategory,
    ActorType,
    AttemptConcurrency,
    ConsequenceProfile,
    DispositionRecord,
    EvidenceStrength,
    InitiatorClass,
    ProvenanceQualifier,
    ReproducibilityClass,
    RunRecord,
    RunState,
    RunTransitionRecord,
    SensitivityClass,
)
from market_platform_foundation.of01.state_machine import validate_relationship


class TestRecordsCommands(unittest.TestCase):
    def test_close_run_orders_disposition_before_transition(self) -> None:
        run_id = new_uuid()
        disposition = DispositionRecord(
            disposition_id=new_uuid(),
            run_id=run_id,
            outcome_id=None,
            decision_at_ns=1,
            authority_type=ActorType.SYSTEM,
            authority_ref="test",
            policy_ref=None,
            action_category=ActionCategory.CANCEL,
            domain_code="TEST",
            prior_disposition_id=None,
            limitations=None,
            retention_class="RET_OPERATIONAL",
            sensitivity_class=SensitivityClass.INTERNAL,
        )
        transition = RunTransitionRecord(
            transition_id=new_uuid(),
            run_id=run_id,
            predecessor_transition_id=new_uuid(),
            from_state=RunState.ACTIVE,
            to_state=RunState.CLOSED,
            effective_at_ns=2,
            actor_type=ActorType.SYSTEM,
            actor_ref="test",
            policy_ref=None,
            reason_code="RUN_CLOSED",
            terminal_disposition_id=disposition.disposition_id,
        )
        command = CloseRun(
            disposition=disposition,
            terminal_transition=transition,
            expected_run_transition_id=new_uuid(),
        )
        plan = command_record_plan(command)
        self.assertEqual(plan[0].record_type, "DISPOSITION")
        self.assertEqual(plan[1].record_type, "RUN_TRANSITION")

    def test_relationship_endpoint_validation(self) -> None:
        validate_relationship(
            relation_type="PRODUCES_ARTIFACT",
            source_record_type="RUN",
            target_record_type="ARTIFACT",
        )
        with self.assertRaises(OF01Error):
            validate_relationship(
                relation_type="PRODUCES_ARTIFACT",
                source_record_type="ARTIFACT",
                target_record_type="RUN",
            )


if __name__ == "__main__":
    unittest.main()
