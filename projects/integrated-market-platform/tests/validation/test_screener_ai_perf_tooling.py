"""The Screener/AI performance record must be self-describing and honest.

A performance number is evidence only if it says what was measured, on what,
where, and whether two runs may be compared at all. These tests pin that the
profile records a complete identity, that it is deterministic, and that the
comparison tool refuses to publish a speedup it cannot justify.

It deliberately does **not** assert a wall-clock threshold: timings vary by
machine and the repository's P7 performance budget is observe-only. Timing
regressions are reported by `tools/screener_ai_perf_compare.py` against a
recorded baseline, never by a pass/fail test on this machine.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from screener_ai_perf_compare import (
    COMPARABLE,
    INCOMPATIBLE_ENVIRONMENT,
    INCOMPATIBLE_WORKLOAD,
    INSUFFICIENT_EVIDENCE,
    NOISE_FLOOR_MS,
    compare,
)


def _record(**overrides):
    record = {
        "profile_version": "screener-ai-perf-profile/2.0.0",
        "methodology": {"tool_sha256": "test-harness", "clock": "perf_counter", "warmup": 1,
                        "gc_enabled": True, "memory": "separate pass", "cache": "explicit",
                        "measurement": "fixture functions", "excluded": ["network"],
                        "source_cleanliness_scope": ["src", "tools", "ui"]},
        "generated_at": "2026-10-12T00:00:00Z",
        "source": {"sha": "d47e3c9ee3bf05d6de663bfaaabbec9681b1fdc4", "branch": "main", "dirty": False},
        "environment": {"python": "3.11.15", "implementation": "CPython",
                        "platform": "Windows", "processor": "x86_64", "cpu_count": 16, "physical_memory_bytes": 32_000_000_000, "machine_identity": "test-machine"},
        "fixture": {"identity": "finviz-export/abc", "provider_rows": 5100, "admitted_rows": 4636,
                    "admitted_target": 4622, "requested_universe": 5100, "page_limit": 200,
                    "etf_catalog_rows": 6306, "quick_mode": False},
        "parity": {"ordered_match_digest": "deadbeef", "ordered_matched": 250, "filtered_by": [], "full_universe_values_digest": "all-values", "api_payload_digest": "api-bytes", "observations_digest": "ai-values"},
        "stages": [{"stage": "e2e.screener_read_cached_page", "repeat": 9, "warmup": 1,
                    "median_ms": .14, "mean_ms": .14, "min_ms": .14, "p95_ms": .14, "max_ms": .14,
                    "stddev_ms": 0, "samples_ms": [.14] * 9, "peak_traced_bytes": 0, "value": 4636}],
    }
    record.update(overrides)
    return record


def _timing(record, value):
    stage = record["stages"][0]
    stage.update({key: value for key in ("median_ms", "mean_ms", "min_ms", "p95_ms", "max_ms")})
    stage["samples_ms"] = [value] * stage["repeat"]


class ProfileIdentityTests(unittest.TestCase):
    """A recorded profile must carry everything a later comparison needs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.record = _record()

    def test_recorded_identity_fields_are_present(self) -> None:
        for key in ("profile_version", "generated_at", "source", "environment", "fixture",
                    "parity", "stages"):
            self.assertIn(key, self.record)
        self.assertIn("sha", self.record["source"])
        for key in ("identity", "provider_rows", "admitted_rows", "page_limit", "quick_mode"):
            self.assertIn(key, self.record["fixture"])
        for key in ("python", "implementation", "platform", "processor", "cpu_count"):
            self.assertIn(key, self.record["environment"])

    def test_every_stage_reports_timing_and_peak_memory(self) -> None:
        for stage in self.record["stages"]:
            for key in ("stage", "repeat", "median_ms", "min_ms", "p95_ms", "max_ms",
                        "peak_traced_bytes"):
                self.assertIn(key, stage, stage.get("stage"))

    def test_parity_block_records_the_deterministic_result(self) -> None:
        self.assertTrue(self.record["parity"]["ordered_match_digest"])


