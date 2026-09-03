import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.errors import IntegrityError
from market_platform_foundation.verifier import (
    aggregate_status,
    candidate_root,
    candidate_tuple_array,
    verify_member,
    verify_result_set,
)


class VerifierTests(unittest.TestCase):
    def test_fail_precedes_blocked(self):
        self.assertEqual(aggregate_status(["PASS", "BLOCKED", "FAIL"]), "FAIL")

    def test_blocked_precedes_pass(self):
        self.assertEqual(aggregate_status(["PASS", "BLOCKED"]), "BLOCKED")

    def test_candidate_root_is_order_independent(self):
        rows = [
            {
                "logical_id": "b",
                "member_sha256": "B",
                "byte_length": 2,
                "media_type": "application/json",
            },
            {
                "logical_id": "a",
                "member_sha256": "A",
                "byte_length": 1,
                "media_type": "application/json",
            },
        ]
        self.assertEqual(candidate_root(rows), candidate_root(list(reversed(rows))))

    def test_changed_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            path.write_bytes(b"{}\n")
            expected = sha256_bytes(path.read_bytes())
            path.write_bytes(b'{"changed":true}\n')
            with self.assertRaises(IntegrityError):
                verify_member(path, expected)

    def test_missing_result_is_blocked(self):
        report = verify_result_set("RUN", [])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("MISSING_MANDATORY_RESULT", report["reason_codes"])

    def test_mixed_run_is_blocked(self):
        rows = [
            {"assertion_id": assertion_id, "run_id": "RUN-A"}
            for assertion_id in (
                "GOV-001",
                "GOV-002",
                "GOV-003",
                "GOV-004",
                "SAFE-001",
                "SAFE-002",
                "SAFE-003-STATIC",
                "SAFE-P0-001",
                "SEC-001",
            )
        ]
        rows[-1]["run_id"] = "RUN-B"
        report = verify_result_set("RUN-A", rows)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("MIXED_RUN_ID", report["reason_codes"])

    def test_postroot_members_are_excluded(self):
        rows = [
            {
                "logical_id": "phase0.approval_records",
                "member_sha256": "A",
                "byte_length": 1,
                "media_type": "application/json",
            },
            {
                "logical_id": "phase0.registry_snapshot",
                "member_sha256": "B",
                "byte_length": 2,
                "media_type": "application/json",
            },
        ]
        self.assertEqual(candidate_tuple_array(rows)[0][0], "phase0.registry_snapshot")
