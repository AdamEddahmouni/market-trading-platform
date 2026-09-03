"""MRA-002 Anthropic assistant acceptance tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.mra002_assertions import MANDATORY_IDS, build_registry
from tools.mra002.run_mra002_pipeline import build_evidence


class Mra002ApiTests(unittest.TestCase):
    def test_registry_mandatory_ids(self) -> None:
        registry = build_registry(ROOT / "manifests/mra002/assertion-predicates.json")
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_pipeline_aggregate_pass(self) -> None:
        output_dir = ROOT / "evidence/mra002/.pytest-run"
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_file():
                    child.unlink()
        report = build_evidence(output_dir)
        self.assertEqual(report["aggregate_status"], "PASS")

    def test_publication_verifier(self) -> None:
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/mra002/verify_mra002_publication.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            build = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/mra002/run_mra002_pipeline.py"),
                    "--output-dir",
                    str(ROOT / "evidence/mra002/build-run"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            publish = subprocess.run(
                [sys.executable, str(ROOT / "tools/mra002/publish_mra002_pass.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(publish.returncode, 0, publish.stdout + publish.stderr)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools/mra002/verify_mra002_publication.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
