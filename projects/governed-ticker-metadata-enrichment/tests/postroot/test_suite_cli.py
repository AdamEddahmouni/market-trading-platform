import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = ROOT / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'};{ROOT}"}


class SuiteCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.first = Path(self.temp_dir.name) / "first.json"
        self.second = Path(self.temp_dir.name) / "second.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_builder(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/postroot/build_postroot_acceptance_suite.py"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=SUBPROCESS_ENV,
        )

    def run_validator(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/postroot/validate_postroot_acceptance_suite.py"), str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=SUBPROCESS_ENV,
        )

    def test_two_writes_are_byte_identical(self):
        first = self.run_builder("--write", str(self.first))
        second = self.run_builder("--write", str(self.second))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(self.first.read_bytes(), self.second.read_bytes())
        self.assertFalse(self.first.read_bytes().endswith(b"\n"))

    def test_check_rejects_changed_bytes(self):
        self.run_builder("--write", str(self.first))
        self.first.write_bytes(self.first.read_bytes() + b"\n")
        result = self.run_builder("--check", str(self.first))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SUITE-BYTES-MISMATCH", result.stderr)

    def test_committed_suite_validates(self):
        if not SUITE_PATH.is_file():
            self.skipTest("committed suite not generated yet")
        result = self.run_validator(SUITE_PATH)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertGreater(report["fixture_count"], 40)

    def test_changed_suite_is_rejected(self):
        if not SUITE_PATH.is_file():
            self.skipTest("committed suite not generated yet")
        changed = Path(self.temp_dir.name) / "changed.json"
        changed.write_bytes(SUITE_PATH.read_bytes() + b"\n")
        result = self.run_validator(changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(str(changed.resolve()), result.stderr)


if __name__ == "__main__":
    unittest.main()
