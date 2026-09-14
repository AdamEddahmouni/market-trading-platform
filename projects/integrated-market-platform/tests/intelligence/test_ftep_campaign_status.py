"""FTEP campaign status read model."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (
    collect_ftep_campaign_status,
)
from market_platform_foundation.local_state.paths import REPO_ROOT


class FtepCampaignStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_ftep_v1_002_status_snapshot(self) -> None:
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.campaign_status.is_within_us_equity_rth",
            return_value=False,
        ):
            payload = collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
        self.assertEqual(payload["campaign_slug"], "FTEP-V1-002")
        self.assertEqual(payload["calendar_scope"], "US_EQUITY_RTH")
        self.assertFalse(payload["us_equity_rth_open"])
        self.assertEqual(payload["campaign_readiness_disposition"], "READY")
        self.assertTrue(payload["signal_only_authorized"])
        self.assertTrue(payload["empirical_lock_authorized"])
        self.assertFalse(payload["manifest_operator_empirical_lock_authorized"])
        self.assertFalse(payload["signal_only_session_started"])
        self.assertEqual(payload["empirical_lock_count"], 0)
        self.assertEqual(payload["empirical_counts_source"], "durable")
        self.assertFalse(payload["secrets_included"])
        self.assertEqual(
            payload["manifest_fingerprint"],
            "F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1",
        )

    def test_status_cli_module_runs(self) -> None:
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env["IMP_PERSIST_STATE"] = "1"
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "ftep_campaign_status.py"), "FTEP-V1-002", "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ftep_campaign_status", result.stdout)


if __name__ == "__main__":
    unittest.main()
