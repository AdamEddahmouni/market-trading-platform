"""FTEP record-prospective-lock dry-run gates (closed-market fixture)."""

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

from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (  # noqa: E402
    empirical_lock_authorized,
    manifest_operator_empirical_lock_authorized,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_lock import (  # noqa: E402
    collect_ftep_prospective_lock_gates,
    manifest_empirical_lock_authorized,
)
from market_platform_foundation.local_state.startup import reset_local_state_for_tests  # noqa: E402


class FtepProspectiveLockDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_manifest_operator_empirical_lock_still_false_for_v1_002(self) -> None:
        self.assertFalse(manifest_operator_empirical_lock_authorized("FTEP-V1-002"))

    def test_empirical_lock_authorized_via_append_only_receipt(self) -> None:
        self.assertTrue(empirical_lock_authorized(ROOT, "FTEP-V1-002"))
        self.assertTrue(manifest_empirical_lock_authorized(ROOT, "FTEP-V1-002"))

    def test_prospective_lock_dry_run_cli_json_closed_market(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reset_local_state_for_tests()
        try:
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.campaign_status.is_within_us_equity_rth",
                return_value=False,
            ):
                payload = collect_ftep_prospective_lock_gates(ROOT, "FTEP-V1-002")
        finally:
            reset_local_state_for_tests()
            os.environ.pop("IMP_STATE_DIR", None)
            os.environ.pop("IMP_PERSIST_STATE", None)
            tmp.cleanup()
        self.assertEqual(payload["artifact_kind"], "ftep_prospective_lock_gate")
        self.assertFalse(payload["would_record_lock"])
        self.assertIn("US_EQUITY_RTH_CLOSED", payload["blockers"])
        self.assertNotIn("EMPIRICAL_LOCK_NOT_AUTHORIZED", payload["blockers"])
        self.assertIn("NO_GOVERNED_SESSION", payload["blockers"])
        self.assertNotIn("forward_test_invoke_steps", payload)

    def test_fixture_qualifying_catalyst_present_without_lock(self) -> None:
        payload = collect_ftep_prospective_lock_gates(
            ROOT,
            "FTEP-V1-002",
            fixture_only=True,
        )
        self.assertFalse(payload["would_record_lock"])
        qualifying = payload.get("qualifying_catalyst")
        self.assertIsNotNone(qualifying)
        self.assertEqual(str(qualifying.get("instrument_id")), "NVDA")


if __name__ == "__main__":
    unittest.main()
