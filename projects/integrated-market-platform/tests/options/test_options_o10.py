"""Tests for Options O10 delta-hedged research primitive."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.delta_hedged import (  # noqa: E402
    compute_delta_hedged_period_return,
    delta_hedged_research_snapshot,
    simulate_delta_hedged_path,
)
from market_platform_foundation.options.r_o6 import (  # noqa: E402
    compose_r_o6_research_snapshot,
    evaluate_r_o6_correlation,
)


class OptionsO10Tests(unittest.TestCase):
    def test_period_return_isolated_from_pure_direction_when_delta_hedged(self) -> None:
        """Flat option marks with spot move should net near zero when perfectly hedged."""
        result = compute_delta_hedged_period_return(
            option_value_start=5.0,
            option_value_end=5.0,
            spot_start=100.0,
            spot_end=105.0,
            delta_at_start=0.5,
        )
        self.assertTrue(result.get("available"))
        self.assertAlmostEqual(result["delta_hedged_pnl"], -2.5, places=4)
        self.assertTrue(result.get("not_trade_signal"))

    def test_period_return_fail_closed_on_invalid_spot(self) -> None:
        result = compute_delta_hedged_period_return(
            option_value_start=5.0,
            option_value_end=5.5,
            spot_start=0.0,
            spot_end=100.0,
            delta_at_start=0.5,
        )
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "INVALID_SPOT")

    def test_simulate_path_produces_cumulative_return(self) -> None:
        spot_path = [100.0, 101.0, 99.5, 100.5]
        result = simulate_delta_hedged_path(
            spot_path,
            strike=100.0,
            rate=0.05,
            volatility=0.30,
            call_put="call",
            maturity_days_start=30,
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result["period_count"], 3)
        self.assertIn("cumulative_delta_hedged_pnl", result)
        self.assertTrue(result.get("research_only"))

    def test_research_snapshot_fail_closed_without_q_vol(self) -> None:
        physical = {"vol_forecast_annualized": 0.25}
        result = delta_hedged_research_snapshot(
            physical,
            {"available": False},
            spot_path=[100.0, 101.0],
            strike=100.0,
        )
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "IMPLIED_VOL_UNAVAILABLE")

    def test_research_snapshot_composes_from_p_and_q(self) -> None:
        physical = {
            "vol_forecast_annualized": 0.28,
            "confidence": "MEDIUM",
        }
        q = {
            "available": True,
            "vol_implied_annualized": 0.33,
            "confidence": "LOW",
        }
        result = delta_hedged_research_snapshot(
            physical,
            q,
            spot_path=[100.0, 101.0, 100.0, 102.0],
            strike=100.0,
            maturity_days=30,
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("target_id"), "T-DH")
        self.assertEqual(result.get("gate_milestone"), "R-O6")
        self.assertAlmostEqual(result.get("vrp_context"), 0.05, places=4)

    def test_compose_r_o6_research_snapshot_unifies_edge_and_delta_hedged(self) -> None:
        physical = {
            "vol_forecast_annualized": 0.28,
            "confidence": "MEDIUM",
            "horizons": [
                {
                    "mean_return": 0.01,
                    "variance": 0.02,
                    "upside_tail_probability": 0.05,
                    "downside_tail_probability": 0.05,
                    "skew": 0.0,
                }
            ],
        }
        q = {
            "available": True,
            "vol_implied_annualized": 0.33,
            "confidence": "LOW",
            "horizons": [
                {
                    "mean_return": 0.005,
                    "variance": 0.025,
                    "upside_tail_probability": 0.04,
                    "downside_tail_probability": 0.06,
                    "skew": 0.0,
                }
            ],
        }
        result = compose_r_o6_research_snapshot(
            physical,
            q,
            spot_path=[100.0, 101.0, 100.0, 102.0],
            strike=100.0,
            maturity_days=30,
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("gate_milestone"), "R-O6")
        self.assertIn("p_vs_q_edge", result)
        self.assertIn("delta_hedged", result)
        self.assertTrue(result.get("not_trade_signal"))

    def test_compose_r_o6_fail_closed_when_q_missing(self) -> None:
        result = compose_r_o6_research_snapshot(
            {"vol_forecast_annualized": 0.25},
            None,
            spot_path=[100.0, 101.0],
            strike=100.0,
        )
        self.assertFalse(result.get("available"))

    def test_evaluate_r_o6_correlation_passes_on_positive_panel(self) -> None:
        import json
        from pathlib import Path

        fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "providers"
            / "options"
            / "nvda_r_o6_panel_slice.json"
        )
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        result = evaluate_r_o6_correlation(payload["panel_rows"])
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("gate_status"), "PASS")
        self.assertGreater(result.get("spearman", 0.0), 0.0)

    def test_evaluate_r_o6_correlation_insufficient_sample(self) -> None:
        result = evaluate_r_o6_correlation(
            [{"volatility_edge": 0.01, "cumulative_delta_hedged_return_pct": 0.01}]
        )
        self.assertEqual(result.get("gate_status"), "INSUFFICIENT_SAMPLE")


if __name__ == "__main__":
    unittest.main()
