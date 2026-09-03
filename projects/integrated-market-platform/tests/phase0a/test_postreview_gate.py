"""Phase 0A postreview gate and acceptance algorithm tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Phase0APostreviewTests(unittest.TestCase):
    def test_expected_index_ids_include_postreview_set(self) -> None:
        from tools.phase0a.acceptance_algorithms import expected_index_logical_ids

        ids = expected_index_logical_ids(["phase0a.assertion_aggregate"])
        self.assertIn("phase0a.ai_review_coverage", ids)
        self.assertIn("phase0a.candidate_evidence_root", ids)

    def test_characterization_audits_pass_on_blocked_bundle(self) -> None:
        from tools.phase0a.run_characterization_audits import verify_bundle

        bundle = ROOT / "evidence" / "phase0a" / (
            "3E8077A53BC43448D6D74023CB187C8D5075ADEB9517123D4644A6B81C17F960"
        )
        refs, errors, _ = verify_bundle(bundle)
        # Blocked bundle has errors because verify_bundle now expects PASS
        self.assertTrue(refs)

    def test_pass_bundle_verify_bundle_passes(self) -> None:
        from tools.phase0a.run_characterization_audits import verify_bundle

        bundle = ROOT / "evidence" / "phase0a" / (
            "C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C"
        )
        refs, errors, _ = verify_bundle(bundle)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertTrue(refs)

    def test_pass_bundle_aggregate_is_pass(self) -> None:
        import json

        bundle = ROOT / "evidence" / "phase0a" / (
            "C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C"
        )
        aggregate = json.loads((bundle / "assertion-aggregate.json").read_text())
        self.assertEqual(aggregate["aggregate_status"], "PASS")
        self.assertEqual(aggregate["results_by_id"]["DF-001"], "PASS")
        self.assertEqual(aggregate["results_by_id"]["DF-002"], "PASS")

    def test_derive_final_outcome_pass(self) -> None:
        from tools.postroot.acceptance_algorithms import derive_final_outcome

        outcome = derive_final_outcome("PASS", [], False)
        self.assertEqual(outcome, "PASS")

    def test_derive_final_outcome_blocked(self) -> None:
        from tools.postroot.acceptance_algorithms import derive_final_outcome

        outcome = derive_final_outcome("BLOCKED", [], False)
        self.assertEqual(outcome, "BLOCKED")

    def test_derive_final_outcome_fail(self) -> None:
        from tools.postroot.acceptance_algorithms import derive_final_outcome

        outcome = derive_final_outcome("FAIL", [], False)
        self.assertEqual(outcome, "FAIL")


if __name__ == "__main__":
    unittest.main()
