"""Unit tests for 0DTE feature modules (GEX, max pain, liquidity, flow, TOD)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.data_models import ContractRow, Snapshot
from options_engine.features import compute_features
from options_engine.features_flow_trend import compute_flow_trend_features
from options_engine.features_gex import black_scholes_gamma, compute_gex_features, gex_regime_label
from options_engine.features_liquidity import compute_liquidity_features, evaluate_contract_liquidity
from options_engine.features_max_pain import compute_max_pain_features, compute_max_pain_strike
from options_engine.features_regime import compute_regime_features
from options_engine.features_tod import compute_tod_features, estimate_remaining_theta_fraction
from options_engine.scoring import score_options


def _settings(**odte_overrides) -> dict:
    base = {
        "features": {"atm_strike_band_pct": 0.05},
        "odte_signals": {
            "gex": {"enabled": True, "positive_pin_pull": 0.35, "negative_trend_boost": 0.15},
            "max_pain": {"enabled": True},
            "flow_trend": {"enabled": True, "lookback_minutes": 30, "slope_gain": 200},
            "liquidity": {"enabled": True, "max_spread_pct_of_mid": 0.08, "min_oi": 50},
            "iv_rank": {"enabled": True, "weight": 5},
            "time_of_day": {"enabled": True, "raise_bar_after_et": "13:30", "late_confidence_mult": 1.25},
            "regime": {"enabled": True, "vix_risk_off": 25},
        },
        "scoring": {
            "weights": {
                "call_volume_share": 8,
                "net_delta_oi": 10,
                "iv_skew": 7,
                "put_call_oi_ratio": 8,
                "put_call_volume_ratio": 8,
                "max_pain_distance": 18,
                "flow_trend": 16,
                "iv_rank_penalty": 5,
            },
            "bullish_threshold": 60,
            "bearish_threshold": 40,
            "min_data_quality_score": 0.6,
            "min_directional_signals": 2,
        },
        "_regime_seed": {"vix": 18.0, "spy_pct": 0.2, "qqq_pct": 0.3},
    }
    for key, val in odte_overrides.items():
        base["odte_signals"][key] = {**base["odte_signals"].get(key, {}), **val}
    return base


class GexTests(unittest.TestCase):
    def test_bs_gamma_atm_positive(self) -> None:
        g = black_scholes_gamma(100.0, 100.0, 1 / 365, 0.3)
        self.assertGreater(g, 0.0)

    def test_gex_available_with_iv(self) -> None:
        # Heavy call OI near spot → dealers short calls → negative dealer GEX.
        snap = Snapshot(
            ticker="TEST",
            as_of="2026-07-16T15:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 100, "2026-07-16", 0.35, 100, 5000, 1.0, 1.1, 1.05, True, delta=0.5),
                ContractRow("P1", "put", 100, "2026-07-16", 0.35, 50, 500, 1.0, 1.1, 1.05, True, delta=-0.5),
            ],
        )
        out = compute_gex_features(snap, _settings())
        self.assertEqual(out["gex_available"], 1.0)
        self.assertLess(out["gex_near_spot"], 0.0)
        self.assertEqual(gex_regime_label(out["gex_regime_code"]), "negative")


class MaxPainTests(unittest.TestCase):
    def test_max_pain_between_strikes(self) -> None:
        contracts = [
            ContractRow("C90", "call", 90, "2026-07-16", 0.3, 10, 100, 1, 1.1, 1, False),
            ContractRow("C100", "call", 100, "2026-07-16", 0.3, 10, 200, 1, 1.1, 1, False),
            ContractRow("C110", "call", 110, "2026-07-16", 0.3, 10, 50, 1, 1.1, 1, False),
            ContractRow("P90", "put", 90, "2026-07-16", 0.3, 10, 50, 1, 1.1, 1, False),
            ContractRow("P100", "put", 100, "2026-07-16", 0.3, 10, 200, 1, 1.1, 1, False),
            ContractRow("P110", "put", 110, "2026-07-16", 0.3, 10, 100, 1, 1.1, 1, False),
        ]
        strike, pain = compute_max_pain_strike(contracts)
        self.assertIn(strike, {90.0, 100.0, 110.0})
        self.assertGreaterEqual(pain, 0.0)

    def test_max_pain_features_distance(self) -> None:
        snap = Snapshot(
            ticker="TEST",
            as_of="2026-07-16T15:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C100", "call", 100, "2026-07-16", 0.3, 10, 300, 1, 1.1, 1, False),
                ContractRow("P100", "put", 100, "2026-07-16", 0.3, 10, 300, 1, 1.1, 1, False),
                ContractRow("C105", "call", 105, "2026-07-16", 0.3, 10, 50, 1, 1.1, 1, False),
                ContractRow("P95", "put", 95, "2026-07-16", 0.3, 10, 50, 1, 1.1, 1, False),
            ],
        )
        out = compute_max_pain_features(snap, _settings())
        self.assertEqual(out["max_pain_available"], 1.0)
        self.assertAlmostEqual(out["max_pain_strike"], 100.0)


class LiquidityTests(unittest.TestCase):
    def test_wide_spread_rejected(self) -> None:
        row = ContractRow("C1", "call", 100, "2026-07-16", 0.3, 10, 200, 1.0, 1.5, 1.2, False)
        ok, reason, spread = evaluate_contract_liquidity(row, max_spread_pct_of_mid=0.08, min_oi=50)
        self.assertFalse(ok)
        self.assertIn("spread", reason)
        self.assertGreater(spread, 0.08)

    def test_tight_spread_passes(self) -> None:
        row = ContractRow("C1", "call", 100, "2026-07-16", 0.3, 10, 200, 1.00, 1.04, 1.02, False)
        ok, reason, _spread = evaluate_contract_liquidity(row, max_spread_pct_of_mid=0.08, min_oi=50)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_chain_liquidity_reject_flag(self) -> None:
        snap = Snapshot(
            ticker="TEST",
            as_of="2026-07-16T15:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 100, "2026-07-16", 0.3, 10, 10, 1.0, 2.0, 1.5, False),
            ],
        )
        out = compute_liquidity_features(snap, _settings(liquidity={"min_oi": 100, "max_spread_pct_of_mid": 0.05}))
        self.assertEqual(out["liquidity_reject"], 1.0)
        self.assertEqual(out["liquidity_reject_primary"], "oi_below_min")
        self.assertIn("OI", out["liquidity_reject_detail"])
        self.assertGreaterEqual(int(out["liquidity_fail_counts"].get("oi_below_min", 0)), 1)

    def test_no_listed_chain_subreason(self) -> None:
        snap = Snapshot(
            ticker="TEST",
            as_of="2026-07-16T15:00:00+00:00",
            spot_price=100.0,
            contracts=[],
        )
        out = compute_liquidity_features(snap, _settings())
        self.assertEqual(out["liquidity_reject"], 1.0)
        self.assertEqual(out["liquidity_reject_primary"], "no_listed_chain")


class FlowTrendTests(unittest.TestCase):
    def test_rising_call_share_bullish(self) -> None:
        history = [
            {
                "as_of": "2026-07-16T14:00:00+00:00",
                "feature_cache": {"call_volume_share": 0.40},
            },
            {
                "as_of": "2026-07-16T14:15:00+00:00",
                "feature_cache": {"call_volume_share": 0.50},
            },
        ]
        out = compute_flow_trend_features(
            call_volume_share=0.60,
            put_call_volume_ratio=0.7,
            as_of="2026-07-16T14:30:00+00:00",
            history=history,
            settings=_settings(),
        )
        self.assertEqual(out["flow_trend_available"], 1.0)
        self.assertGreater(out["call_share_slope_per_min"], 0.0)
        self.assertGreater(out["flow_trend_score"], 0.5)


class TodAndRegimeTests(unittest.TestCase):
    def test_theta_declines_through_day(self) -> None:
        from datetime import time

        morning = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc).astimezone()
        # Use ET-aware helper via estimate with explicit times
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        am = datetime(2026, 7, 16, 10, 0, tzinfo=et)
        pm = datetime(2026, 7, 16, 15, 0, tzinfo=et)
        left_am = estimate_remaining_theta_fraction(am, time(15, 45))
        left_pm = estimate_remaining_theta_fraction(pm, time(15, 45))
        self.assertGreater(left_am, left_pm)

    def test_regime_risk_off_on_high_vix(self) -> None:
        out = compute_regime_features(_settings(), vix=30.0, spy_pct=-0.2, qqq_pct=-0.1)
        self.assertEqual(out["regime_available"], 1.0)
        self.assertEqual(out["regime_risk_off"], 1.0)
        self.assertLess(out["regime_trust_multiplier"], 1.0)

    def test_tod_late_multiplier(self) -> None:
        out = compute_tod_features(_settings(), as_of="2026-07-16T18:00:00+00:00")  # 14:00 ET
        self.assertEqual(out["tod_available"], 1.0)
        self.assertEqual(out["tod_is_late"], 1.0)
        self.assertGreater(out["tod_confidence_multiplier"], 1.0)


class IntegrationFeatureAndScoreTests(unittest.TestCase):
    def test_compute_features_includes_odte_keys(self) -> None:
        snap = Snapshot(
            ticker="TEST",
            as_of="2026-07-16T15:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 100, "2026-07-16", 0.3, 100, 200, 1.0, 1.05, 1.02, True, delta=0.5),
                ContractRow("P1", "put", 100, "2026-07-16", 0.32, 80, 250, 1.0, 1.05, 1.02, True, delta=-0.5),
            ],
        )
        out = compute_features(snap, [], _settings())
        for key in (
            "gex_available",
            "max_pain_strike",
            "liquidity_ok",
            "flow_trend_score",
            "tod_confidence_multiplier",
            "regime_trust_multiplier",
            "iv_rank_penalty",
        ):
            self.assertIn(key, out)

    def test_gex_modulation_pins_extreme_score(self) -> None:
        # Bullish flow + positive GEX should be pulled toward 50 vs no-GEX baseline.
        feats_base = {
            "put_call_volume_ratio": 0.5,
            "call_volume_share": 0.75,
            "put_call_oi_ratio": 0.6,
            "net_delta_oi": 0.3,
            "iv_skew": -0.03,
            "greeks_available": 1.0,
            "iv_skew_available": 1.0,
            "volume_available": 1.0,
            "oi_available": 1.0,
            "atm_iv": 0.3,
            "iv_rank": 0.4,
            "max_pain_distance_pct": 0.0,
            "max_pain_available": 1.0,
            "flow_trend_score": 0.7,
            "flow_trend_available": 1.0,
            "gex_regime_code": 0.0,
            "gex_available": 0.0,
            "liquidity_ok": 1.0,
            "liquidity_reject": 0.0,
        }
        settings = _settings()
        bull = score_options("T", feats_base, [], settings)
        pinned = dict(feats_base)
        pinned["gex_available"] = 1.0
        pinned["gex_regime_code"] = 1.0
        pinned_score = score_options("T", pinned, [], settings)
        self.assertGreater(float(bull["options_score"]), 55.0)
        self.assertLess(float(pinned_score["options_score"]), float(bull["options_score"]))


if __name__ == "__main__":
    unittest.main()
