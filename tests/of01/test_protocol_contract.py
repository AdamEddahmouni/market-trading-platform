from __future__ import annotations

import importlib
import inspect
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.of01.canonical import COMMAND_PROFILE
from market_platform_foundation.of01.commands import (
    COMMAND_SCHEMA_VERSION,
    CommandEnvelope,
    RegisterRun,
    compute_command_hash,
)
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.memory import InMemoryLedger
from market_platform_foundation.of01.protocols import DispositionScope, DispositionSelectionPolicyV1
from market_platform_foundation.of01.records import (
    ActionCategory,
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

FIXTURE = Path(__file__).parent / "fixtures" / "golden_v1.json"
AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _golden_register_run() -> RegisterRun:
    run = RunRecord(
        run_id="11111111-1111-4111-8111-111111111111",
        operation_class="VALIDATION",
        objective="Run validation — café",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        reproducibility_class=ReproducibilityClass.R4_DETERMINISTIC_REPLAY,
        evidence_strength=EvidenceStrength.E2_GOVERNED_SYNTHETIC,
        initiator_class=InitiatorClass.CI,
        initiator_ref="github-actions",
        trigger_type=TriggerType.PULL_REQUEST,
        trigger_ref="refs/pull/42",
        registered_at_ns=1787923200000000000,
        attempt_concurrency=AttemptConcurrency.SEQUENTIAL,
        parallel_capacity=None,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        retention_class="RET_REPRODUCIBILITY",
        sensitivity_class=SensitivityClass.INTERNAL,
        evaluation_protocol_ref=None,
        temporal_cutoff_bundle_ref=None,
    )
    transition = RunTransitionRecord(
        transition_id="44444444-4444-4444-8444-444444444444",
        run_id="11111111-1111-4111-8111-111111111111",
        predecessor_transition_id=None,
        from_state=None,
        to_state=RunState.REGISTERED,
        effective_at_ns=1787923200000000000,
        actor_type=ActorType.CI,
        actor_ref="github-actions",
        policy_ref=None,
        reason_code="RUN_REGISTERED",
        terminal_disposition_id=None,
    )
    return RegisterRun(run=run, initial_transition=transition)


def _golden_envelope(command_id: str = "22222222-2222-4222-8222-222222222222") -> CommandEnvelope:
    command = _golden_register_run()
    return CommandEnvelope(
        command_id=command_id,
        command_type="RegisterRun",
        command_schema_version=COMMAND_SCHEMA_VERSION,
        command_canonicalization_profile=COMMAND_PROFILE,
        command_hash=compute_command_hash(command),
        command=command,
    )


class LedgerContractMixin:
    ledger_factory: type[InMemoryLedger]

    def make_ledger(self) -> InMemoryLedger:
        return self.ledger_factory(ledger_authority_id=AUTHORITY_ID)

    def test_same_id_same_hash_retry_returns_existing_receipt(self) -> None:
        ledger = self.make_ledger()
        envelope = _golden_envelope()
        first = ledger.submit(envelope)
        second = ledger.submit(envelope)
        self.assertFalse(first.was_existing)
        self.assertTrue(second.was_existing)
        self.assertEqual(first.commit_id, second.commit_id)
        self.assertEqual(first.commit_sequence, second.commit_sequence)
        resolved = ledger.resolve_command(envelope.command_id)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.commit_id, second.commit_id)

    def test_same_id_different_hash_conflicts(self) -> None:
        ledger = self.make_ledger()
        envelope = _golden_envelope()
        ledger.submit(envelope)
        other_command = _golden_register_run()
        other_run = RunRecord(
            run_id="11111111-1111-4111-8111-111111111111",
            operation_class="OTHER",
            objective="Different objective",
            consequence_profile=ConsequenceProfile.C2_GOVERNED,
            reproducibility_class=ReproducibilityClass.R4_DETERMINISTIC_REPLAY,
            evidence_strength=EvidenceStrength.E2_GOVERNED_SYNTHETIC,
            initiator_class=InitiatorClass.CI,
            initiator_ref="github-actions",
            trigger_type=TriggerType.PULL_REQUEST,
            trigger_ref="refs/pull/42",
            registered_at_ns=1787923200000000000,
            attempt_concurrency=AttemptConcurrency.SEQUENTIAL,
            parallel_capacity=None,
            provenance_qualifier=ProvenanceQualifier.NATIVE,
            retention_class="RET_REPRODUCIBILITY",
            sensitivity_class=SensitivityClass.INTERNAL,
            evaluation_protocol_ref=None,
            temporal_cutoff_bundle_ref=None,
        )
        other = RegisterRun(run=other_run, initial_transition=other_command.initial_transition)
        conflicting = CommandEnvelope(
            command_id=envelope.command_id,
            command_type="RegisterRun",
            command_schema_version=COMMAND_SCHEMA_VERSION,
            command_canonicalization_profile=COMMAND_PROFILE,
            command_hash=compute_command_hash(other),
            command=other,
        )
        with self.assertRaises(OF01Error) as ctx:
            ledger.submit(conflicting)
        self.assertEqual(ctx.exception.code, OF01ErrorCode.COMMAND_ID_CONFLICT)

    def test_domain_id_collision(self) -> None:
        ledger = self.make_ledger()
        ledger.submit(_golden_envelope("22222222-2222-4222-8222-222222222222"))
        with self.assertRaises(OF01Error) as ctx:
            ledger.submit(_golden_envelope("99999999-9999-4999-8999-999999999999"))
        self.assertEqual(ctx.exception.code, OF01ErrorCode.DOMAIN_ID_CONFLICT)

    def test_ordered_multi_record_receipt(self) -> None:
        ledger = self.make_ledger()
        receipt = ledger.submit(_golden_envelope())
        self.assertEqual(len(receipt.records), 2)
        self.assertEqual(receipt.records[0].item_ordinal, 0)
        self.assertEqual(receipt.records[0].record_type, "RUN")
        self.assertEqual(receipt.records[1].item_ordinal, 1)
        self.assertEqual(receipt.records[1].record_type, "RUN_TRANSITION")

    def test_typed_reads_and_stream_order(self) -> None:
        ledger = self.make_ledger()
        ledger.submit(_golden_envelope())
        run = ledger.get_record("RUN", "11111111-1111-4111-8111-111111111111")
        self.assertIsNotNone(run)
        view = ledger.get_run(
            "11111111-1111-4111-8111-111111111111",
            DispositionSelectionPolicyV1(
                scope=DispositionScope.RUN.value,
                allowed_authority_types=frozenset({"SYSTEM"}),
                allowed_action_categories=frozenset({ActionCategory.NO_ACTION.value}),
            ),
        )
        self.assertIsNotNone(view)
        bundles = list(ledger.stream_commits(0))
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].commit_sequence, 1)
        self.assertEqual(len(bundles[0].records), 2)


class TestInMemoryLedgerContract(LedgerContractMixin, unittest.TestCase):
    ledger_factory = InMemoryLedger


class TestPortableSurface(unittest.TestCase):
    def test_domain_package_has_no_sqlite_or_mongo_imports(self) -> None:
        for module_name in (
            "market_platform_foundation.of01.commands",
            "market_platform_foundation.of01.records",
            "market_platform_foundation.of01.protocols",
            "market_platform_foundation.of01.memory",
        ):
            module = importlib.import_module(module_name)
            source = inspect.getsource(module)
            self.assertNotIn("sqlite3", source, module_name)
            self.assertNotIn("pymongo", source, module_name)
            self.assertNotIn("motor", source, module_name)

    def test_golden_fixture_command_hash(self) -> None:
        fixture = load_json_strict(FIXTURE)
        assert isinstance(fixture, dict)
        envelope = _golden_envelope()
        self.assertEqual(envelope.command_hash, fixture["command_hash"])


if __name__ == "__main__":
    unittest.main()
