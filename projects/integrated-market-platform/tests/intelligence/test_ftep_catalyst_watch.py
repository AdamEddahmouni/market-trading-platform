"""FTEP catalyst watch dry-run / fixture mode."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (  # noqa: E402
    collect_ftep_catalyst_watch,
)
from market_platform_foundation.local_state.paths import REPO_ROOT


class FtepCatalystWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_fixture_smoke_when_no_governed_sessions(self) -> None:
        payload = collect_ftep_catalyst_watch(REPO_ROOT, "FTEP-V1-002", fixture_only=True)
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["watch_mode"], "FIXTURE_SMOKE")
        self.assertEqual(payload["summary_count"], 2)
        self.assertEqual(payload["governed_session_ids"], [])
        self.assertTrue(payload["dry_run"])

    def test_watch_catalysts_cli_json(self) -> None:
        env = os.environ.copy()
        env["IMP_PERSIST_STATE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "ftep_watch_catalysts.py"),
                "FTEP-V1-002",
                "--fixture",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["artifact_kind"], "ftep_catalyst_watch_report")


if __name__ == "__main__":
    unittest.main()
