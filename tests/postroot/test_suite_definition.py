from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.postroot.contract_core import strict_loads, validate_contract

from tools.postroot.suite_definition import (
    PLAN_SHA256,
    PROCEDURE_SHA256,
    SPECIFICATION_SHA256,
    build_contract_schemas,
    build_suite,
)


EXPECTED_CONTRACT_IDS = (
    "phase0.acceptance_index.contract",
    "phase0.ai_review_coverage.contract",
    "phase0.ai_review_output.contract",
    "phase0.ai_review_run.contract",
    "phase0.approval_records.contract",
    "phase0.final_acceptance_result.contract",
    "phase0.postroot_acceptance_contract_suite.approval.contract",
    "phase0.preapproval_reviewer_eligibility.contract",
)

EXPECTED_SUITE_FIELDS = {
    "acknowledgements",
    "artifact_type",
    "authority_bindings",
    "canonical_encoding_profile",
    "closed_contract_profile",
    "contract_schemas",
    "documented_on",
    "effectivity",
    "fixture_catalog",
    "logical_id",
    "non_authorizations",
    "reason_code_registry",
    "schema_version",
    "suite_scope",
    "supersession",
    "validation_order",
}

EXPECTED_REVIEW_OUTPUT_FIELDS = {
    "candidate_evidence_root",
    "coverage_assertion_ids",
    "coverage_logical_ids",
    "findings",
    "limitations",
    "recommended_candidate_outcome",
    "reproduction_results",
    "review_class",
    "summary",
}

EXPECTED_REVIEW_RUN_FIELDS = {
    "candidate_evidence_root",
    "canonical_configuration_hash",
    "completed_at",
    "coverage_assertion_ids",
    "coverage_logical_ids",
    "disqualification_reason_codes",
    "eligibility_result",
    "findings",
    "input_artifact_hashes",
    "model_service_and_declared_version",
    "plan_hash",
    "qualification_state",
    "recommended_candidate_outcome",
    "registry_hash",
    "reproduction_results",
    "review_class",
    "review_output_hash",
    "review_procedure_id_and_hash",
    "review_run_id",
    "run_id",
    "runtime_and_tool_versions",
    "specification_hash",
    "started_at",
    "terminal_state",
}

EXPECTED_COVERAGE_FIELDS = {
    "candidate_evidence_root",
    "coverage_assertion_ids_union",
    "coverage_logical_ids_union",
    "disqualification_reason_codes",
    "duplicate_identity_results",
    "expected_assertion_ids",
    "expected_logical_ids",
    "extra_assertion_ids",
    "extra_logical_ids",
    "invalid_review_run_ids",
    "invalid_selected_run_reason_codes",
    "isolation_check_results",
    "missing_assertion_ids",
    "missing_logical_ids",
    "qualification_status",
    "qualifying_review_run_ids",
    "registry_hash",
    "review_class_assignments",
    "review_procedure_id_and_hash",
    "selected_review_run_ids",
}

EXPECTED_PREELIGIBILITY_CHECK_IDS = [
    "PREELIG-ROLE-RESOLUTION-001",
    "PREELIG-PROCEDURE-DESIGNATION-001",
    "PREELIG-PROCEDURE-APPROVAL-001",
    "PREELIG-REVIEW-CONTROLS-001",
    "PREELIG-NONCIRCULARITY-001",
    "PREELIG-NO-FALSE-EVIDENCE-001",
]

