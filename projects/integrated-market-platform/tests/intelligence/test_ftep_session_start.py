"""FTEP session-start dry-run gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from market_platform_foundation.local_state.paths import REPO_ROOT

ROOT = Path(__file__).resolve().parents[2]


class FtepSessionStartDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_session_start_dry_run_cli_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "ftep_session_start.py"),
                "FTEP-V1-002",
                "--dry-run",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "IMP_PERSIST_STATE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["artifact_kind"], "ftep_session_start_gate")
        self.assertFalse(payload["would_create_session"])
        self.assertIn("US_EQUITY_RTH_CLOSED", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
