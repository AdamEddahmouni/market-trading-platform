"""Tests for futures lane acceptance tooling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tools.integration.futures_lane_acceptance import run_acceptance  # noqa: E402


class FuturesLaneAcceptanceToolTests(unittest.TestCase):
    def test_offline_fail_closed_projection(self) -> None:
        result = run_acceptance(
            donor_url="http://127.0.0.1:59999",
            imp_url="http://127.0.0.1:59998",
        )
        fail_closed = next(check for check in result.checks if check.check_id == "projection_fail_closed")
        self.assertTrue(fail_closed.passed)
        fixture_fallback = next(
            check for check in result.checks if check.check_id == "projection_workspace_fixture_fallback"
        )
        self.assertTrue(fixture_fallback.passed)

    def test_live_projection_when_donor_up(self) -> None:
        result = run_acceptance(donor_url="http://127.0.0.1:8788", imp_url="http://127.0.0.1:59998")
        if not result.summary.get("donor_live"):
            self.skipTest("FuturesX bridge not running on :8788")
        passed_ids = {check.check_id for check in result.checks if check.passed}
        self.assertIn("projection_explore_live", passed_ids)
        self.assertIn("projection_workspace_donor_overlay", passed_ids)


if __name__ == "__main__":
    unittest.main()
