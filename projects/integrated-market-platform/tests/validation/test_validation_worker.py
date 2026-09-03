"""Tests for structured unittest execution without console scraping."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tools.validation_worker import run_worker
except ModuleNotFoundError as exc:  # RED: report the absent worker as a failure.
    run_worker = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class ValidationWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"validation worker is missing: {IMPORT_ERROR}")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.suite_path = self.root / "tests" / "synthetic"
        self.suite_path.mkdir(parents=True)

    def write_test(self, name: str, source: str) -> Path:
        path = self.suite_path / name
        path.write_text(source, encoding="utf-8")
        return path

    def test_structured_counts_come_from_test_result(self) -> None:
        self.write_test(
            "test_counts.py",
            "import unittest\n"
            "class CountTests(unittest.TestCase):\n"
            "    def test_pass(self): self.assertEqual(2 + 2, 4)\n"
            "    @unittest.skip('not applicable')\n"
            "    def test_skip(self): pass\n"
            "    @unittest.expectedFailure\n"
            "    def test_expected(self): self.assertEqual(1, 2)\n"
            "    @unittest.expectedFailure\n"
            "    def test_unexpected(self): self.assertEqual(1, 1)\n"
            "    def test_failure(self): self.assertEqual('left', 'right')\n"
            "    def test_error(self): raise RuntimeError('boom')\n",
        )
        result = run_worker(
            repository_root=self.root,
            suite_id="synthetic",
            suite_path="tests/synthetic",
        )
        self.assertEqual(result["tests_run"], 6)
        self.assertEqual(result["passes"], 1)
        self.assertEqual(result["skips"], 1)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["expected_failures"], 1)
        self.assertEqual(result["unexpected_successes"], 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["per_test_durations"]), 6)
        self.assertGreaterEqual(result["discovery_seconds"], 0)
        self.assertGreaterEqual(result["wall_seconds"], 0)

    def test_exact_selector_does_not_require_package_directories(self) -> None:
        self.write_test(
            "test_select.py",
            "import unittest\n"
            "class SelectTests(unittest.TestCase):\n"
            "    def test_first(self): self.assertTrue(True)\n"
            "    def test_second(self): self.assertTrue(True)\n",
        )
        selector = "tests/synthetic/test_select.py::SelectTests::test_second"
        result = run_worker(
            repository_root=self.root,
            suite_id="fast",
            selectors=(selector,),
        )
        self.assertEqual(result["tests_run"], 1)
        self.assertEqual(result["passes"], 1)
        self.assertEqual(result["selectors"], [selector])
        self.assertEqual(result["per_test_durations"][0]["selector"], selector)

    def test_missing_selector_is_an_explicit_worker_error(self) -> None:
        self.write_test(
            "test_select.py",
            "import unittest\nclass SelectTests(unittest.TestCase):\n"
            "    def test_present(self): self.assertTrue(True)\n",
        )
        selector = "tests/synthetic/test_select.py::SelectTests::test_missing"
        result = run_worker(repository_root=self.root, suite_id="fast", selectors=(selector,))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tests_run"], 0)
        self.assertIn("selector not found", result["worker_error"])

    def test_selector_results_are_deterministically_ordered(self) -> None:
        self.write_test(
            "test_order.py",
            "import unittest\nclass OrderTests(unittest.TestCase):\n"
            "    def test_a(self): self.assertTrue(True)\n"
            "    def test_b(self): self.assertTrue(True)\n",
        )
        selectors = (
            "tests/synthetic/test_order.py::OrderTests::test_b",
            "tests/synthetic/test_order.py::OrderTests::test_a",
        )
        result = run_worker(repository_root=self.root, suite_id="ordered", selectors=selectors)
        observed = [row["selector"] for row in result["per_test_durations"]]
        self.assertEqual(observed, sorted(selectors))
        self.assertEqual(result["selectors"], list(selectors))

    def test_fixture_profile_counts_repository_fixture_opens(self) -> None:
        fixture = self.root / "tests" / "fixtures" / "sample.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_text('{"ok": true}', encoding="utf-8")
        self.write_test(
            "test_fixture.py",
            "import pathlib, unittest\n"
            "ROOT = pathlib.Path(__file__).resolve().parents[2]\n"
            "class FixtureTests(unittest.TestCase):\n"
            "    def test_read(self):\n"
            "        self.assertIn('ok', (ROOT/'tests/fixtures/sample.json').read_text())\n",
        )
        result = run_worker(
            repository_root=self.root,
            suite_id="fixture",
            suite_path="tests/synthetic",
            profile_fixtures=True,
        )
        profile = result["fixture_io"]
        self.assertGreaterEqual(profile["opens"], 1)
        self.assertGreaterEqual(profile["estimated_bytes"], fixture.stat().st_size)
        self.assertEqual(profile["files"][0]["path"], "tests/fixtures/sample.json")

    def test_cli_emits_one_json_document(self) -> None:
        self.write_test(
            "test_cli.py",
            "import unittest\nclass CliTests(unittest.TestCase):\n"
            "    def test_print(self):\n"
            "        print('diagnostic noise')\n"
            "        self.assertTrue(True)\n",
        )
        worker = Path(__file__).resolve().parents[2] / "tools" / "validation_worker.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(worker),
                "--repository-root",
                str(self.root),
                "--suite-id",
                "synthetic",
                "--suite-path",
                "tests/synthetic",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["tests_run"], 1)
        self.assertEqual(payload["passes"], 1)
        self.assertNotIn("diagnostic noise", completed.stdout)


if __name__ == "__main__":
    unittest.main()
