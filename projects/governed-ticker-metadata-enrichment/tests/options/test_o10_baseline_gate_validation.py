"""Integration tests for O10-S5 baseline gate validation harness."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.research.harness import (  # noqa: E402
    run_o10_baseline_gate_validation,
)


class O10BaselineGateValidationTests(unittest.TestCase):
    def test_unified_gate_validation_passes_on_admitted_fixtures(self) -> None:
        report = run_o10_baseline_gate_validation()
        self.assertEqual(report.get("artifact_type"), "O10_BASELINE_GATE_VALIDATION_REPORT")
        self.assertEqual(report.get("scope"), "fixture")
        self.assertTrue(report.get("research_only"))
        self.assertIn("r_o6_evaluation", report)
        self.assertIn("r_o5_evaluation", report)
        self.assertIn("r_o10_surf_evaluation", report)
        self.assertEqual(report.get("aggregate_status"), "PASS")

        gate_summary = report.get("gate_summary", [])
        self.assertEqual(len(gate_summary), 3)
        for row in gate_summary:
            self.assertEqual(row.get("gate_status"), "PASS")

        admission_ids = {
            ref.get("admission_id") or ref.get("admitted_fixture_id")
            for ref in report.get("fixture_refs", [])
            if isinstance(ref, dict)
        }
        self.assertIn("ADMITTED-OPTIONS-NVDA-R-O6-001", admission_ids)
        self.assertIn("ADMITTED-DISTRIBUTION-NVDA-001", admission_ids)
        self.assertIn("ADMITTED-OPTIONS-NVDA-001", admission_ids)

    def test_matches_golden_gate_summary(self) -> None:
        expected_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "providers"
            / "options"
            / "nvda_o10_baseline_gates_expected.json"
        )
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        report = run_o10_baseline_gate_validation()
        self.assertEqual(report.get("aggregate_status"), expected["aggregate_status"])
        self.assertEqual(report.get("gate_summary"), expected["gate_summary"])


if __name__ == "__main__":
    unittest.main()
