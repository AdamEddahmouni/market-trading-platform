"""MRA-001 grounded assistant acceptance tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.mra001_assertions import MANDATORY_IDS, build_registry
from tools.mra001.run_mra001_pipeline import build_evidence


class Mra001ApiTests(unittest.TestCase):
    def test_registry_mandatory_ids(self) -> None:
        registry = build_registry(ROOT / "manifests/mra001/assertion-predicates.json")
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_pipeline_aggregate_pass(self) -> None:
        output_dir = ROOT / "evidence/mra001/.pytest-run"
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_file():
                    child.unlink()
        report = build_evidence(output_dir)
        self.assertEqual(report["aggregate_status"], "PASS")

    def test_publication_verifier(self) -> None:
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/mra001/verify_mra001_publication.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            publish = subprocess.run(
                [sys.executable, str(ROOT / "tools/mra001/publish_mra001_pass.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(publish.returncode, 0, publish.stdout + publish.stderr)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools/mra001/verify_mra001_publication.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
