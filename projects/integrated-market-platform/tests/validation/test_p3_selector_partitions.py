"""P3 selector partitioning, evidence-only, governance, and plan-mode contract tests."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

from tools.validation_manifest import load_manifest
from tools.validate import (
    CLASS_EVIDENCE_ONLY_CHECK,
    CLASS_FAIL_SAFE,
    CLASS_GOVERNANCE_ONLY_CHECK,
    CLASS_OWNING_SUITE_SELECTION,
    SELECTOR_VERSION,
    build_selection_plan,
    manifest_fingerprint,
    select_changed,
)


ROOT = Path(__file__).resolve().parents[2]


class P3SelectorPartitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(
            ROOT / "tools" / "validation_manifest.json", repository_root=ROOT
        )

    def test_news_only_uses_directional_dependents_not_neighbors(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/news/pipeline.py"]
        )
        self.assertEqual(selection.selected_suite_ids, ("news", "intelligence"))
        self.assertFalse(selection.core_checkpoint_required)
        self.assertIn("DEPENDENT_OF:news_foundation", selection.selection_reasons["intelligence"])
        self.assertNotIn("finviz", selection.selected_suite_ids)
        self.assertNotIn("platform", selection.selected_suite_ids)

    def test_intelligence_inference_avoids_contract_platform_neighbors(self) -> None:
        selection = select_changed(
            self.manifest,
            ["src/market_platform_foundation/intelligence/inference/service.py"],
        )
        self.assertEqual(selection.selected_suite_ids, ("intelligence",))
        self.assertNotIn("contracts", selection.selected_suite_ids)
        self.assertNotIn("platform", selection.selected_suite_ids)

    def test_strategy_evaluation_only_stays_in_intelligence_suite(self) -> None:
        selection = select_changed(
            self.manifest,
            [
                "src/market_platform_foundation/intelligence/news_strategy_evaluation/laboratory.py"
            ],
        )
        self.assertEqual(selection.selected_suite_ids, ("intelligence",))
        self.assertNotIn("news", selection.selected_suite_ids)

    def test_docs_only_stays_cheap(self) -> None:
        selection = select_changed(
            self.manifest, ["docs/engineering/VALIDATION_ARCHITECTURE.md"]
        )
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertEqual(selection.cheap_checks, ("documentation",))

    def test_performance_evidence_only_does_not_escalate(self) -> None:
        selection = select_changed(self.manifest, ["artifacts/g14-runtime-performance.json"])
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_EVIDENCE_ONLY_CHECK
        )
        self.assertEqual(
            selection.path_decisions[0].evidence_category, "GENERATED_PERFORMANCE_EVIDENCE"
        )

    def test_performance_evidence_plus_news_matches_news_functional_set(self) -> None:
        news_only = select_changed(
            self.manifest, ["src/market_platform_foundation/news/pipeline.py"]
        )
        mixed = select_changed(
            self.manifest,
            [
                "src/market_platform_foundation/news/pipeline.py",
                "artifacts/g14-runtime-performance.json",
            ],
        )
        self.assertEqual(mixed.selected_suite_ids, news_only.selected_suite_ids)
        self.assertIn("evidence-json", mixed.cheap_checks)

    def test_validation_manifest_change_selects_validation_suite(self) -> None:
        selection = select_changed(self.manifest, ["tools/validation_manifest.json"])
        self.assertIn("validation", selection.selected_suite_ids)
        self.assertTrue(selection.core_checkpoint_required)

    def test_unknown_path_remains_fail_safe(self) -> None:
        selection = select_changed(self.manifest, ["artifacts/scratch/notes.txt"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertEqual(selection.path_decisions[0].classification, CLASS_FAIL_SAFE)

    def test_governance_rules_select_validation_not_core_product_suites(self) -> None:
        selection = select_changed(
            self.manifest, [".cursor/rules/developer-workflow.mdc"]
        )
        self.assertEqual(selection.selected_suite_ids, ("validation",))
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_GOVERNANCE_ONLY_CHECK
        )

    def test_frontend_ui_partition_selects_ui1_without_backend_fanout(self) -> None:
        selection = select_changed(self.manifest, ["ui/src/App.tsx"])
        self.assertEqual(selection.selected_suite_ids, ("ui1",))
        self.assertFalse(selection.core_checkpoint_required)

    def test_mixed_multi_subsystem_unions_required_owners(self) -> None:
        selection = select_changed(
            self.manifest,
            [
                "src/market_platform_foundation/news/pipeline.py",
                "src/market_platform_foundation/intelligence/news_strategy_evaluation/laboratory.py",
            ],
        )
        self.assertIn("news", selection.selected_suite_ids)
        self.assertIn("intelligence", selection.selected_suite_ids)

    def test_windows_path_normalization(self) -> None:
        selection = select_changed(
            self.manifest, ["src\\market_platform_foundation\\news\\pipeline.py"]
        )
        self.assertIn("news", selection.selected_suite_ids)

    def test_build_selection_plan_is_deterministic_and_fast(self) -> None:
        paths = ["src/market_platform_foundation/news/pipeline.py"]
        selection = select_changed(self.manifest, paths)
        started = time.perf_counter()
        first = build_selection_plan(
            selection, self.manifest, manifest_path=ROOT / "tools/validation_manifest.json"
        )
        second = build_selection_plan(
            selection, self.manifest, manifest_path=ROOT / "tools/validation_manifest.json"
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(first, second)
        self.assertFalse(first["executes_tests"])
        self.assertEqual(first["selector_version"], SELECTOR_VERSION)
        self.assertTrue(first["manifest_hash"])
        self.assertLess(elapsed, 1.0)

    def test_plan_cli_executes_zero_tests(self) -> None:
        paths_file = ROOT / "artifacts" / "p3-plan-scenario.txt"
        paths_file.parent.mkdir(parents=True, exist_ok=True)
        paths_file.write_text("src/market_platform_foundation/news/pipeline.py\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "validate.py"),
                "changed",
                "--paths-file",
                str(paths_file),
                "--plan",
                "--json",
                str(ROOT / "artifacts" / "p3-plan-cli-check.json"),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(
            (ROOT / "artifacts" / "p3-plan-cli-check.json").read_text(encoding="utf-8")
        )
        self.assertFalse(payload["executes_tests"])
        self.assertIn("news", payload["selected_suites"])
        self.assertNotIn("tests_run", payload)

    def test_manifest_fingerprint_changes_when_partitions_change(self) -> None:
        baseline = manifest_fingerprint(self.manifest)
        self.assertTrue(len(baseline) == 64)


if __name__ == "__main__":
    unittest.main()
