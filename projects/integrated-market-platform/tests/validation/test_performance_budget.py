"""P7 performance budget and telemetry contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from tools.performance_budget import (
    CLASSIFICATION_INCOMPATIBLE,
    CLASSIFICATION_INSUFFICIENT_DATA,
    CLASSIFICATION_NORMAL,
    CLASSIFICATION_NO_BASELINE,
    CLASSIFICATION_REGRESSION,
    CLASSIFICATION_SEVERE_REGRESSION,
    CLASSIFICATION_WARNING,
    classify_performance,
    environments_compatible,
    load_performance_budget,
    summarize_variance,
    validate_budget_schema,
    workload_identity_matches,
)
from tools.performance_telemetry import (
    enrich_validation_receipt,
    environment_fingerprint,
    format_regression_explanation,
    performance_status_for_env,
    suite_timing_summary,
)


class PerformanceBudgetSchemaTests(unittest.TestCase):
    def test_load_budget_manifest(self) -> None:
        root = Path(__file__).resolve().parents[2]
        budget = load_performance_budget(root / "manifests" / "performance_budget.json")
        self.assertEqual(budget.budget_version, "p7-bl-0910-2")
        self.assertEqual(budget.gating_policy, "OBSERVE_ONLY")
        self.assertIn("fast", budget.workloads)
        self.assertIn("full", budget.workloads)

    def test_validate_budget_schema_rejects_missing_fields(self) -> None:
        errors = validate_budget_schema({"schema_version": "1.0"})
        self.assertTrue(any("budget_version" in error for error in errors))


class PerformanceClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.budget = load_performance_budget(root / "manifests" / "performance_budget.json")
        self.environment = {
            "os_family": "windows",
            "python_version": "3.11.15",
            "logical_cpu_count": 8,
            "ci": False,
            "environment_class": "local_windows_warm_venv",
            "baseline_logical_cpu_count": 8,
        }

    def test_normal_classification_within_budget(self) -> None:
        baseline = self.budget.workloads["fast"].baseline_median_seconds
        receipt = {
            "mode": "fast",
            "wall_seconds": baseline * 1.02,
            "tests_run": 21,
            "workers": 1,
            "effective_workers": 1,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_NORMAL)
        self.assertTrue(result["trustworthy_for_action"])

    def test_warning_classification(self) -> None:
        baseline = self.budget.workloads["fast"].baseline_median_seconds
        receipt = {
            "mode": "fast",
            "wall_seconds": baseline * 1.20,
            "tests_run": 21,
            "workers": 1,
            "effective_workers": 1,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_WARNING)

    def test_regression_classification(self) -> None:
        baseline = self.budget.workloads["fast"].baseline_median_seconds
        receipt = {
            "mode": "fast",
            "wall_seconds": baseline * 1.35,
            "tests_run": 21,
            "workers": 1,
            "effective_workers": 1,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_REGRESSION)

    def test_severe_regression_classification(self) -> None:
        baseline = self.budget.workloads["fast"].baseline_median_seconds
        receipt = {
            "mode": "fast",
            "wall_seconds": baseline * 1.55,
            "tests_run": 21,
            "workers": 1,
            "effective_workers": 1,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_SEVERE_REGRESSION)

    def test_incompatible_worker_count(self) -> None:
        receipt = {
            "mode": "fast",
            "wall_seconds": 3.5,
            "tests_run": 21,
            "workers": 2,
            "effective_workers": 2,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_INCOMPATIBLE)

    def test_no_baseline_for_unknown_mode(self) -> None:
        receipt = {"mode": "live", "wall_seconds": 1.0, "tests_run": 1}
        result = classify_performance(
            receipt, budget=self.budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_NO_BASELINE)

    def test_changed_workload_identity_mismatch(self) -> None:
        workload = self.budget.workloads["changed_product_paths"]
        receipt = {"tests_run": 100, "skips": 0}
        ok, reasons = workload_identity_matches(workload, receipt)
        self.assertFalse(ok)
        self.assertTrue(reasons)
        result = classify_performance(
            {
                "mode": "changed",
                "wall_seconds": 173.0,
                "tests_run": 100,
                "skips": 0,
                "workers": 2,
                "effective_workers": 2,
                "scheduler_version": "p2-bl-0901-1",
            },
            budget=self.budget,
            environment=self.environment,
        )
        self.assertEqual(result["classification"], CLASSIFICATION_INSUFFICIENT_DATA)

    def test_regression_masking_risk_when_primary_baseline_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            budget_path = Path(temporary) / "performance_budget.json"
            budget_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "telemetry_schema_version": "1.0",
                        "budget_version": "test-bl-1",
                        "parent_scheduler_version": "p2-bl-0901-1",
                        "parent_selector_version": "p3-bl-0801-1",
                        "gating_policy": "OBSERVE_ONLY",
                        "maturity_status": "PROVISIONAL",
                        "threshold_policy": self.budget.raw["threshold_policy"],
                        "environment_compatibility": self.budget.compatibility,
                        "workloads": {
                            "domain_macro": {
                                "validation_mode": "domain",
                                "domain_target": "macro",
                                "reference_workers": 2,
                                "baseline_wall_seconds": 6.901,
                                "baseline_median_seconds": 6.901,
                                "baseline_sample_count": 3,
                                "p2_inherited_seconds": 3.273,
                                "inherited_baseline_status": "MEASURED_COMPATIBLE",
                                "reference_test_count": 304,
                                "environment_class": "local_windows_warm_venv",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            budget = load_performance_budget(budget_path)
        receipt = {
            "mode": "domain",
            "domain_target": "macro",
            "wall_seconds": 6.95,
            "tests_run": 304,
            "workers": 2,
            "effective_workers": 2,
            "scheduler_version": "p2-bl-0901-1",
        }
        result = classify_performance(
            receipt, budget=budget, environment=self.environment
        )
        self.assertEqual(result["classification"], CLASSIFICATION_NORMAL)
        self.assertTrue(result.get("regression_masking_risk"))

    def test_environments_compatible_rejects_ci_vs_local(self) -> None:
        compatible, reasons = environments_compatible(
            {"ci": True, "os_family": "linux"},
            "local_windows_warm_venv",
            self.budget.compatibility,
        )
        self.assertFalse(compatible)
        self.assertTrue(reasons)


class PerformanceTelemetryTests(unittest.TestCase):
    def test_enrich_validation_receipt_adds_stable_fields(self) -> None:
        root = Path(__file__).resolve().parents[2]
        budget = load_performance_budget(root / "manifests" / "performance_budget.json")
        receipt = {
            "mode": "fast",
            "started_at": "2026-09-10T00:00:00+00:00",
            "wall_seconds": budget.workloads["fast"].baseline_median_seconds * 1.02,
            "tests_run": 21,
            "skips": 0,
            "failures": 0,
            "errors": 0,
            "workers": 1,
            "effective_workers": 1,
            "scheduler_version": "p2-bl-0901-1",
            "worker_results": [
                {
                    "suite_id": "phase0",
                    "wall_seconds": 1.2,
                    "discovery_seconds": 0.1,
                    "tests_run": 10,
                    "status": "passed",
                }
            ],
            "execution_schedule": {
                "waves": [{"wave_id": 0, "policy": "PARALLEL_SAFE", "concurrency": 1, "suite_ids": ["phase0"]}]
            },
        }
        enriched = enrich_validation_receipt(receipt, repository_root=root)
        perf = enriched["performance_telemetry"]
        self.assertEqual(perf["telemetry_schema_version"], "1.0")
        self.assertIn("budget", perf)
        self.assertIn("environment", perf)
        self.assertIn("suite_timing", perf)
        self.assertIn(
            perf["budget"]["classification"],
            {
                CLASSIFICATION_NORMAL,
                CLASSIFICATION_WARNING,
                CLASSIFICATION_REGRESSION,
                CLASSIFICATION_SEVERE_REGRESSION,
                CLASSIFICATION_INCOMPATIBLE,
            },
        )

    def test_suite_timing_summary_orders_slowest_first(self) -> None:
        summary = suite_timing_summary(
            {
                "worker_results": [
                    {"suite_id": "a", "wall_seconds": 1.0, "tests_run": 1, "status": "passed"},
                    {"suite_id": "b", "wall_seconds": 3.0, "tests_run": 1, "status": "passed"},
                ]
            }
        )
        self.assertEqual(summary["slowest_suites"][0]["suite_id"], "b")

    def test_performance_status_for_env_is_fast(self) -> None:
        root = Path(__file__).resolve().parents[2]
        status = performance_status_for_env(root)
        self.assertTrue(status["available"])
        self.assertEqual(status["gating_policy"], "OBSERVE_ONLY")

    def test_regression_explanation_includes_threshold(self) -> None:
        text = format_regression_explanation(
            {"tests_run": 21, "failures": 0},
            {
                "classification": CLASSIFICATION_REGRESSION,
                "observed_wall_seconds": 5.0,
                "baseline_median_seconds": 3.5,
                "absolute_delta_seconds": 1.5,
                "percentage_delta": 42.8,
                "threshold_crossed": "regression_ratio",
            },
            {"slowest_suites": [{"suite_id": "phase0", "wall_seconds": 2.0}]},
        )
        self.assertIn("threshold_crossed=regression_ratio", text)
        self.assertIn("slowest_suites=phase0:2.0s", text)

    def test_environment_fingerprint_structure(self) -> None:
        root = Path(__file__).resolve().parents[2]
        fingerprint = environment_fingerprint(root)
        self.assertIn("python_version", fingerprint)
        self.assertIn("repository_sha", fingerprint)


class PerformanceVarianceTests(unittest.TestCase):
    def test_summarize_variance_statistics(self) -> None:
        stats = summarize_variance([3.4, 3.5, 3.6])
        self.assertEqual(stats["sample_count"], 3.0)
        self.assertAlmostEqual(stats["median_seconds"], 3.5)
        self.assertGreater(stats["stdev_seconds"], 0.0)


class PerformancePlanModeTests(unittest.TestCase):
    def test_plan_mode_has_no_performance_classification_requirement(self) -> None:
        root = Path(__file__).resolve().parents[2]
        from tools.validate import build_selection_plan, load_manifest, select_full

        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            (temp_root / "tests").mkdir()
            manifest_path = temp_root / "tools" / "validation_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "domains": ["core"],
                        "core_checkpoint_invalidators": [],
                        "mandatory_invariants": [],
                        "suites": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = load_manifest(manifest_path, repository_root=temp_root)
            plan = build_selection_plan(
                select_full(manifest),
                manifest,
                workers=2,
            )
            self.assertFalse(plan.get("executes_tests", True))
            self.assertIn("execution_schedule", plan)


if __name__ == "__main__":
    unittest.main()
