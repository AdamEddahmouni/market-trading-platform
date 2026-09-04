"""Tests for Options O4 VRP research module."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import estimate_vrp, vrp_research_snapshot  # noqa: E402


class OptionsVRPTests(unittest.TestCase):
    def test_vrp_positive_when_iv_exceeds_rv(self) -> None:
        result = estimate_vrp(0.35, 0.30)
        self.assertTrue(result.get("available"))
        self.assertGreater(result["vrp"], 0)
        self.assertTrue(result.get("iv_not_unbiased_rv_forecast"))
        self.assertTrue(result.get("not_trade_signal"))

    def test_vrp_snapshot_fail_closed_without_vol(self) -> None:
        physical = {"confidence": "LOW"}
        q = {"available": True, "confidence": "LOW"}
        result = vrp_research_snapshot(physical, q)
        self.assertFalse(result.get("available"))

    def test_vrp_snapshot_from_forecasts(self) -> None:
        physical = {
            "confidence": "MEDIUM",
            "vol_forecast_annualized": 0.28,
            "methodology_tags": ["ewma"],
        }
        q = {
            "available": True,
            "confidence": "LOW",
            "vol_implied_annualized": 0.33,
            "horizons": [{"horizon_days": 30}],
        }
        result = vrp_research_snapshot(physical, q)
        self.assertTrue(result.get("available"))
        self.assertAlmostEqual(result["vrp"], 0.05, places=4)


if __name__ == "__main__":
    unittest.main()
