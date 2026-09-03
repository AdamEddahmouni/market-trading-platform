"""Tests for Options O3 risk-neutral Q inference."""

from __future__ import annotations

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


class OptionsO3Tests(unittest.TestCase):
    def test_bad_surface_qa_blocks_q(self) -> None:
        surface = {"points": [], "point_count": 0, "surface_version": "sigma_kt_v1"}
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
            },
            {
                "bid": 2.10,
                "ask": 2.15,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 135.0,
                "underlying_price": 132.0,
            },
        ]
        surface = build_volatility_surface(activities)
        result = infer_risk_neutral_distribution(
            surface,
            symbol="BIYA",
            as_of_time="2026-07-21T19:45:00.000000000Z",
        )
        self.assertTrue(result.get("available"))
        self.assertIn("replay_hash", result)
        horizons = result.get("horizons", [])
        self.assertTrue(horizons)
        self.assertIn("upside_tail_probability", horizons[0])


if __name__ == "__main__":
    unittest.main()
