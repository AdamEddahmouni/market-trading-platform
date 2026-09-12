"""FTEP session-start dry-run gates and governed execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_platform_foundation.local_state.startup import reset_local_state_for_tests  # noqa: E402
from tools.ftep_session_start import (  # noqa: E402
    _build_forward_test_invoke_steps,
    execute_governed_session_start,
)


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

    def test_execute_blocked_without_persistence(self) -> None:
        prior_persist = os.environ.pop("IMP_PERSIST_STATE", None)
        prior_state_dir = os.environ.pop("IMP_STATE_DIR", None)
        try:
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.campaign_status.is_within_us_equity_rth",
                return_value=True,
            ):
                payload, exit_code = execute_governed_session_start(ROOT, "FTEP-V1-002")
        finally:
            if prior_persist is not None:
                os.environ["IMP_PERSIST_STATE"] = prior_persist
            if prior_state_dir is not None:
                os.environ["IMP_STATE_DIR"] = prior_state_dir
        self.assertEqual(exit_code, 1)
        self.assertIn("PERSISTENCE_NOT_CONFIGURED", payload["blockers"])

    def test_execute_creates_durable_session_with_mock_rth(self) -> None:
        evidence_path = ROOT / "artifacts/ftep-v1-002/governed-session-start-evidence.jsonl"
        prior_size = evidence_path.stat().st_size if evidence_path.exists() else 0
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reset_local_state_for_tests()
        try:
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.campaign_status.is_within_us_equity_rth",
                return_value=True,
            ):
                payload, exit_code = execute_governed_session_start(ROOT, "FTEP-V1-002")
        finally:
            reset_local_state_for_tests()
            os.environ.pop("IMP_STATE_DIR", None)
            os.environ.pop("IMP_PERSIST_STATE", None)
            tmp.cleanup()
            if evidence_path.exists():
                if prior_size == 0:
                    evidence_path.unlink()
                else:
                    evidence_path.write_bytes(evidence_path.read_bytes()[:prior_size])
        self.assertEqual(exit_code, 0)
        sessions = payload.get("sessions_created") or []
        self.assertGreaterEqual(len(sessions), 1)
        self.assertTrue(payload.get("evidence_paths"))


if __name__ == "__main__":
    unittest.main()
