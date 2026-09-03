from __future__ import annotations

import unittest

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)


def member(logical_id: str, path: str, digest: str = "A" * 64) -> dict[str, object]:
    return {
        "byte_length": 10,
        "logical_id": logical_id,
        "media_type": "application/json",
        "member_sha256": digest,
        "repository_relative_path": path,
        "root_id": "ROOT-TEST-001",
    }


def provisional_index(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "candidate_evidence_root": "A" * 64,
        "index_members": rows,
        "logical_id": "phase0.acceptance_index",
        "procedure_id_and_hash": {
            "logical_id": "phase0.ai_review_procedure",
            "sha256": "B" * 64,
        },
        "root_id": "ROOT-TEST-001",
        "schema_version": "1.0.0",
        "suite_id_and_hash": {
            "logical_id": "phase0.postroot_acceptance_contract_suite",
            "sha256": "C" * 64,
        },
    }


class AcceptanceAlgorithmTests(unittest.TestCase):
    def test_record_identity_omits_only_identity_field(self):
        record = {"approval_record_id": "X", "status": "APPROVED"}
        self.assertEqual(
            record_identity(record, "approval_record_id"),
            record_identity(
                {**record, "approval_record_id": "Y"}, "approval_record_id"
            ),
        )

    def test_expected_index_ids_add_exact_postroot_set(self):
        ids = expected_index_logical_ids(["a", "b"])
        self.assertEqual(
            ids,
            (
                "a",
                "b",
                "phase0.ai_review_coverage",
                "phase0.ai_review_runs",
                "phase0.approval_records",
                "phase0.candidate_evidence_root",
                "phase0.postroot_acceptance_contract_suite",
                "phase0.postroot_acceptance_contract_suite.approval",
            ),
        )

    def test_duplicate_candidate_logical_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "INDEX-DUPLICATE-LOGICAL-ID"):
            expected_index_logical_ids(["a", "a"])

    def test_index_hashes_are_order_independent_before_normalization(self):
        rows = [member("b", "synthetic/b.json", "B" * 64), member("a", "synthetic/a.json")]
        self.assertEqual(
            compute_index_hashes(provisional_index(rows)),
            compute_index_hashes(provisional_index(list(reversed(rows)))),
        )

    def test_verify_index_hashes_detects_each_stored_hash_mismatch(self):
        index = provisional_index([member("a", "synthetic/a.json")])
        expected_index, expected_root = compute_index_hashes(index)
        valid = {**index, "index_sha256": expected_index, "root_hash": expected_root}
        self.assertEqual(verify_index_hashes(valid), ())
        self.assertEqual(
            verify_index_hashes({**valid, "index_sha256": "F" * 64}),
            ("INDEX-SHA256-MISMATCH",),
        )
        self.assertEqual(
            verify_index_hashes({**valid, "root_hash": "F" * 64}),
            ("INDEX-ROOT-HASH-MISMATCH",),
        )

    def test_duplicate_index_logical_id_is_rejected(self):
        rows = [member("a", "synthetic/a.json"), member("a", "synthetic/b.json")]
        with self.assertRaisesRegex(ValueError, "INDEX-DUPLICATE-LOGICAL-ID"):
            compute_index_hashes(provisional_index(rows))

    def test_duplicate_index_path_is_rejected(self):
        rows = [member("a", "synthetic/a.json"), member("b", "synthetic/a.json")]
        with self.assertRaisesRegex(ValueError, "INDEX-DUPLICATE-PATH"):
            compute_index_hashes(provisional_index(rows))

    def test_index_self_membership_is_rejected(self):
        rows = [member("phase0.acceptance_index", "synthetic/index.json")]
        with self.assertRaisesRegex(ValueError, "INDEX-SELF-MEMBERSHIP"):
            compute_index_hashes(provisional_index(rows))

    def test_final_result_membership_is_rejected(self):
        rows = [member("phase0.final_acceptance_result", "synthetic/final.json")]
        with self.assertRaisesRegex(ValueError, "INDEX-FINAL-RESULT-MEMBERSHIP"):
            compute_index_hashes(provisional_index(rows))

    def test_missing_member_sha256_is_rejected(self):
        row = member("a", "synthetic/a.json")
        del row["member_sha256"]
        with self.assertRaisesRegex(ValueError, "INDEX-MEMBER-HASH-MISMATCH"):
            compute_index_hashes(provisional_index([row]))

    def test_invalid_or_unsortable_path_is_rejected(self):
        for path in (None, "", "C:/synthetic/a.json", "../synthetic/a.json", "synthetic\\a.json"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "INDEX-NONNORMALIZED-PATH"):
                    compute_index_hashes(provisional_index([member("a", path)]))  # type: ignore[arg-type]

    def test_fail_precedes_blocked(self):
        self.assertEqual(
            derive_final_outcome("PASS", ["FAIL", "BLOCKED"], False), "FAIL"
        )

    def test_invalid_precedes_absence(self):
        self.assertEqual(derive_final_outcome("PASS", ["INVALID"], True), "FAIL")

    def test_absence_blocks_when_nothing_is_invalid(self):
        self.assertEqual(derive_final_outcome("PASS", [], True), "BLOCKED")

    def test_blocked_assertion_blocks(self):
        self.assertEqual(derive_final_outcome("BLOCKED", [], False), "BLOCKED")

    def test_pass_requires_passing_assertions_and_no_other_condition(self):
        self.assertEqual(derive_final_outcome("PASS", [], False), "PASS")


if __name__ == "__main__":
    unittest.main()
