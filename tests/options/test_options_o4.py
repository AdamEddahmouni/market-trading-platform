"""Tests for Options O4 P vs Q edge decomposition."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import compare_physical_vs_risk_neutral  # noqa: E402


class OptionsO4Tests(unittest.TestCase):
    def test_edge_unavailable_without_p(self) -> None:
        q = {
            "available": True,
            "horizons": [{"mean_return": 0.01, "variance": 0.02, "upside_tail_probability": 0.05}],
        }
        result = compare_physical_vs_risk_neutral(None, q)
        self.assertFalse(result.get("available"))

    def test_edge_decomposition_no_universal_score(self) -> None:
        physical = {
            "confidence": "MEDIUM",
            "vol_forecast_annualized": 0.30,
            "horizons": [
                {
                    "mean_return": 0.02,
                    "variance": 0.04,
                    "upside_tail_probability": 0.10,
                    "downside_tail_probability": 0.06,
                    "skew": 0.1,
                }
            ],
        }
        risk_neutral = {
            "available": True,
            "confidence": "LOW",
            "vol_implied_annualized": 0.35,
            "horizons": [
                {
                    "mean_return": 0.01,
                    "variance": 0.05,
                    "upside_tail_probability": 0.07,
                    "downside_tail_probability": 0.08,
                    "skew": 0.0,
                }
            ],
        }
        result = compare_physical_vs_risk_neutral(physical, risk_neutral)
        self.assertTrue(result.get("available"))
        self.assertNotIn("universal_score", result)
        components = result.get("components", {})
        self.assertIn("directional_edge", components)
        self.assertIn("volatility_edge", components)
        self.assertIn("replay_hash", result)


if __name__ == "__main__":
    unittest.main()
