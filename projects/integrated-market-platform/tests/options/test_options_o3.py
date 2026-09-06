"""Tests for Options O3 risk-neutral Q inference."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import (  # noqa: E402
    build_volatility_surface,
    evaluate_surface_qa,
    infer_risk_neutral_distribution,
)
from market_platform_foundation.options import risk_neutral as options_q  # noqa: E402


class OptionsO3Tests(unittest.TestCase):
    def test_bad_surface_qa_blocks_q(self) -> None:
        surface = {"points": [], "point_count": 0, "surface_version": "sigma_kt_v3"}
        qa = evaluate_surface_qa(surface, min_points=2)
        self.assertTrue(qa["blocked"])
        result = infer_risk_neutral_distribution(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "SURFACE_QA_BLOCKED")

    def test_clean_fixture_surface_produces_q(self) -> None:
        activities = [
            {
                "bid": 1.80,
                "ask": 1.85,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 130.0,
                "underlying_price": 132.0,
                "rate": 0.04,
            },
            {
                "bid": 2.10,
                "ask": 2.15,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 135.0,
                "underlying_price": 132.0,
                "rate": 0.04,
            },
        ]
        surface = build_volatility_surface(activities)
        result = infer_risk_neutral_distribution(
            surface,
            symbol="BIYA",
            as_of_time="2026-07-21T19:45:00.000000000Z",
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("model_version"), "risk_neutral_log_normal_moment_approx_v1")
        self.assertIn("log_normal_moment_approximation", result.get("methodology_tags", []))
        self.assertIn("replay_hash", result)
        horizons = result.get("horizons", [])
        self.assertTrue(horizons)
        self.assertIn("upside_tail_probability", horizons[0])
        self.assertEqual(surface["surface_version"], "sigma_kt_v3")
        self.assertEqual(surface["points"][0]["underlying_price"], 132.0)
        self.assertEqual(surface["points"][0]["rate"], 0.04)

    def test_unstamped_surface_without_spot_fails_closed(self) -> None:
        surface = {
            "point_count": 2,
            "surface_version": "sigma_kt_v3",
            "points": [
                {
                    "strike": 130.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.30,
                },
                {
                    "strike": 135.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.32,
                },
            ],
        }
        result = infer_risk_neutral_distribution(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "UNDERLYING_PRICE_UNKNOWN")

    def test_stamped_spot_without_rate_fails_closed(self) -> None:
        surface = {
            "point_count": 2,
            "surface_version": "sigma_kt_v3",
            "points": [
                {
                    "strike": 130.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.30,
                    "underlying_price": 132.0,
                },
                {
                    "strike": 135.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.32,
                    "underlying_price": 132.0,
                },
            ],
        }
        result = infer_risk_neutral_distribution(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), "RATE_ASSUMPTION_MISSING")

    def test_explicit_rate_kwarg_enables_q(self) -> None:
        surface = {
            "point_count": 2,
            "surface_version": "sigma_kt_v3",
            "points": [
                {
                    "strike": 130.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.30,
                    "underlying_price": 132.0,
                },
                {
                    "strike": 135.0,
                    "expiration": "2026-08-15",
                    "dte": 25,
                    "call_put": "call",
                    "sigma": 0.32,
                    "underlying_price": 132.0,
                },
            ],
        }
        result = infer_risk_neutral_distribution(surface, rate=0.04)
        self.assertTrue(result.get("available"))
        self.assertFalse(hasattr(options_q, "DEFAULT_RATE"))
        self.assertEqual(options_q.RATE_ASSUMPTION_MISSING, "RATE_ASSUMPTION_MISSING")
        self.assertIsNone(
            inspect.signature(infer_risk_neutral_distribution).parameters["rate"].default
        )
        source = Path(options_q.__file__).read_text(encoding="utf-8")
        self.assertNotIn("rate: float = 0.05", source)


if __name__ == "__main__":
    unittest.main()
