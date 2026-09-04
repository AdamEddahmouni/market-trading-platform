"""Tests for Options O4 P vs Q edge decomposition."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import (  # noqa: E402
    apply_executable_edge,
    compare_physical_vs_risk_neutral,
    estimate_execution_friction,
)


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

    def test_executable_unavailable_without_bid_ask(self) -> None:
        activities = [{"volume": 100, "option_type": "call"}]
        friction = estimate_execution_friction(activities)
        self.assertFalse(friction.get("executable_available"))
        theoretical = {
            "available": True,
            "components": {"directional_edge": 0.01, "volatility_edge": 0.05},
        }
        executable = apply_executable_edge(theoretical, friction)
        self.assertFalse(executable.get("executable_available"))

    def test_nvda_fixture_friction_reduces_edge(self) -> None:
        activities = [
            {"bid": 1.80, "ask": 1.85},
            {"bid": 2.05, "ask": 2.10},
        ]
        friction = estimate_execution_friction(activities)
        self.assertTrue(friction.get("executable_available"))
        theoretical = {
            "available": True,
            "components": {
                "directional_edge": 0.02,
                "volatility_edge": 0.05,
                "skew_edge": 0.1,
                "tail_edge": 0.03,
            },
        }
        executable = apply_executable_edge(theoretical, friction)
        self.assertTrue(executable.get("executable_available"))
        self.assertNotIn("universal_score", executable)
        self.assertNotIn("total_edge", executable)
        exec_components = executable["executable_edge"]["components"]
        self.assertLess(
            exec_components["net_volatility_edge"],
            theoretical["components"]["volatility_edge"],
        )


if __name__ == "__main__":
    unittest.main()
