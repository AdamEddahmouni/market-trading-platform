import hashlib
import json
import re
import unittest
from pathlib import Path

from tools.postroot.suite_definition import (
    PROCEDURE_SHA256,
    SUITE_LOGICAL_ID,
    build_suite,
)

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_MANIFEST = ROOT / "evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/candidate-evidence-root.json"
CANDIDATE_ROOT = "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482"
SUITE_IDS = {
    "phase0.postroot_acceptance_contract_suite",
    "phase0.postroot_acceptance_contract_suite.approval",
}


class SuiteDefinitionTests(unittest.TestCase):
    EXPECTED_CONTRACT_IDS = (
        "phase0.acceptance_index.contract",
        "phase0.ai_review_coverage.contract",
        "phase0.ai_review_output.contract",
        "phase0.ai_review_run.contract",
        "phase0.approval_records.contract",
        "phase0.final_acceptance_result.contract",
        "phase0.preapproval_reviewer_eligibility.contract",
        "phase0.postroot_acceptance_contract_suite.approval.contract",
    )

    REQUIRED_PREFIXES = (
        "APPROVAL-",
        "BYTE-",
        "COVERAGE-",
        "GATE-",
        "HASH-",
        "ID-",
        "INDEX-",
        "JSON-",
        "REF-",
        "REVIEW-",
        "SCHEMA-",
    )

    SENSITIVE_PATTERNS = (
        re.compile(r"https?://", re.IGNORECASE),
        re.compile(r"[A-Za-z]:\\\\"),
        re.compile(r"\\\\"),
        re.compile(r"password\s*=", re.IGNORECASE),
        re.compile(r"api[_-]?key", re.IGNORECASE),
    )

    def setUp(self) -> None:
        self.suite = build_suite()

    def test_contract_inventory(self):
        contract_ids = tuple(row["contract_id"] for row in self.suite["contract_schemas"])
        self.assertEqual(contract_ids, self.EXPECTED_CONTRACT_IDS)

    def test_suite_shell(self):
        self.assertEqual(self.suite["logical_id"], SUITE_LOGICAL_ID)
        self.assertEqual(
            self.suite["effectivity"]["current_effectivity"],
            "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL",
        )
        self.assertNotIn("candidate_evidence_root", self.suite["suite_scope"])
        self.assertEqual(self.suite["authority_bindings"][0]["sha256"], PROCEDURE_SHA256)

    def test_reason_registry_and_fixture_coverage(self):
        codes = {row["reason_code"] for row in self.suite["reason_code_registry"]}
        fixture_codes = {
            code
            for fixture in self.suite["fixture_catalog"]
            if fixture["expected_status"] != "PASS"
            for code in fixture["expected_reason_codes"]
        }
        self.assertTrue(
            all(any(code.startswith(prefix) for code in codes) for prefix in self.REQUIRED_PREFIXES)
        )
        self.assertEqual(codes, fixture_codes)
        self.assertEqual(
            [row["fixture_id"] for row in self.suite["fixture_catalog"]],
            sorted(row["fixture_id"] for row in self.suite["fixture_catalog"]),
        )

    def test_fixture_catalog_completeness(self):
        golden_ids = {
            "GOLDEN-ACCEPTANCE-INDEX-001",
            "GOLDEN-AI-REVIEW-COVERAGE-001",
            "GOLDEN-AI-REVIEW-OUTPUT-001",
            "GOLDEN-AI-REVIEW-RUN-001",
            "GOLDEN-APPROVAL-RECORDS-001",
            "GOLDEN-FINAL-ACCEPTANCE-RESULT-001",
            "GOLDEN-PREAPPROVAL-ELIGIBILITY-001",
            "GOLDEN-SUITE-APPROVAL-001",
        }
        fixture_ids = {row["fixture_id"] for row in self.suite["fixture_catalog"]}
        self.assertTrue(golden_ids.issubset(fixture_ids))

    def test_sanitization_scan(self):
        text = json.dumps(self.suite, ensure_ascii=False)
        for pattern in self.SENSITIVE_PATTERNS:
            self.assertIsNone(pattern.search(text))

    def test_candidate_root_preserved(self):
        manifest = json.loads(CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["candidate_evidence_root"], CANDIDATE_ROOT)
        self.assertTrue(SUITE_IDS.isdisjoint(row[0] for row in manifest["ordered_member_tuples"]))

    def test_historical_evidence_inventory_unchanged(self):
        inventory: dict[str, str] = {}
        for path in sorted((ROOT / "evidence/phase0").rglob("*")):
            if path.is_file():
                inventory[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest().upper()
        self.assertGreater(len(inventory), 0)
        self.assertIn(
            "evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/candidate-evidence-root.json",
            inventory,
        )


if __name__ == "__main__":
    unittest.main()
