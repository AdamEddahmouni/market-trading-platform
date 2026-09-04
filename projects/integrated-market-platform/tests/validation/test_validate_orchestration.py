"""Tests for subprocess orchestration, gates, fail-fast, and JSON output."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import validate as validate_module
from tools.validate import (
    ValidationSelection,
    execute_selection,
    run_worker_process,
    select_full,
    select_live,
    write_json_atomic,
)
from tools.validation_manifest import load_manifest


class ValidateOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "tests").mkdir()

    def write_suite(
        self,
        suite_id: str,
        source: str,
        *,
        classification: str = "offline",
        safety: str = "PARALLEL_SAFE",
        provider: str | None = None,
    ) -> dict[str, object]:
        path = self.root / "tests" / suite_id
        path.mkdir()
        (path / f"test_{suite_id}.py").write_text(source, encoding="utf-8")
        row: dict[str, object] = {
            "id": suite_id,
            "path": f"tests/{suite_id}",
            "classification": classification,
            "tiers": ["live" if classification == "live" else "full"],
            "domains": ["core"],
            "parallel_safety": safety,
            "resource_weight": 1,
            "source_globs": [],
            "test_globs": [f"tests/{suite_id}/test_*.py"],
            "neighbors": [],
        }
        if provider is not None:
            row["live_provider"] = provider
        return row

    def manifest(self, suites: list[dict[str, object]]):
        path = self.root / "tools" / "validation_manifest.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "domains": ["core"],
                    "full_invalidators": [],
                    "mandatory_invariants": [],
                    "suites": suites,
                }
            ),
            encoding="utf-8",
        )
        return load_manifest(path, repository_root=self.root)

    def test_worker_crash_and_malformed_json_are_explicit_errors(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        crash = self.root / "crash.py"
        crash.write_text("raise SystemExit(7)\n", encoding="utf-8")
        malformed = self.root / "malformed.py"
        malformed.write_text("print('not-json')\n", encoding="utf-8")
        for worker, expected in ((crash, "exited 7"), (malformed, "malformed worker JSON")):
            with self.subTest(worker=worker.name):
                result = run_worker_process(
                    repository_root=self.root,
                    suite_id="alpha",
                    suite_path=str(suite["path"]),
                    worker_path=worker,
                )
                self.assertEqual(result["status"], "error")
                self.assertIn(expected, result["worker_error"])

    def test_full_clears_live_gates_in_child_only(self) -> None:
        suite = self.write_suite(
            "offline",
            "import os, unittest\nclass GateTests(unittest.TestCase):\n"
            "    def test_gate_absent(self): self.assertIsNone(os.environ.get('IMP_EIA_LIVE'))\n",
            safety="SERIAL_REQUIRED",
        )
        manifest = self.manifest([suite])
        with patch.dict(os.environ, {"IMP_EIA_LIVE": "parent-value"}, clear=False):
            result = execute_selection(
                repository_root=self.root,
                manifest=manifest,
                selection=select_full(manifest),
                workers=1,
            )
            self.assertEqual(os.environ["IMP_EIA_LIVE"], "parent-value")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tests_run"], 1)

    def test_weather_live_gate_is_registered_without_credential_gate(self) -> None:
        from tools.validate import LIVE_GATES

        self.assertEqual(LIVE_GATES["weather"], ("IMP_WEATHER_LIVE",))

    def test_live_sets_only_selected_provider_gates_in_child(self) -> None:
        suite = self.write_suite(
            "live_eia",
            "import os, unittest\nclass GateTests(unittest.TestCase):\n"
            "    def test_gate_scope(self):\n"
            "        self.assertEqual(os.environ.get('IMP_EIA_LIVE'), '1')\n"
            "        self.assertIsNone(os.environ.get('RUN_LIVE_CFTC'))\n",
            classification="live",
            safety="LIVE_EXCLUSIVE",
            provider="eia",
        )
        manifest = self.manifest([suite])
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMP_EIA_LIVE", None)
            result = execute_selection(
                repository_root=self.root,
                manifest=manifest,
                selection=select_live(manifest, "eia"),
                workers=1,
                live_provider="eia",
            )
            self.assertNotIn("IMP_EIA_LIVE", os.environ)
        self.assertEqual(result["status"], "passed")

    def test_structured_aggregate_is_independent_of_completion_order(self) -> None:
        slow = self.write_suite(
            "slow",
            "import time, unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_slow(self): time.sleep(0.05); self.assertTrue(True)\n",
        )
        fast = self.write_suite(
            "fast",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    @unittest.skip('expected')\n"
            "    def test_skip(self): pass\n"
            "    def test_pass(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([slow, fast])
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=select_full(manifest),
            workers=2,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tests_run"], 3)
        self.assertEqual(result["passes"], 2)
        self.assertEqual(result["skips"], 1)
        self.assertEqual([row["suite_id"] for row in result["suite_results"]], ["slow", "fast"])

    def test_fail_fast_stops_scheduling_new_serial_suites(self) -> None:
        failed = self.write_suite(
            "failed",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_fail(self): self.fail('stop')\n",
            safety="SERIAL_REQUIRED",
        )
        marker = self.root / "should-not-exist.txt"
        later = self.write_suite(
            "later",
            "import pathlib, unittest\nROOT=pathlib.Path(__file__).resolve().parents[2]\n"
            "class Tests(unittest.TestCase):\n"
            "    def test_later(self):\n"
            "        (ROOT/'should-not-exist.txt').write_text('ran')\n"
            "        self.assertTrue(True)\n",
            safety="SERIAL_REQUIRED",
        )
        manifest = self.manifest([failed, later])
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=select_full(manifest),
            workers=1,
            fail_fast=True,
        )
        self.assertEqual(result["status"], "failed")
        self.assertFalse(marker.exists())
        self.assertEqual(result["not_run_suites"], ["later"])

    def test_atomic_json_write_replaces_target_without_temp_residue(self) -> None:
        target = self.root / "result.json"
        target.write_text("old", encoding="utf-8")
        write_json_atomic(target, {"status": "passed", "tests_run": 2})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["tests_run"], 2)
        self.assertEqual(list(self.root.glob(".result.json.*.tmp")), [])

    def test_benchmark_mode_delegates_to_informational_tool(self) -> None:
        output = self.root / "benchmark.json"
        report = {
            "schema_version": "1.0",
            "report_type": "informational_benchmark",
            "runner_overhead": [],
            "production_operations": [],
        }
        with patch("tools.benchmark.run_benchmarks", return_value=report) as delegated:
            exit_code = validate_module.main(["benchmark", "--json", str(output)])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)
        delegated.assert_called_once()

    def test_explicit_selector_batch_runs_before_selected_suites(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_fast(self): self.assertTrue(True)\n"
            "    def test_full(self): self.assertTrue(True)\n",
            safety="SERIAL_REQUIRED",
        )
        path = self.root / "tools" / "validation_manifest.json"
        path.parent.mkdir(exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "domains": ["core"],
            "full_invalidators": [],
            "mandatory_invariants": [
                {
                    "id": "fast",
                    "selector": "tests/alpha/test_alpha.py::Tests::test_fast",
                    "order": 1,
                    "isolation": "shared",
                }
            ],
            "suites": [suite],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        manifest = load_manifest(path, repository_root=self.root)
        selection = ValidationSelection(
            mode="changed",
            selected_suite_ids=("alpha",),
            mandatory_selectors=("tests/alpha/test_alpha.py::Tests::test_fast",),
        )
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=selection,
            workers=1,
        )
        self.assertEqual(result["worker_results"][0]["suite_id"], "mandatory-shared")
        self.assertEqual(result["tests_run"], 3)


if __name__ == "__main__":
    unittest.main()
