"""Golden tests for optional evidence capture-context sidecars."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "evidence_capture"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.evidence_capture import (  # noqa: E402
    CAPTURE_CONTEXT_SCHEMA_VERSION,
    CaptureContextError,
    create_capture_context_sidecar,
    default_sidecar_path_for_artifact,
    infer_artifact_evidence_class,
    verify_capture_context_sidecar,
)


class EvidenceCaptureContextTests(unittest.TestCase):
    def test_infer_fixture_evidence_class_from_watch_payload(self) -> None:
        artifact = FIXTURES / "receipt_fixture.json"
        inferred = infer_artifact_evidence_class(artifact)
        self.assertEqual(inferred, "NON_EMPIRICAL_FIXTURE")

    def test_create_and_verify_sidecar_golden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            artifact = work / "receipt.json"
            artifact.write_text((FIXTURES / "receipt_fixture.json").read_text(encoding="utf-8"), encoding="utf-8")
            sidecar = default_sidecar_path_for_artifact(artifact)
            record = create_capture_context_sidecar(
                artifact_path=artifact,
                sidecar_path=sidecar,
                campaign="FTEP-V1-002",
                provider="finviz.elite.context",
                command="python tools/ftep_watch_catalysts.py --dry-run",
                working_directory="projects/integrated-market-platform",
                operator_run_id="ECC-GOLDENFIXTURE01",
                captured_at_ns=1_789_322_400_000_000_000,
                temporary_gate_states={"IMP_PROSPECTIVE_CATALYST_INGRESS": False},
                repository_root=ROOT,
            )
            self.assertEqual(record["schema_version"], CAPTURE_CONTEXT_SCHEMA_VERSION)
            self.assertFalse(record["orders_placed"])
            self.assertFalse(record["empirical_lock_created"])
            self.assertEqual(record["evidence_class"], "NON_EMPIRICAL_FIXTURE")
            result = verify_capture_context_sidecar(sidecar_path=sidecar)
            self.assertEqual(result["disposition"], "VALID")

    def test_verify_fails_when_artifact_mutated_after_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            artifact = work / "receipt.json"
            artifact.write_text('{"evidence_class":"SOFTWARE"}', encoding="utf-8")
            sidecar = default_sidecar_path_for_artifact(artifact)
            create_capture_context_sidecar(
                artifact_path=artifact,
                sidecar_path=sidecar,
                campaign="FTEP-V1-002",
                repository_root=ROOT,
            )
            artifact.write_text('{"evidence_class":"SOFTWARE","mutated":true}', encoding="utf-8")
            with self.assertRaises(CaptureContextError) as ctx:
                verify_capture_context_sidecar(sidecar_path=sidecar)
            self.assertIn("ARTIFACT_SHA256_MISMATCH", str(ctx.exception))

    def test_sidecar_cannot_upgrade_evidence_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            artifact = work / "receipt.json"
            artifact.write_text(
                json.dumps(
                    {
                        "evidence_class": "SOFTWARE",
                        "attention_data_kind": "FIXTURE_SMOKE",
                        "dry_run": True,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(CaptureContextError):
                create_capture_context_sidecar(
                    artifact_path=artifact,
                    sidecar_path=default_sidecar_path_for_artifact(artifact),
                    campaign="FTEP-V1-002",
                    evidence_class="PROSPECTIVE_OBSERVATIONAL",
                    repository_root=ROOT,
                )

    def test_no_secrets_leaked_in_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            artifact = work / "receipt.json"
            artifact.write_text('{"evidence_class":"SOFTWARE"}', encoding="utf-8")
            with self.assertRaises(CaptureContextError):
                create_capture_context_sidecar(
                    artifact_path=artifact,
                    sidecar_path=default_sidecar_path_for_artifact(artifact),
                    campaign="FTEP-V1-002",
                    temporary_gate_states={"finviz_api_token": "super-secret-value"},
                    repository_root=ROOT,
                )

    def test_cli_create_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            artifact = work / "receipt.json"
            artifact.write_text((FIXTURES / "receipt_fixture.json").read_text(encoding="utf-8"), encoding="utf-8")
            sidecar = work / "receipt.capture-context.json"
            create_cmd = [
                sys.executable,
                str(ROOT / "tools" / "evidence_capture_context.py"),
                "create",
                "--artifact",
                str(artifact),
                "--sidecar",
                str(sidecar),
                "--campaign",
                "FTEP-V1-002",
                "--provider",
                "finviz.elite.context",
            ]
            created = subprocess.run(create_cmd, cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, msg=created.stderr)
            verify_cmd = [
                sys.executable,
                str(ROOT / "tools" / "evidence_capture_context.py"),
                "--json",
                "verify",
                "--sidecar",
                str(sidecar),
            ]
            completed = subprocess.run(verify_cmd, cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["disposition"], "VALID")


if __name__ == "__main__":
    unittest.main()
