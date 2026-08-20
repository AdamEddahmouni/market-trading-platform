"""Tests for O10 surface baseline research milestones."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import build_volatility_surface  # noqa: E402
from market_platform_foundation.options.research.surface_baseline import (  # noqa: E402
    GATE_MILESTONE,
    evaluate_surface_baseline_oos,
    forecast_surface_baseline,
    surface_baseline_spec,
)


class OptionsO10SurfaceBaselineTests(unittest.TestCase):
    def _sample_surface(self) -> dict:
        activities = [
            {
                "bid": 1.80,
                "ask": 1.85,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 130.0,
                "underlying_price": 128.0,
            },
            {
                "bid": 3.10,
                "ask": 3.15,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "put",
                "strike": 130.0,
                "underlying_price": 128.0,
            },
        ]
        return build_volatility_surface(activities)

    def test_surface_baseline_spec_has_model_identity(self) -> None:
        spec = surface_baseline_spec("parametric_skew_v1")
        self.assertEqual(spec["model_family"], "options_surface_baseline_v1")
        self.assertIn("model_spec_hash", spec)

    def test_forecast_surface_baseline_from_o2_surface(self) -> None:
        result = forecast_surface_baseline(self._sample_surface(), method="spline_valid_quotes_v1")
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("gate_milestone"), GATE_MILESTONE)
        self.assertTrue(result.get("not_trade_signal"))
        self.assertIn("forecast_atm_iv_delta", result)

    def test_forecast_fail_closed_on_empty_surface(self) -> None:
        result = forecast_surface_baseline({"point_count": 0, "points": []})
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "SURFACE_EMPTY")

    def test_evaluate_surface_baseline_oos_mae(self) -> None:
        predictions = [
            {
                "forecast_atm_iv_delta": 0.01,
                "forecast_skew_delta": 0.002,
                "forecast_term_slope_delta": 0.001,
            },
            {
                "forecast_atm_iv_delta": 0.02,
                "forecast_skew_delta": 0.004,
                "forecast_term_slope_delta": 0.002,
            },
        ]
        realized = [
            {
                "realized_atm_iv_delta": 0.015,
                "realized_skew_delta": 0.003,
                "realized_term_slope_delta": 0.0015,
            },
            {
                "realized_atm_iv_delta": 0.025,
                "realized_skew_delta": 0.005,
                "realized_term_slope_delta": 0.0025,
            },
        ]
        result = evaluate_surface_baseline_oos(predictions, realized)
        self.assertTrue(result.get("available"))
        self.assertEqual(result["target_metrics"]["T-IV"]["sample_size"], 2)


if __name__ == "__main__":
    unittest.main()
