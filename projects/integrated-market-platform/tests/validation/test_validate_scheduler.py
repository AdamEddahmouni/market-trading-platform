"""P2 scheduler and concurrency contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import validate as validate_module
from tools.validate import (
    ValidationSelection,
    build_execution_schedule,
    build_selection_plan,
    execute_selection,
    resolve_workers,
    schedule_to_dict,
    select_full,
)
from tools.validation_manifest import load_manifest


class ValidateSchedulerTests(unittest.TestCase):
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
        resource_weight: int = 1,
        resource_class: str | None = None,
        concurrency_reason: str = "",
        exclusive_group: str | None = None,
        max_concurrency: int | None = None,
        live_provider: str | None = None,
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
            "resource_weight": resource_weight,
            "source_globs": [],
            "test_globs": [f"tests/{suite_id}/test_*.py"],
            "neighbors": [],
        }
        if resource_class is not None:
            row["resource_class"] = resource_class
        if concurrency_reason:
            row["concurrency_reason"] = concurrency_reason
        if exclusive_group is not None:
            row["exclusive_group"] = exclusive_group
        if max_concurrency is not None:
            row["max_concurrency"] = max_concurrency
        if live_provider is not None:
            row["live_provider"] = live_provider
        return row

    def manifest(self, suites: list[dict[str, object]]):
        path = self.root / "tools" / "validation_manifest.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "domains": ["core"],
                    "core_checkpoint_invalidators": [],
                    "mandatory_invariants": [],
                    "suites": suites,
                }
            ),
            encoding="utf-8",
        )
        return load_manifest(path, repository_root=self.root)

    def test_one_safe_suite_executes_once(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([suite])
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=select_full(manifest),
            workers=2,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tests_run"], 1)
        self.assertEqual(len(result["suite_results"]), 1)

    def test_multiple_safe_suites_run_concurrently(self) -> None:
        slow = self.write_suite(
            "slow",
            "import time, unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_slow(self): time.sleep(0.08); self.assertTrue(True)\n",
            resource_weight=3,
        )
        fast = self.write_suite(
            "fast",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([slow, fast])
        schedule = build_execution_schedule(
            manifest, select_full(manifest), workers=2
        )
        self.assertEqual(schedule.waves[0].policy, "PARALLEL_SAFE")
        self.assertEqual(schedule.waves[0].concurrency, 2)
        self.assertEqual(schedule.waves[0].suite_ids[0], "slow")
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=select_full(manifest),
            workers=2,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tests_run"], 2)
        self.assertEqual(result["effective_workers"], 2)

    def test_serial_required_never_overlaps_parallel_safe(self) -> None:
        serial = self.write_suite(
            "serial",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            safety="SERIAL_REQUIRED",
            resource_class="SERIAL",
        )
        safe = self.write_suite(
            "safe",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([serial, safe])
        schedule = build_execution_schedule(
            manifest, select_full(manifest), workers=2
        )
        self.assertEqual(schedule.waves[0].policy, "SERIAL_REQUIRED")
        self.assertEqual(schedule.waves[1].policy, "PARALLEL_SAFE")

    def test_two_serial_required_run_serially(self) -> None:
        first = self.write_suite(
            "first",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            safety="SERIAL_REQUIRED",
        )
        second = self.write_suite(
            "second",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            safety="SERIAL_REQUIRED",
        )
        manifest = self.manifest([first, second])
        schedule = build_execution_schedule(
            manifest, select_full(manifest), workers=4
        )
        self.assertEqual(schedule.waves[0].concurrency, 1)
        self.assertEqual(schedule.waves[0].suite_ids, ("first", "second"))

    def test_resource_heavy_respects_concurrency_cap(self) -> None:
        heavy = self.write_suite(
            "heavy",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            safety="RESOURCE_HEAVY",
            resource_class="HEAVY",
        )
        manifest = self.manifest([heavy])
        schedule = build_execution_schedule(
            manifest, select_full(manifest), workers=4
        )
        self.assertEqual(schedule.waves[-1].policy, "RESOURCE_HEAVY")
        self.assertEqual(schedule.waves[-1].concurrency, 2)

    def test_unknown_parallel_safety_falls_back_serial(self) -> None:
        unknown = self.write_suite(
            "unknown",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            safety="PARALLEL_SAFE",
        )
        manifest = self.manifest([unknown])
        with patch.object(
            validate_module,
            "scheduling_policy",
            return_value="UNKNOWN_FAIL_SAFE",
        ):
            schedule = build_execution_schedule(
                manifest, select_full(manifest), workers=2
            )
        self.assertEqual(schedule.waves[0].policy, "SERIAL_REQUIRED")

    def test_live_exclusive_scheduled_serial(self) -> None:
        live = self.write_suite(
            "live_eia",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            classification="live",
            safety="LIVE_EXCLUSIVE",
            resource_class="LIVE_EXCLUSIVE",
            live_provider="eia",
        )
        manifest = self.manifest([live])
        schedule = build_execution_schedule(
            manifest,
            ValidationSelection(mode="live", selected_suite_ids=("live_eia",)),
            workers=2,
        )
        self.assertEqual(schedule.waves[-1].policy, "LIVE_EXCLUSIVE")
        self.assertEqual(schedule.waves[-1].concurrency, 1)

    def test_worker_failure_propagates(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([suite])
        with patch.object(
            validate_module,
            "run_worker_process",
            return_value={
                "status": "error",
                "suite_id": "alpha",
                "tests_run": 0,
                "passes": 0,
                "skips": 0,
                "failures": 0,
                "errors": 1,
                "worker_error": "boom",
            },
        ):
            result = execute_selection(
                repository_root=self.root,
                manifest=manifest,
                selection=select_full(manifest),
                workers=1,
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"], 1)

    def test_malformed_worker_receipt_fails_explicitly(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([suite])
        crash = self.root / "crash.py"
        crash.write_text("raise SystemExit(9)\n", encoding="utf-8")
        result = validate_module.run_worker_process(
            repository_root=self.root,
            suite_id="alpha",
            suite_path=str(suite["path"]),
            worker_path=crash,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("exited 9", result["worker_error"])

    def test_deterministic_report_order(self) -> None:
        suites = [
            self.write_suite(
                f"suite_{index}",
                "import unittest\nclass Tests(unittest.TestCase):\n"
                f"    def test_{index}(self): self.assertTrue(True)\n",
            )
            for index in range(3)
        ]
        manifest = self.manifest(suites)
        selection = select_full(manifest)
        first = build_execution_schedule(manifest, selection, workers=2)
        second = build_execution_schedule(manifest, selection, workers=2)
        self.assertEqual(schedule_to_dict(first), schedule_to_dict(second))

    def test_worker_count_clamp(self) -> None:
        self.assertEqual(resolve_workers(99, parallel_eligible_count=2), 2)
        self.assertEqual(resolve_workers(0, env={"IMP_VALIDATION_WORKERS": "3"}), 3)
        self.assertEqual(resolve_workers(-1, env={"IMP_VALIDATION_WORKERS": "bad"}), 2)

    def test_plan_mode_executes_zero_tests(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([suite])
        plan = build_selection_plan(select_full(manifest), manifest, workers=2)
        self.assertFalse(plan["executes_tests"])
        self.assertIn("execution_schedule", plan)
        self.assertEqual(plan["execution_schedule"]["waves"][0]["policy"], "PARALLEL_SAFE")

    def test_execution_receipt_includes_schedule_metadata(self) -> None:
        suite = self.write_suite(
            "alpha",
            "import unittest\nclass Tests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
        )
        manifest = self.manifest([suite])
        result = execute_selection(
            repository_root=self.root,
            manifest=manifest,
            selection=select_full(manifest),
            workers=2,
        )
        self.assertEqual(result["scheduler_version"], validate_module.SCHEDULER_VERSION)
        self.assertIn("execution_schedule", result)
        self.assertEqual(result["effective_workers"], 1)


if __name__ == "__main__":
    unittest.main()
