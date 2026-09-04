import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.postroot.build_postroot_suite_approval import (
    build_approval_record,
    build_record_without_id,
    validate_inputs,
)
from tools.postroot.contract_core import canonical_bytes, sha256_bytes, validate_contract
from tools.postroot.suite_contracts import build_contract_schemas
from tools.postroot.suite_definition import PROCEDURE_ID, PROCEDURE_SHA256, SUITE_LOGICAL_ID

ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = ROOT / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
BUILDER = ROOT / "tools/postroot/build_postroot_suite_approval.py"
SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'};{ROOT}"}

APPROVAL_FIELDS = {
    "approval_record_id",
    "approved_at",
    "approved_by_principal_id",
    "approved_capacities",
    "approved_logical_id",
    "approved_sha256",
    "approval_scope",
    "procedure_id",
    "procedure_sha256",
    "status",
}

SUITE_SHA256 = "84431668E9F5103362D1A6275B235D8003A0BD600CAF694A4B0A4999C70F330F"
VALID_TIMESTAMP = "2099-12-31T23:59:59.999999999Z"


class SuiteApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SUITE_PATH.is_file():
            self.skipTest("committed suite not generated yet")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name) / "approval.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_builder(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILDER), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=SUBPROCESS_ENV,
        )

    def test_missing_required_arguments(self):
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)

    def test_wrong_suite_hash(self):
        result = self.run_builder(
            "--approved-suite-sha256",
            "0" * 64,
            "--approved-at",
            VALID_TIMESTAMP,
            "--write",
            str(self.output),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APPROVED-SUITE-HASH-MISMATCH", result.stderr)

    def test_noncanonical_timestamp(self):
        result = self.run_builder(
            "--approved-suite-sha256",
            SUITE_SHA256,
            "--approved-at",
            "2026-08-15T02:42:00Z",
            "--write",
            str(self.output),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APPROVAL-TIMESTAMP-NONCANONICAL", result.stderr)

    def test_timestamp_predates_suite(self):
        result = self.run_builder(
            "--approved-suite-sha256",
            SUITE_SHA256,
            "--approved-at",
            "1970-01-01T00:00:00.000000000Z",
            "--write",
            str(self.output),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APPROVAL-TIMESTAMP-PREDATES-SUITE", result.stderr)

    def test_deterministic_identity(self):
        first = build_approval_record(SUITE_SHA256, VALID_TIMESTAMP)
        second = build_approval_record(SUITE_SHA256, VALID_TIMESTAMP)
        self.assertEqual(first, second)
        record_without_id = build_record_without_id(SUITE_SHA256, VALID_TIMESTAMP)
        expected_id = sha256_bytes(canonical_bytes(record_without_id))
        self.assertEqual(first["approval_record_id"], expected_id)

    def test_valid_record_structure(self):
        record = build_approval_record(SUITE_SHA256, VALID_TIMESTAMP)
        self.assertEqual(set(record), APPROVAL_FIELDS)
        self.assertEqual(record["approved_logical_id"], SUITE_LOGICAL_ID)
        self.assertEqual(record["approved_sha256"], SUITE_SHA256)
        self.assertEqual(record["procedure_id"], PROCEDURE_ID)
        self.assertEqual(record["procedure_sha256"], PROCEDURE_SHA256)
        self.assertEqual(record["status"], "APPROVED")
        self.assertNotIn("candidate_evidence_root", record)

    def test_record_validates_against_contract(self):
        record = build_approval_record(SUITE_SHA256, VALID_TIMESTAMP)
        contract = next(
            schema
            for schema in build_contract_schemas()
            if schema["contract_id"] == "phase0.postroot_acceptance_contract_suite.approval.contract"
        )
        result = validate_contract(record, contract)
        self.assertEqual(result.status, "PASS", result.reason_codes)

    def test_builder_writes_canonical_bytes(self):
        result = self.run_builder(
            "--approved-suite-sha256",
            SUITE_SHA256,
            "--approved-at",
            VALID_TIMESTAMP,
            "--write",
            str(self.output),
            "--replace-unapproved-record",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = self.output.read_bytes()
        self.assertFalse(raw.endswith(b"\n"))
        record = json.loads(raw.decode("utf-8"))
        self.assertEqual(record["approval_record_id"], result.stdout.strip())
        validate_inputs(
            approved_suite_sha256=SUITE_SHA256,
            approved_at=VALID_TIMESTAMP,
            suite_path=SUITE_PATH,
        )


if __name__ == "__main__":
    unittest.main()