EXPECTED_REASON_CODES = {
    "APPROVAL-CAPACITY-DUPLICATE",
    "APPROVAL-CAPACITY-EXTRA",
    "APPROVAL-CAPACITY-MISSING",
    "APPROVAL-HASH-BINDING-MISMATCH",
    "APPROVAL-IDENTITY-INVALID",
    "APPROVAL-NOT-EFFECTIVE",
    "APPROVAL-PRINCIPAL-MISMATCH",
    "APPROVAL-WAIVER-ATTEMPT",
    "BYTE-CANONICAL-MISMATCH",
    "BYTE-TRAILING-DATA",
    "BYTE-UTF8-BOM",
    "BYTE-UTF8-INVALID",
    "COVERAGE-CLASS-INVALID",
    "COVERAGE-DUPLICATE-IDENTITY",
    "COVERAGE-EXTRA-ID",
    "COVERAGE-ISOLATION-INVALID",
    "COVERAGE-MISSING-ID",
    "COVERAGE-SELECTION-CARDINALITY",
    "GATE-FINAL-RESULT-ID-MISMATCH",
    "GATE-OUTCOME-MISMATCH",
    "GATE-PRECEDENCE-MISMATCH",
    "HASH-CANDIDATE-ROOT-MISMATCH",
    "HASH-CONTENT-MISMATCH",
    "HASH-PROCEDURE-MISMATCH",
    "HASH-REGISTRY-MISMATCH",
    "HASH-REVIEW-OUTPUT-MISMATCH",
    "HASH-RUN-MISMATCH",
    "HASH-SUITE-MISMATCH",
    "ID-DUPLICATE-SEMANTIC-IDENTITY",
    "ID-LOGICAL-ID-INVALID",
    "ID-RECORD-ID-MISMATCH",
    "INDEX-ABSOLUTE-PATH",
    "INDEX-DUPLICATE-LOGICAL-ID",
    "INDEX-DUPLICATE-PATH",
    "INDEX-EXTRA-MEMBER",
    "INDEX-FINAL-RESULT-MEMBERSHIP",
    "INDEX-MEMBER-BYTE-LENGTH-MISMATCH",
    "INDEX-MEMBER-HASH-MISMATCH",
    "INDEX-MISSING-MEMBER",
    "INDEX-NONNORMALIZED-PATH",
    "INDEX-ROOT-HASH-MISMATCH",
    "INDEX-ROOT-ID-MISMATCH",
    "INDEX-SELF-MEMBERSHIP",
    "INDEX-SHA256-MISMATCH",
    "INDEX-SYMLINK-OR-REPARSE-ESCAPE",
    "JSON-DUPLICATE-KEY",
    "JSON-PARSE-INVALID",
    "REF-CONTRADICTORY-BINDING",
    "REF-UNRESOLVED",
    "REVIEW-AUTHORING-CONTEXT",
    "REVIEW-CLASS-MISSING",
    "REVIEW-DISQUALIFICATION-CODE-MISMATCH",
    "REVIEW-GOVERNED-SUBJECT-MUTATION",
    "REVIEW-OUTCOME-MISMATCH",
    "REVIEW-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS",
    "SCHEMA-ARRAY-DUPLICATE",
    "SCHEMA-ARRAY-ORDER",
    "SCHEMA-ENUM-INVALID",
    "SCHEMA-FORMAT-INVALID",
    "SCHEMA-MISSING-REQUIRED-FIELD",
    "SCHEMA-TYPE-INVALID",
    "SCHEMA-UNDECLARED-FIELD",
}

EXPECTED_GOLDEN_FIXTURES = {
    "GOLDEN-ACCEPTANCE-INDEX-001": "phase0.acceptance_index.contract",
    "GOLDEN-AI-REVIEW-COVERAGE-001": "phase0.ai_review_coverage.contract",
    "GOLDEN-AI-REVIEW-OUTPUT-001": "phase0.ai_review_output.contract",
    "GOLDEN-AI-REVIEW-RUN-001": "phase0.ai_review_run.contract",
    "GOLDEN-APPROVAL-RECORDS-001": "phase0.approval_records.contract",
    "GOLDEN-FINAL-ACCEPTANCE-RESULT-001": "phase0.final_acceptance_result.contract",
    "GOLDEN-PREAPPROVAL-ELIGIBILITY-001": "phase0.preapproval_reviewer_eligibility.contract",
    "GOLDEN-SUITE-APPROVAL-001": "phase0.postroot_acceptance_contract_suite.approval.contract",
}


class SuiteDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.contracts = build_contract_schemas()
        self.by_id = {row["contract_id"]: row for row in self.contracts}
        self.suite = build_suite()

    def test_contract_inventory_is_exact_and_sorted(self):
        self.assertEqual(
            tuple(row["contract_id"] for row in self.contracts),
            EXPECTED_CONTRACT_IDS,
        )

    def test_every_contract_is_closed_and_has_no_optional_fields(self):
        for row in self.contracts:
            with self.subTest(contract_id=row["contract_id"]):
                self.assertEqual(
                    set(row),
                    {
                        "additional_properties",
                        "contract_id",
                        "field_rules",
                        "required_fields",
                        "schema_version",
                        "validation_rules",
                    },
                )
                self.assertEqual(row["additional_properties"], "REJECT")
                self.assertEqual(row["required_fields"], sorted(row["field_rules"]))
                self.assertEqual(row["schema_version"], "1.0.0")

    def test_procedure_contract_field_sets_are_exact(self):
        self.assertEqual(
            set(self.by_id["phase0.ai_review_output.contract"]["required_fields"]),
            EXPECTED_REVIEW_OUTPUT_FIELDS,
        )
        self.assertEqual(
            set(self.by_id["phase0.ai_review_run.contract"]["required_fields"]),
            EXPECTED_REVIEW_RUN_FIELDS,
        )
        self.assertEqual(
            set(self.by_id["phase0.ai_review_coverage.contract"]["required_fields"]),
            EXPECTED_COVERAGE_FIELDS,
        )

        repository_root = Path(__file__).resolve().parents[2]
        procedure = strict_loads(
            (
                repository_root
                / "docs"
                / "superpowers"
                / "governance"
                / "2026-08-14-ai-review-process-001.json"
            ).read_bytes()
        )
        self.assertEqual(
            set(procedure["review_run_record_contract"]["required_fields"]),
            EXPECTED_REVIEW_RUN_FIELDS,
        )
        self.assertEqual(
            set(
                procedure["review_run_record_contract"]["review_output_contract"][
                    "required_fields"
                ]
            ),
            EXPECTED_REVIEW_OUTPUT_FIELDS,
        )
        self.assertEqual(
            set(procedure["coverage_qualification_contract"]["required_fields"]),
            EXPECTED_COVERAGE_FIELDS,
        )

    def test_preeligibility_contract_binds_exact_check_order(self):
        rules = self.by_id[
            "phase0.preapproval_reviewer_eligibility.contract"
        ]["validation_rules"]
        self.assertIn(
            {"check_id_order_required": EXPECTED_PREELIGIBILITY_CHECK_IDS}, rules
        )
        self.assertIn({"required_check_count": 6}, rules)

    def test_preeligibility_contract_accepts_the_exact_governed_record(self):
        repository_root = Path(__file__).resolve().parents[2]
        governed_path = repository_root / "docs" / "superpowers" / "governance" / (
            "2026-08-14-gov-002-preapproval-reviewer-eligibility.json"
        )
        governed_record = strict_loads(governed_path.read_bytes())
        self.assertEqual(
            set(
                self.by_id[
                    "phase0.preapproval_reviewer_eligibility.contract"
                ]["required_fields"]
            ),
            set(governed_record),
        )
        result = validate_contract(
            governed_record,
            self.by_id["phase0.preapproval_reviewer_eligibility.contract"],
        )
        self.assertEqual(result.status, "PASS", result.reason_codes)

    def test_suite_shell_is_exact_and_pending(self):
        self.assertEqual(set(self.suite), EXPECTED_SUITE_FIELDS)
        self.assertEqual(
            self.suite["artifact_type"],
            "PHASE0_POSTROOT_ACCEPTANCE_CONTRACT_SUITE",
        )
        self.assertEqual(
            self.suite["logical_id"],
            "phase0.postroot_acceptance_contract_suite",
        )
        self.assertEqual(
            self.suite["effectivity"]["current_effectivity"],
            "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL",
        )
        self.assertNotIn("candidate_evidence_root", self.suite["suite_scope"])

    def test_suite_authority_hashes_are_exact(self):
        bindings = self.suite["authority_bindings"]
        self.assertEqual(bindings[0]["sha256"], PROCEDURE_SHA256)
        self.assertEqual(PROCEDURE_SHA256, "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8")
        self.assertEqual(PLAN_SHA256, "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904")
        self.assertEqual(SPECIFICATION_SHA256, "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35")

    def test_contract_catalog_is_embedded(self):
        self.assertEqual(self.suite["contract_schemas"], self.contracts)

    def test_reason_registry_is_exact_unique_and_has_all_prefix_families(self):
        registry = self.suite["reason_code_registry"]
        codes = [row["reason_code"] for row in registry]
        self.assertEqual(set(codes), EXPECTED_REASON_CODES)
        self.assertEqual(codes, sorted(codes))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(row["description"].endswith(".") for row in registry))
        self.assertTrue(all(row["gate_effect"] in {"BLOCKED", "FAIL", "REJECTED"} for row in registry))
        required_prefixes = (
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
        self.assertTrue(
            all(any(code.startswith(prefix) for code in codes) for prefix in required_prefixes)
        )

    def test_fixture_shape_golden_coverage_and_adversarial_reason_coverage(self):
        fixtures = self.suite["fixture_catalog"]
        fixture_ids = [row["fixture_id"] for row in fixtures]
        self.assertGreater(len(fixtures), 40)
        self.assertEqual(fixture_ids, sorted(fixture_ids))
        self.assertEqual(len(fixture_ids), len(set(fixture_ids)))
        exact_fields = {
            "expected_derived_values",
            "expected_reason_codes",
            "expected_status",
            "fixture_id",
            "input_artifacts",
            "invariant_under_test",
            "target_contract_id",
            "validation_phase",
        }
        for row in fixtures:
            with self.subTest(fixture_id=row["fixture_id"]):
                self.assertEqual(set(row), exact_fields)
                self.assertEqual(row["expected_reason_codes"], sorted(set(row["expected_reason_codes"])))
                self.assertTrue(all(isinstance(raw, str) for raw in row["input_artifacts"]))

        actual_golden = {
            row["fixture_id"]: row["target_contract_id"]
            for row in fixtures
            if row["fixture_id"].startswith("GOLDEN-")
        }
        self.assertEqual(actual_golden, EXPECTED_GOLDEN_FIXTURES)
        for row in fixtures:
            if not row["fixture_id"].startswith("GOLDEN-"):
                continue
            with self.subTest(fixture_id=row["fixture_id"], check="golden-schema"):
                self.assertEqual(len(row["input_artifacts"]), 1)
                subject = strict_loads(row["input_artifacts"][0].encode("utf-8"))
                result = validate_contract(subject, self.by_id[row["target_contract_id"]])
                self.assertEqual(result.status, "PASS", result.reason_codes)
        covered_codes = {
            code
            for row in fixtures
            if row["expected_status"] != "PASS"
            for code in row["expected_reason_codes"]
        }
        self.assertEqual(covered_codes, EXPECTED_REASON_CODES)

    def test_fixture_content_is_synthetic_and_contains_no_sensitive_locator(self):
        prohibited = re.compile(
            r"(?i)(?:https?://|[A-Z]:[/\\]|\\\\|credential|account.identifier|"
            r"market.data|trade.data|donor.data|conversation.content)"
        )
        for row in self.suite["fixture_catalog"]:
            serialized = " ".join(row["input_artifacts"])
            with self.subTest(fixture_id=row["fixture_id"]):
                self.assertIsNone(prohibited.search(serialized))


if __name__ == "__main__":
    unittest.main()
