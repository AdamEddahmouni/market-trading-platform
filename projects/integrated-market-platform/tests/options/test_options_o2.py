"""Tests for Options O2 IV, Greeks, and surface."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options import (  # noqa: E402
    bsm_greeks,
    build_surface_point,
    build_volatility_surface,
    dual_track_iv,
    evaluate_surface_qa,
    implied_volatility,
    select_atm_contracts,
    estimate_contract_dealer_greeks,
    estimate_implied_event_move,
)
from market_platform_foundation.options import dealer as options_dealer  # noqa: E402
from market_platform_foundation.options import surface as options_surface  # noqa: E402
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
                "rate": 0.04,
            }
        ]
        surface = build_volatility_surface(activities)
        qa = evaluate_surface_qa(surface, min_points=1)
        self.assertGreater(surface["point_count"], 0)
        self.assertEqual(surface["surface_version"], "sigma_kt_v3")
        self.assertEqual(surface["points"][0]["underlying_price"], 132.0)
        self.assertEqual(surface["points"][0]["rate"], 0.04)
        self.assertIn("internal_iv", surface["points"][0])
        self.assertIn("blocked", qa)

    def test_quote_and_strike_without_underlying_skips_point(self) -> None:
        surface = build_volatility_surface(
            [
                {
                    "bid": 1.80,
                    "ask": 1.85,
                    "event_time": "2026-07-21T19:45:00.000000000Z",
                    "expiry": "2026-08-15",
                    "option_type": "call",
                    "strike": 130.0,
                }
            ]
        )
        self.assertEqual(surface["point_count"], 0)
        self.assertEqual(surface["surface_version"], "sigma_kt_v3")

    def test_quote_and_spot_without_rate_skips_point(self) -> None:
        surface = build_volatility_surface(
            [
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
        )
        self.assertEqual(surface["point_count"], 0)
        self.assertEqual(surface["surface_version"], "sigma_kt_v3")

    def test_explicit_rate_kwarg_stamps_surface_point(self) -> None:
        point = build_surface_point(
            {
                "bid": 1.80,
                "ask": 1.85,
                "event_time": "2026-07-21T19:45:00.000000000Z",
                "expiry": "2026-08-15",
                "option_type": "call",
                "strike": 130.0,
                "underlying_price": 132.0,
            },
            rate=0.04,
        )
        self.assertIsNotNone(point)
        assert point is not None
        self.assertEqual(point["rate"], 0.04)

    def test_surface_module_has_no_strike_multiple_fallback(self) -> None:
        source = Path(options_surface.__file__).read_text(encoding="utf-8")
        self.assertNotIn("1.02", source)
        self.assertNotIn("0.98", source)
        self.assertFalse(hasattr(options_surface, "DEFAULT_RATE"))
        self.assertIsNone(inspect.signature(build_volatility_surface).parameters["rate"].default)
        self.assertIsNone(inspect.signature(build_surface_point).parameters["rate"].default)
        self.assertNotIn("rate: float = 0.05", source)

    def test_dealer_fails_closed_without_underlying(self) -> None:
        result = estimate_contract_dealer_greeks(
            {
                "option_type": "call",
                "strike": 4.0,
                "expiry": "2026-08-15",
                "event_time": "2026-07-21T20:30:00.000000000Z",
                "bid": 0.35,
                "ask": 0.38,
                "open_interest": 100,
            }
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "UNDERLYING_PRICE_ASSUMPTION_MISSING")
        self.assertFalse(hasattr(options_dealer, "DEFAULT_RATE"))
        self.assertEqual(options_dealer.DEALER_VERSION, "options_dealer_proxy_v2")
        self.assertIsNone(
            inspect.signature(estimate_contract_dealer_greeks).parameters["rate"].default
        )

    def test_strategy_spot_unavailable_without_underlying(self) -> None:
        result = select_atm_contracts(
            [
                {
                    "option_type": "call",
                    "strike": 130.0,
                    "expiry": "2026-08-15",
                    "bid": 1.80,
                    "ask": 1.85,
                    "open_interest": 500,
                },
                {
                    "option_type": "put",
                    "strike": 130.0,
                    "expiry": "2026-08-15",
                    "bid": 1.70,
                    "ask": 1.75,
                    "open_interest": 400,
                },
            ]
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "SPOT_UNAVAILABLE")

    def test_event_vol_fails_closed_without_underlying(self) -> None:
        result = estimate_implied_event_move(
            [
                {
                    "option_type": "call",
                    "strike": 128.0,
                    "expiry": "2026-08-22",
                    "bid": 8.40,
                    "ask": 8.50,
                    "event_time": "2026-08-19T20:30:00.000000000Z",
                },
                {
                    "option_type": "put",
                    "strike": 128.0,
                    "expiry": "2026-08-22",
                    "bid": 7.80,
                    "ask": 7.90,
                    "event_time": "2026-08-19T20:30:00.000000000Z",
                },
            ],
            event_expiry="2026-08-22",
        )
        self.assertFalse(result["available"])

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
