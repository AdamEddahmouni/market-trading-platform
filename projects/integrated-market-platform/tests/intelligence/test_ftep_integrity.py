"""FTEP integrity check read model."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
    collect_ftep_integrity_checks,
)
from market_platform_foundation.local_state.paths import REPO_ROOT


class FtepIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_v1_002_integrity_passes(self) -> None:
        payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["failed_check_ids"], [])

    def test_integrity_cli_module_runs(self) -> None:
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env["IMP_PERSIST_STATE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "ftep_integrity_check.py"),
                "FTEP-V1-002",
                "--json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ftep_integrity_report", result.stdout)


if __name__ == "__main__":
    unittest.main()
