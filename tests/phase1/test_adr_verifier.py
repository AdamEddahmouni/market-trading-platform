"""Phase 1 ADR verifier and decision bundle tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Phase1AdrVerifierTests(unittest.TestCase):
    def test_registry_has_26_rows(self) -> None:
        from market_platform_foundation.adr_verifier import load_registry

        registry = load_registry(ROOT)
        self.assertEqual(len(registry["rows"]), 26)

    def test_verifier_passes(self) -> None:
        from market_platform_foundation.adr_verifier import verify_registry

        result = verify_registry(ROOT)
        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["blocking_count"], 0)
        self.assertEqual(result["accepted_count"], 26)

    def test_acceptance_index_matches_accepted_rows(self) -> None:
        from market_platform_foundation.adr_verifier import (
            build_acceptance_index,
            verify_registry,
        )

        result = verify_registry(ROOT)
        index = build_acceptance_index(ROOT)
        self.assertEqual(index["accepted_adr_count"], result["accepted_count"])

    def test_decision_bundle_builder(self) -> None:
        from tools.phase1.build_decision_bundle import build

        out = ROOT / "tests" / "phase1" / ".out"
        report = build(out)
        self.assertEqual(report["verifier_status"], "PASS")
        self.assertTrue((out / "adr-verifier-result.json").is_file())
        self.assertTrue((out / "adr-acceptance-index.json").is_file())
        self.assertTrue((out / "candidate-evidence-root.json").is_file())

    def test_postreview_gate_outcome_pass(self) -> None:
        import json

        final_path = ROOT / "evidence/phase1/postreview/phase1.final_acceptance_result.json"
        self.assertTrue(final_path.is_file())
        final_doc = json.loads(final_path.read_text(encoding="utf-8"))
        self.assertEqual(final_doc["outcome"], "PASS")
        self.assertEqual(final_doc["review_coverage_status"], "QUALIFIED")

    def test_decision_audits_verify_bundle(self) -> None:
        from tools.phase1.run_decision_audits import verify_bundle

        bundle = ROOT / "evidence/phase1/decision-bundle"
        refs, errors, _ = verify_bundle(bundle)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertTrue(refs)


if __name__ == "__main__":
    unittest.main()
