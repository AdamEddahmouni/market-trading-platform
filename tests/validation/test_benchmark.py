"""Tests for the informational validation and production benchmark tool."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tools.benchmark import measure_operation, run_benchmarks, write_report
except ModuleNotFoundError as exc:  # RED: make the missing implementation diagnosable.
    measure_operation = None  # type: ignore[assignment]
    run_benchmarks = None  # type: ignore[assignment]
    write_report = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[2]


class BenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"benchmark tool is missing: {IMPORT_ERROR}")

    def test_operation_measurements_are_informational_not_threshold_gates(self) -> None:
        row = measure_operation("addition", lambda: 1 + 1, iterations=5, repeat=2)

        self.assertEqual(row["name"], "addition")
        self.assertEqual(row["availability"], "measured")
        self.assertEqual(row["iterations_per_sample"], 5)
        self.assertEqual(len(row["sample_seconds"]), 2)
        self.assertGreaterEqual(row["median_seconds_per_operation"], 0.0)
        self.assertNotIn("passed", row)
        self.assertNotIn("threshold", row)

    def test_unavailable_operation_has_reason_and_no_fabricated_timing(self) -> None:
        def unavailable() -> None:
            raise ImportError("fixed fixture adapter is not available")

        row = measure_operation("optional_operation", unavailable, iterations=3, repeat=2)

        self.assertEqual(row["availability"], "unavailable")
        self.assertIn("fixed fixture adapter", row["reason"])
        self.assertNotIn("sample_seconds", row)
        self.assertNotIn("median_seconds_per_operation", row)

    def test_report_measures_startup_worker_and_minimum_production_operations(self) -> None:
        report = run_benchmarks(
            ROOT,
            repeat=1,
            operation_iterations=2,
            include_fast=False,
        )

        self.assertEqual(report["report_type"], "informational_benchmark")
        runner = {row["name"]: row for row in report["runner_overhead"]}
        self.assertEqual(runner["python_startup"]["availability"], "measured")
        self.assertEqual(runner["tiny_unittest_worker"]["availability"], "measured")
        self.assertEqual(runner["fast_validation"]["availability"], "not_requested")

        production = {row["name"]: row for row in report["production_operations"]}
        required_measured = {
            "p0_as_of_lookup",
            "bitemporal_revision_lookup",
            "fred_registry_lookup",
            "eia_registry_lookup",
            "macro_state_as_of",
            "energy_market_context",
            "short_pressure_state",
            "cftc_product_mapping",
            "representative_simulation_operation",
        }
        self.assertTrue(required_measured.issubset(production))
        for name in required_measured:
            self.assertEqual(production[name]["availability"], "measured", production[name])
            self.assertIn("fixture_refs", production[name])
            self.assertTrue(production[name]["fixture_refs"], production[name])
        self.assertNotIn("overall_pass", report)
        self.assertNotIn("performance_thresholds", report)

    def test_optional_fast_command_records_subprocess_measurement(self) -> None:
        report = run_benchmarks(
            ROOT,
            repeat=1,
            operation_iterations=1,
            include_fast=True,
            fast_command=(sys.executable, "-c", "raise SystemExit(0)"),
        )

        runner = {row["name"]: row for row in report["runner_overhead"]}
        self.assertEqual(runner["fast_validation"]["availability"], "measured")
        self.assertEqual(runner["fast_validation"]["return_codes"], [0])

    def test_report_is_written_only_through_explicit_write_call(self) -> None:
        report = run_benchmarks(ROOT, repeat=1, operation_iterations=1)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested" / "benchmark.json"
            self.assertFalse(output.exists())

            write_report(output, report)

            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)


if __name__ == "__main__":
    unittest.main()
