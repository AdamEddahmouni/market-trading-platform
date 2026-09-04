"""Tests for Options O2 IV, Greeks, and surface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import (  # noqa: E402
    bsm_greeks,
    build_volatility_surface,
    dual_track_iv,
    evaluate_surface_qa,
    implied_volatility,
)
from market_platform_foundation.providers.adapters.fixture_option_chain import (  # noqa: E402
    FixtureOptionChainProvider,
)


class OptionsO2Tests(unittest.TestCase):
    def test_implied_volatility_solver(self) -> None:
        iv = implied_volatility(
            market_price=5.0,
            spot=100.0,
            strike=100.0,
            time_years=0.5,
            rate=0.05,
            call_put="call",
        )
        self.assertIsNotNone(iv)
        assert iv is not None
        self.assertGreater(iv, 0.0)

    def test_greeks_reproducible(self) -> None:
        greeks = bsm_greeks(100.0, 100.0, 0.5, 0.05, 0.25, "call")
        self.assertIsNotNone(greeks["delta"])
        self.assertEqual(greeks["version"], "bsm_greeks_v1")

    def test_surface_from_fixture_chain(self) -> None:
        provider = FixtureOptionChainProvider()
        result = provider.fetch_chain("NVDA")
        self.assertEqual(result.status, "available")
        activities = [
            {
                "bid": 1.80,
                "ask": 1.85,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 130.0,
                "underlying_price": 132.0,
            }
        ]
        surface = build_volatility_surface(activities)
        qa = evaluate_surface_qa(surface, min_points=1)
        self.assertGreater(surface["point_count"], 0)
        self.assertIn("blocked", qa)

    def test_dual_track_iv(self) -> None:
        track = dual_track_iv(
            market_price=2.0,
            spot=100.0,
            strike=100.0,
            time_years=0.25,
            rate=0.05,
            call_put="call",
            provider_iv=0.22,
        )
        self.assertFalse(track["iv_invalid"])


if __name__ == "__main__":
    unittest.main()
