"""Track E Wave 1 experiment harness infrastructure tests."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.research.wave1.config import load_frozen_registry
from market_platform_foundation.research.wave1.errors import Wave1ExportGateError
from market_platform_foundation.research.wave1.export_gate import require_pit_pass_for_oos
from market_platform_foundation.research.wave1.runner import run_wave1_from_export_stub, run_wave1_registry

ROOT = Path(__file__).resolve().parents[2]
EXPORT_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "wave1_non_empirical_export.json"
EXAMPLES_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "wave1_examples.json"


class Wave1HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.export = load_json_strict(EXPORT_FIXTURE)
        assert isinstance(self.export, dict)
        self.examples = load_json_strict(EXAMPLES_FIXTURE)
        assert isinstance(self.examples, list)

    def test_frozen_registry_loads_eight_families(self) -> None:
        registry = load_frozen_registry()
        self.assertEqual(len(registry.families), 8)
        ids = {f.family_id for f in registry.families}
        self.assertEqual(
            ids,
            {
                "W1-F01",
                "W1-F02",
                "W1-F03",
                "W1-F04",
                "W1-F05",
                "W1-F06",
                "W1-F07",
                "W1-F08",
            },
        )
        for family in registry.families:
            self.assertTrue(family.hypothesis_ref.startswith("TRACK_E/W1/prereg/"))

    def test_reproducible_run_fingerprint(self) -> None:
        first = run_wave1_from_export_stub(self.export, allow_oos=False)
        second = run_wave1_from_export_stub(self.export, allow_oos=False)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.run_fingerprint, second.run_fingerprint)

    def test_in_sample_runs_all_families_without_oos(self) -> None:
        report = run_wave1_registry(
            [dict(row) for row in self.examples],
            export_manifest=self.export,
            allow_oos=False,
        )
        self.assertEqual(report.oos_mode, "IN_SAMPLE_ONLY")
        self.assertEqual(len(report.family_results), 8)
        for result in report.family_results:
            self.assertEqual(result.oos_mode, "IN_SAMPLE_ONLY")
            self.assertIn("OOS_BLOCKED_PENDING_PIT_PASS", result.limitations)

    def test_oos_blocked_on_non_empirical_export(self) -> None:
        with self.assertRaises(Wave1ExportGateError) as ctx:
            require_pit_pass_for_oos(self.export, validation_dataset_manifest=self.export["validation_dataset_manifest"])
        self.assertEqual(ctx.exception.code, "W1_OOS_BLOCKED_EXPORT_NOT_PIT_PASS")

    def test_allow_oos_flag_still_in_sample_on_fixture(self) -> None:
        report = run_wave1_from_export_stub(copy.deepcopy(self.export), allow_oos=True)
        self.assertEqual(report.oos_mode, "IN_SAMPLE_ONLY")
        self.assertEqual(report.evidence_class, "NON_EMPIRICAL_FIXTURE")

    def test_pit_pass_export_without_empirical_class_can_enable_oos_mode(self) -> None:
        export = copy.deepcopy(self.export)
        export["metadata"] = {
            "evidence_class": "OUT_OF_SAMPLE_REPLAY",
            "pit_status": "PIT-PASS",
        }
        report = run_wave1_from_export_stub(export, allow_oos=True)
        self.assertEqual(report.oos_mode, "OOS_PIT_PASS")
        self.assertTrue(all(r.oos_mode == "OOS_PIT_PASS" for r in report.family_results))

    def test_external_research_data_stays_in_sample_even_if_pit_pass(self) -> None:
        export = copy.deepcopy(self.export)
        export["metadata"] = {
            "evidence_class": "EXTERNAL_RESEARCH_DATA",
            "pit_status": "PIT-PASS",
        }
        with self.assertRaises(Wave1ExportGateError) as ctx:
            require_pit_pass_for_oos(
                export,
                validation_dataset_manifest=export["validation_dataset_manifest"],
            )
        self.assertEqual(ctx.exception.code, "W1_OOS_BLOCKED_EXTERNAL_RESEARCH_DATA")
        report = run_wave1_from_export_stub(export, allow_oos=True)
        self.assertEqual(report.oos_mode, "IN_SAMPLE_ONLY")
        self.assertEqual(report.evidence_class, "EXTERNAL_RESEARCH_DATA")
        self.assertTrue(all(r.oos_mode == "IN_SAMPLE_ONLY" for r in report.family_results))

    def test_mixed_external_and_fixture_class_blocks_oos(self) -> None:
        export = copy.deepcopy(self.export)
        export["metadata"] = {
            "evidence_class": "OUT_OF_SAMPLE_REPLAY",
            "evidence_classes": ["EXTERNAL_RESEARCH_DATA"],
            "pit_status": "PIT-PASS",
        }
        with self.assertRaises(Wave1ExportGateError) as ctx:
            require_pit_pass_for_oos(
                export,
                validation_dataset_manifest=export["validation_dataset_manifest"],
            )
        self.assertEqual(ctx.exception.code, "W1_OOS_BLOCKED_MIXED_EXTERNAL_RESEARCH_DATA")


if __name__ == "__main__":
    unittest.main()
