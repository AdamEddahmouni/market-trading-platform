from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.canonical import HASH_PROFILE
from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.commands import (
    CommandEnvelope,
    PreparedArtifactToken,
    RegisterArtifact,
    RegisterRun,
    compute_command_hash,
)
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.records import (
    ActorType,
    AttemptConcurrency,
    Completeness,
    ConsequenceProfile,
    EvidenceStrength,
    InitiatorClass,
    ProvenanceQualifier,
    RedactionState,
    ReproducibilityClass,
    RunRecord,
    RunState,
    RunTransitionRecord,
    SensitivityClass,
    UseRestriction,
    ValidationState,
    ArtifactRecord,
)
from market_platform_foundation.of01.writer import open_writer

AUTHORITY_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _register_run_for_artifact(run_id: str) -> RegisterRun:
    transition_id = new_uuid()
    run = RunRecord(
        run_id=run_id,
        operation_class="VALIDATION",
        objective="artifact test",
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


class TestCAS(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cas = LocalCAS(Path(self.tmp.name) / "cas")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_prepare_publish_and_verify(self) -> None:
        payload = b"artifact-bytes-123"
        prepared = self.cas.prepare(io.BytesIO(payload))
        published = self.cas.publish(prepared)
        self.assertEqual(published.byte_size, len(payload))
        handle = self.cas.open_verified(published.content_hash)
        self.assertEqual(handle.read(), payload)

    def test_duplicate_publish_is_idempotent(self) -> None:
        payload = b"duplicate"
        prepared1 = self.cas.prepare(io.BytesIO(payload))
        published1 = self.cas.publish(prepared1)
        prepared2 = self.cas.prepare(io.BytesIO(payload))
        published2 = self.cas.publish(prepared2)
        self.assertEqual(published1.content_hash, published2.content_hash)
        self.assertTrue(published1.final_path.exists())

    def test_expected_hash_mismatch(self) -> None:
        with self.assertRaises(OF01Error) as ctx:
            self.cas.prepare(io.BytesIO(b"x"), expected_hash="A" * 64)
        self.assertEqual(ctx.exception.code, OF01ErrorCode.CAS_HASH_MISMATCH)

    def test_missing_object_raises(self) -> None:
        with self.assertRaises(OF01Error) as ctx:
            self.cas.open_verified("B" * 64)
        self.assertEqual(ctx.exception.code, OF01ErrorCode.CAS_REFERENCED_OBJECT_MISSING)

    def test_inventory_lists_objects(self) -> None:
        payload = b"inventory"
        prepared = self.cas.prepare(io.BytesIO(payload))
        published = self.cas.publish(prepared)
        hashes = {item.content_hash for item in self.cas.inventory()}
        self.assertIn(published.content_hash, hashes)


class TestArtifactCommands(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cas = LocalCAS(self.root / "cas")
        self.writer = open_writer(
            self.root / "ledger.sqlite3",
            ledger_authority_id=AUTHORITY_ID,
            cas_root=self.root / "cas",
            acquire_lock=False,
        )
        self.run_id = new_uuid()
        register = _register_run_for_artifact(self.run_id)
        self.writer.submit(
            CommandEnvelope(
                command_id=new_uuid(),
                command_type="RegisterRun",
                command_schema_version=1,
                command_canonicalization_profile="imp-of01-command-canonical-json-v1",
                command_hash=compute_command_hash(register),
                command=register,
            )
        )

    def tearDown(self) -> None:
        self.writer.close()
        self.tmp.cleanup()

    def test_register_artifact_commits_with_cas(self) -> None:
        payload = b"registered-artifact"
        prepared = self.cas.prepare(io.BytesIO(payload))
        artifact_id = new_uuid()
        artifact = ArtifactRecord(
            artifact_id=artifact_id,
            logical_role="OUTPUT",
            logical_name="result",
            content_hash=prepared.content_hash,
            hash_profile=HASH_PROFILE,
            byte_size=prepared.byte_size,
            media_type="application/octet-stream",
            content_type=None,
            producer_run_id=self.run_id,
            producer_attempt_id=None,
            completeness=Completeness.COMPLETE,
            producer_terminal_result=None,
            validation_state=ValidationState.NOT_VALIDATED,
            use_restriction=UseRestriction.UNRESTRICTED,
            mutability_class="IMMUTABLE_EVIDENCE",
            retention_class="RET_OPERATIONAL",
            sensitivity_class=SensitivityClass.INTERNAL,
            cas_locator_profile="imp-of01-local-cas-v1",
            redaction_state=RedactionState.NOT_APPLICABLE,
        )
        command = RegisterArtifact(artifact=artifact)
        token = PreparedArtifactToken(
            artifact_id=artifact_id,
            temp_path=str(prepared.temp_path),
            content_hash=prepared.content_hash,
            byte_size=prepared.byte_size,
            operation_id=prepared.operation_id,
        )
        receipt = self.writer.submit(
            CommandEnvelope(
                command_id=new_uuid(),
                command_type="RegisterArtifact",
                command_schema_version=1,
                command_canonicalization_profile="imp-of01-command-canonical-json-v1",
                command_hash=compute_command_hash(command),
                command=command,
            ),
            prepared_artifacts={artifact_id: token},
        )
        self.assertEqual(len(receipt.records), 1)
        self.cas.open_verified(prepared.content_hash)


if __name__ == "__main__":
    unittest.main()
