"""Tests for catalyst lane acceptance tooling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.donor_bridge import internship_client  # noqa: E402
from tools.integration.catalyst_lane_acceptance import run_acceptance  # noqa: E402


class CatalystLaneAcceptanceToolTests(unittest.TestCase):
    def test_offline_fail_closed_projection(self) -> None:
        result = run_acceptance(imp_url="http://127.0.0.1:59998")
        fail_closed = next(check for check in result.checks if check.check_id == "projection_fail_closed")
        self.assertTrue(fail_closed.passed)
        fixture_fallback = next(
            check for check in result.checks if check.check_id == "projection_workspace_fixture_fallback"
        )
        self.assertTrue(fixture_fallback.passed)

    def test_live_projection_when_state_seeded(self) -> None:
        state_dir = internship_client.default_state_dir()
        if not internship_client.is_available(state_dir=state_dir):
            self.skipTest("internship demo state not seeded")
        result = run_acceptance(imp_url="http://127.0.0.1:59998", state_dir=state_dir)
        passed_ids = {check.check_id for check in result.checks if check.passed}
        self.assertIn("projection_explore_rows", passed_ids)
        self.assertIn("projection_reference_symbol", passed_ids)
        self.assertIn("projection_attention_items", passed_ids)


if __name__ == "__main__":
    unittest.main()
