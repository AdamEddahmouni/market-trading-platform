"""FTEP session-start dry-run gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ftep_session_start import _build_forward_test_invoke_steps  # noqa: E402


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
        self.assertNotIn("forward_test_invoke_steps", payload)

    def test_forward_test_invoke_steps_for_v1_002_manifest(self) -> None:
        steps = _build_forward_test_invoke_steps(ROOT, "FTEP-V1-002")
        create_calls = [
            item for item in steps if item.get("action") == "ForwardTestService.create_session"
        ]
        self.assertEqual(len(create_calls), 2)
        arms = {str(item["kwargs"]["cohort_arm"]) for item in create_calls}
        self.assertEqual(arms, {"BASELINE", "AI_ENHANCED"})


if __name__ == "__main__":
    unittest.main()