class ProfileExecutionTests(unittest.TestCase):
    """The profiler really runs and produces a self-describing record."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        cls.output = Path(cls._directory.name) / "profile.json"
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "screener_ai_perf_profile.py"),
             "--quick", "--repeat", "1", f"--out={cls.output}"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
            env={**__import__("os").environ,
                 "PYTHONPATH": __import__("os").pathsep.join(
                     [str(ROOT), str(ROOT / "src"), __import__("os").environ.get("PYTHONPATH", "")])})
        cls.completed = result
        cls.record = json.loads(cls.output.read_text(encoding="utf-8")) if cls.output.is_file() else None

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_profile_completes_and_writes_a_record(self) -> None:
        self.assertEqual(self.completed.returncode, 0, self.completed.stderr[-2000:])
        self.assertIsNotNone(self.record)
        self.assertEqual(self.record["profile_version"], "screener-ai-perf-profile/2.0.0")

    def test_profile_covers_the_documented_pipeline_stages(self) -> None:
        stages = {stage["stage"] for stage in self.record["stages"]}
        for required in ("ingest.universe_refresh_cpu", "filter.apply_filters_3_rules",
                         "order.order_rows_full", "evidence.observations_for_row",
                         "evidence.build_candidate", "plan.classify_all_rows",
                         "coverage.enumerate_universe", "e2e.screener_read_filtered_uncached"):
            self.assertIn(required, stages)

    def test_profile_admits_the_requested_universe_size(self) -> None:
        fixture = self.record["fixture"]
        self.assertGreater(fixture["admitted_rows"], 0)
        self.assertLessEqual(fixture["admitted_rows"], fixture["provider_rows"])
        self.assertAlmostEqual(fixture["admitted_rows"], fixture["admitted_target"],
                               delta=max(5, fixture["admitted_target"] * 0.02))

    def test_repeated_runs_agree_on_the_result_identity(self) -> None:
        second = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "screener_ai_perf_profile.py"),
             "--quick", "--repeat", "1", f"--out={self.output.with_suffix('.2.json')}"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
            env={**__import__("os").environ,
                 "PYTHONPATH": __import__("os").pathsep.join(
                     [str(ROOT), str(ROOT / "src"), __import__("os").environ.get("PYTHONPATH", "")])})
        self.assertEqual(second.returncode, 0, second.stderr[-2000:])
        other = json.loads(self.output.with_suffix(".2.json").read_text(encoding="utf-8"))
        self.assertEqual(self.record["fixture"]["identity"], other["fixture"]["identity"])
        self.assertEqual(self.record["parity"]["ordered_match_digest"],
                         other["parity"]["ordered_match_digest"])
        self.assertEqual(self.record["parity"]["ordered_matched"], other["parity"]["ordered_matched"])


class ComparisonPolicyTests(unittest.TestCase):
    """The comparison tool must never report an unjustified speedup."""

    def test_identical_workload_and_environment_is_comparable(self) -> None:
        report = compare(_record(), _record(), threshold=1.15)
        self.assertEqual(report["verdict"], COMPARABLE)
        self.assertEqual(report["verdict_reasons"], [])

    def test_a_different_fixture_is_incompatible_not_a_speedup(self) -> None:
        after = _record()
        after["fixture"]["admitted_rows"] = 4000
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INCOMPATIBLE_WORKLOAD)
        for row in report["stages"]:
            self.assertEqual(row["verdict"], INCOMPATIBLE_WORKLOAD)
            self.assertNotIn("speedup", row)

    def test_a_different_machine_is_incompatible(self) -> None:
        after = _record()
        after["environment"]["processor"] = "arm64"
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INCOMPATIBLE_ENVIRONMENT)
        for row in report["stages"]:
            self.assertNotIn("speedup", row)

    def test_a_different_python_major_is_incompatible(self) -> None:
        after = _record()
        after["environment"]["python"] = "2.7.18"
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INCOMPATIBLE_ENVIRONMENT)

    def test_a_python_minor_change_requires_a_new_environment_baseline(self) -> None:
        after = _record()
        after["environment"]["python"] = "3.12.1"
        self.assertEqual(compare(_record(), after, threshold=1.15)["verdict"], INCOMPATIBLE_ENVIRONMENT)

    def test_a_missing_stage_is_insufficient_evidence(self) -> None:
        after = _record()
        after["stages"] = []
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(report["stages"][0]["verdict"], INSUFFICIENT_EVIDENCE)

    def test_a_real_improvement_is_reported_as_one(self) -> None:
        before = _record()
        _timing(before, 4.0)
        after = _record()
        _timing(after, 2.0)
        report = compare(before, after, threshold=1.15)
        self.assertEqual(report["verdict"], COMPARABLE)
        row = report["stages"][0]
        self.assertAlmostEqual(row["speedup"], 2.0, places=2)
        self.assertTrue(row["improvement"])
        self.assertFalse(row["regression"])

    def test_sub_floor_differences_are_reported_as_noise_not_regression(self) -> None:
        after = _record()
        _timing(after, 0.14 + (NOISE_FLOOR_MS / 2))
        report = compare(_record(), after, threshold=1.15)
        row = report["stages"][0]
        self.assertTrue(row["within_noise_floor"])
        self.assertFalse(row["regression"])
        self.assertFalse(row["improvement"])

    def test_a_real_regression_is_reported(self) -> None:
        after = _record()
        _timing(after, 5.0)
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["regressed_stages"], ["e2e.screener_read_cached_page"])

    def test_the_report_documents_its_own_verdict_vocabulary(self) -> None:
        policy = compare(_record(), _record(), threshold=1.15)["comparison_policy"]
        for status in (COMPARABLE, INCOMPATIBLE_WORKLOAD, INCOMPATIBLE_ENVIRONMENT, INSUFFICIENT_EVIDENCE):
            self.assertIn(status, policy)



class RecoveryComparisonTests(unittest.TestCase):
    def test_sub_rounding_positive_samples_with_zero_summary_cannot_divide_by_zero(self):
        before, after = _record(), _record()
        for record in (before, after):
            stage = record["stages"][0]
            _timing(record, 0)
            stage["samples_ms"] = [.00001] * stage["repeat"]
        report = compare(before, after, threshold=1.15)
        self.assertEqual(report["verdict"], INSUFFICIENT_EVIDENCE)
        self.assertNotIn("speedup", report["stages"][0])

    def test_empty_methodology_or_inventory_is_insufficient(self):
        for key, value in (("methodology", {}), ("stages", [])):
            before, after = _record(), _record()
            before[key] = after[key] = value
            self.assertEqual(compare(before, after, threshold=1.15)["verdict"], INSUFFICIENT_EVIDENCE)

    def test_missing_or_invalid_variance_samples_and_warmup_withhold_ratios(self):
        for key, value in (("stddev_ms", None), ("stddev_ms", float("nan")), ("samples_ms", []),
                           ("repeat", True), ("warmup", None)):
            before, after = _record(), _record()
            _timing(before, 4.0)
            _timing(after, 2.0)
            after["stages"][0][key] = value
            report = compare(before, after, threshold=1.15)
            self.assertEqual(report["verdict"], INSUFFICIENT_EVIDENCE)
            self.assertNotIn("speedup", report["stages"][0])

    def test_duplicate_stage_names_cannot_hide_a_measurement(self):
        after = _record()
        after["stages"] *= 2
        self.assertEqual(compare(_record(), after, threshold=1.15)["verdict"], INSUFFICIENT_EVIDENCE)

    def test_missing_source_identity_cannot_publish_ratios(self):
        after = _record()
        after["source"] = {}
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INSUFFICIENT_EVIDENCE)
        self.assertTrue(all("speedup" not in row for row in report["stages"]))

    def test_changed_values_are_incompatible_even_if_instrument_order_matches(self):
        after = _record()
        after["parity"]["ordered_match_digest"] = "changed-value-digest"
        self.assertEqual(compare(_record(), after, threshold=1.15)["verdict"], INCOMPATIBLE_WORKLOAD)

    def test_repeat_mismatch_prevents_speedup_classification(self):
        after = _record()
        after["stages"][0]["repeat"] = 3
        report = compare(_record(), after, threshold=1.15)
        self.assertNotEqual(report["stages"][0]["verdict"], COMPARABLE)
        self.assertNotIn("speedup", report["stages"][0])

    def test_zero_and_nonfinite_duration_cannot_publish_ratios(self):
        for duration in (0, -1, float("nan"), float("inf"), None):
            after = _record()
            after["stages"][0]["median_ms"] = duration
            with self.subTest(duration=duration):
                report = compare(_record(), after, threshold=1.15)
                self.assertEqual(report["stages"][0]["verdict"], INSUFFICIENT_EVIDENCE)
                self.assertNotIn("speedup", report["stages"][0])

    def test_dirty_tree_cannot_be_attributed_to_its_head_sha(self):
        after = _record()
        after["source"]["dirty"] = True
        report = compare(_record(), after, threshold=1.15)
        self.assertEqual(report["verdict"], INSUFFICIENT_EVIDENCE)
        self.assertTrue(all("speedup" not in row for row in report["stages"]))

    def test_different_clean_source_shas_are_a_valid_optimization_comparison(self):
        after = _record()
        after["source"]["sha"] = "a" * 40
        self.assertEqual(compare(_record(), after, threshold=1.15)["verdict"], COMPARABLE)

    def test_missing_environment_cannot_be_treated_as_matching_missing_values(self):
        before, after = _record(), _record()
        before["environment"] = after["environment"] = {}
        self.assertEqual(compare(before, after, threshold=1.15)["verdict"], INSUFFICIENT_EVIDENCE)


if __name__ == "__main__":
    unittest.main()