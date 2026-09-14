"""FTEP integrity check read model."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (
    load_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
    collect_ftep_integrity_checks,
)
from market_platform_foundation.local_state.paths import REPO_ROOT
from market_platform_foundation.local_state.startup import (
    open_local_state,
    reset_local_state_for_tests,
)

T0 = 1_700_000_000_000_000_000
HOUR_NS = 3_600_000_000_000


class FtepIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_v1_002_integrity_surfaces_persistence_hint_without_env(self) -> None:
        prior_persist = os.environ.pop("IMP_PERSIST_STATE", None)
        prior_state_dir = os.environ.pop("IMP_STATE_DIR", None)
        try:
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        finally:
            if prior_persist is not None:
                os.environ["IMP_PERSIST_STATE"] = prior_persist
            if prior_state_dir is not None:
                os.environ["IMP_STATE_DIR"] = prior_state_dir
        self.assertEqual(payload["disposition"], "FAIL")
        self.assertIn("campaign_readiness_ready", payload["failed_check_ids"])
        self.assertTrue(payload.get("operator_hints"))
        self.assertIn("IMP_PERSIST_STATE", payload["operator_hints"][0])

    def test_v1_002_integrity_passes(self) -> None:
        payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["failed_check_ids"], [])

    def test_signal_only_started_requires_durable_session_counts(self) -> None:
        manifest = load_activation_manifest("FTEP-V1-002")
        campaign_id = str(manifest.campaign_id or "")
        self.assertTrue(campaign_id)

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                local = open_local_state(force=True)
                self.assertIsNotNone(local)
                connection = local.connection
                for index in range(2):
                    connection.execute(
                        """
                        INSERT INTO forward_test_sessions(
                            session_id, account_id, mode, strategy_id, strategy_version,
                            universe_json, evaluation_horizon_ns, created_at_ns, status,
                            config_json, campaign_id
                        ) VALUES (?, ?, 'PAPER', 'news_deterministic_baseline', '1.0.0',
                                  '["AAPL"]', ?, ?, 'ACTIVE', '{}', ?)
                        """,
                        (
                            f"fts-signal-only-{index}",
                            f"paper-signal-only-{index}",
                            HOUR_NS,
                            T0 + index,
                            campaign_id,
                        ),
                    )
                payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

        check = next(
            item
            for item in payload["checks"]
            if item["check_id"] == "signal_only_session_requires_durable_state"
        )
        self.assertTrue(check["passed"])
        self.assertIn("sessions=2", check["detail"])
        self.assertNotIn(
            "signal_only_session_requires_durable_state",
            payload["failed_check_ids"],
        )

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
