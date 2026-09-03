"""Tests for O10 Phase B walk-forward harness scaffolding."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.research.harness import (  # noqa: E402
    PHASE_B_ADMISSION_STATUS_ADMITTED,
    PHASE_B_ADMISSION_STATUS_PENDING,
    build_phase_b_walk_forward_partitions,
    evaluate_phase_b_admission,
    load_phase_b_chain_history_admission_manifest,
    run_o10_phase_b_walk_forward_harness,
)


class OptionsO10PhaseBHarnessTests(unittest.TestCase):
    def test_default_manifest_is_pending(self) -> None:
        manifest = load_phase_b_chain_history_admission_manifest()
        self.assertEqual(manifest.get("status"), PHASE_B_ADMISSION_STATUS_PENDING)
        self.assertEqual(manifest.get("logical_id"), "options.o10_phase_b_chain_history_admission")

    def test_evaluate_phase_b_admission_fail_closed(self) -> None:
        admission = evaluate_phase_b_admission()
        self.assertFalse(admission.get("admitted"))
        self.assertIn("PHASE_B_MANIFEST_STATUS_PENDING", admission.get("blocking_reasons", []))

    def test_phase_b_harness_fail_closed_without_admitted_data(self) -> None:
        report = run_o10_phase_b_walk_forward_harness()
        self.assertFalse(report.get("available"))
        self.assertEqual(report.get("gate_status"), "BLOCKED")
        self.assertEqual(report.get("reason"), "PHASE_B_DATA_NOT_ADMITTED")
        self.assertEqual(report["partition_scaffold"]["fold_count"], 0)
        self.assertEqual(report["partition_scaffold"]["partitions"], [])

    def test_build_phase_b_partitions_requires_sufficient_history(self) -> None:
        short_history = list(range(100))
        result = build_phase_b_walk_forward_partitions(short_history)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "INSUFFICIENT_OBSERVATIONS")
        self.assertEqual(result.get("partitions"), [])

    def test_build_phase_b_partitions_scaffold_on_synthetic_history(self) -> None:
        history = list(range(600))
        result = build_phase_b_walk_forward_partitions(history)
        self.assertTrue(result.get("available"))
        self.assertGreater(result.get("fold_count", 0), 0)
        self.assertEqual(result.get("pit_status"), "PASS")
        first = result["partitions"][0]
        self.assertLess(first["train_end_cutoff"], first["test_start_cutoff"])

    def test_admitted_manifest_without_slots_still_blocks(self) -> None:
        manifest = load_phase_b_chain_history_admission_manifest()
        adversarial = {
            **manifest,
            "status": PHASE_B_ADMISSION_STATUS_ADMITTED,
            "admission_requirements": [
                {
                    **row,
                    "status": PHASE_B_ADMISSION_STATUS_ADMITTED,
                }
                for row in manifest.get("admission_requirements", [])
                if isinstance(row, dict)
            ],
            "dataset_slots": [],
        }
        admission = evaluate_phase_b_admission(adversarial)
        self.assertFalse(admission.get("admitted"))
        report = run_o10_phase_b_walk_forward_harness(manifest=adversarial)
        self.assertFalse(report.get("available"))
        self.assertEqual(report.get("reason"), "PHASE_B_DATA_NOT_ADMITTED")


if __name__ == "__main__":
    unittest.main()
