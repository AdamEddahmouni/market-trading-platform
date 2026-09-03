"""Tests for 0DTE decision fusion, news decay, risk, and screener scoring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import decide_trade_action
from agent.news_decay import apply_news_decay, decay_multiplier
from agent.odte_decision import apply_odte_decision_policy, detect_conflicts, extract_independent_signals
from agent.risk_manager import check_new_trade_allowed, correlation_bucket, fixed_fractional_contracts
from screener.odte_screener import score_setup_quality


class NewsDecayTests(unittest.TestCase):
    def test_half_life(self) -> None:
        self.assertAlmostEqual(decay_multiplier(45.0, half_life_minutes=45.0), 0.5, places=3)

    def test_apply_decay(self) -> None:
        out = apply_news_decay(
            0.8,
            published_at="2026-07-16T12:00:00+00:00",
            settings={"news_decay": {"enabled": True, "half_life_minutes": 45}},
            now=__import__("datetime").datetime(2026, 7, 16, 13, 30, tzinfo=__import__("datetime").timezone.utc),
        )
        self.assertLess(out["decayed_score"], out["raw_score"])
        self.assertAlmostEqual(out["age_minutes"], 90.0)


class OdteDecisionTests(unittest.TestCase):
    def test_conflict_news_vs_options(self) -> None:
        signals = extract_independent_signals(
            decayed_news_score=0.8,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="bearish",
            options_score=30.0,
            feature_values={},
        )
        conflict, reasons = detect_conflicts(signals, min_conflict_sources=2)
        self.assertTrue(conflict)
        self.assertTrue(any("directional_conflict" in r for r in reasons))

    def test_review_resolves_when_no_conflict(self) -> None:
        decision, reason, meta = apply_odte_decision_policy(
            decision="REVIEW",
            reason="weak social",
            decayed_news_score=0.8,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="bullish",
            options_score=70.0,
            feature_values={
                "flow_trend_available": 1.0,
                "flow_trend_score": 0.7,
                "liquidity_ok": 1.0,
                "liquidity_reject": 0.0,
                "tod_confidence_multiplier": 1.0,
                "regime_trust_multiplier": 1.0,
                "iv_rank": 0.4,
            },
            setup_quality_score=70.0,
            settings={
                "execution": {
                    "review_only_on_conflict": True,
                    "min_confidence_for_action": 40,
                    "force_review_all": False,
                    "require_options_bias_to_autoresolve": True,
                },
                "odte_screener": {"min_setup_score": 0},
            },
            data_quality=0.9,
            signal_source="news",
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("auto-resolved", reason)
        self.assertGreaterEqual(meta["confidence_pct"], 40)

    def test_path_b_neutral_options_does_not_autoresolve(self) -> None:
        decision, _, meta = apply_odte_decision_policy(
            decision="REVIEW",
            reason="Path B",
            decayed_news_score=0.0,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="neutral",
            options_score=42.0,
            feature_values={
                "max_pain_available": 1.0,
                "max_pain_distance_pct": -0.5,
                "liquidity_ok": 1.0,
                "liquidity_reject": 0.0,
                "tod_confidence_multiplier": 1.0,
                "regime_trust_multiplier": 1.0,
                "iv_rank": 0.5,
            },
            setup_quality_score=65.0,
            settings={
                "execution": {
                    "review_only_on_conflict": True,
                    "min_confidence_for_action": 40,
                    "min_confidence_for_path_b": 65,
                    "require_options_bias_to_autoresolve": True,
                },
                "odte_screener": {"min_setup_score": 0},
            },
            data_quality=0.9,
            signal_source="expiry",
        )
        self.assertEqual(decision, "LOG")
        self.assertIn(meta.get("review_reason_code_odte"), {"options_not_clear", "low_confidence", "no_lean"})

    def test_override_buy_blocked_when_conf_below_path_b_floor(self) -> None:
        """Path B override BUY must still pass final confidence floor."""
        decision, reason, meta = apply_odte_decision_policy(
            decision="BUY",
            reason="Path B expiry BUY (score=70.0, urgency=55).",
            decayed_news_score=0.0,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="bullish",
            options_score=70.0,
            feature_values={
                "liquidity_ok": 1.0,
                "liquidity_reject": 0.0,
                "tod_confidence_multiplier": 1.0,
                "regime_trust_multiplier": 1.0,
                "iv_rank": 0.5,
            },
            setup_quality_score=66.0,
            settings={
                "execution": {
                    "review_only_on_conflict": True,
                    "min_confidence_for_action": 40,
                    "min_confidence_for_path_b": 65,
                    "require_options_bias_to_autoresolve": True,
                },
                "odte_screener": {"min_setup_score": 45},
            },
            data_quality=0.9,
            signal_source="expiry",
        )
        self.assertEqual(decision, "LOG")
        self.assertIn("actionable blocked", reason)
        self.assertEqual(meta.get("review_reason_code_odte"), "low_confidence")

    def test_liquidity_reject_equity_fallback_on_strong_catalyst(self) -> None:
        decision, reason, meta = apply_odte_decision_policy(
            decision="BUY",
            reason="ok",
            decayed_news_score=0.8,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="bullish",
            options_score=70.0,
            feature_values={
                "liquidity_reject": 1.0,
                "liquidity_ok": 0.0,
                "liquidity_reject_primary": "spread_too_wide",
                "atm_median_spread_pct": 0.15,
                "liquidity_max_spread_pct": 0.08,
                "atm_min_oi": 45.0,
                "liquidity_min_oi_required": 100.0,
            },
            setup_quality_score=80.0,
            settings={
                "trading": {"prefer_equity_on_liquidity_reject": True, "equity_fallback_min_news_score": 0.5},
                "execution": {"review_only_on_conflict": True},
                "odte_screener": {"min_setup_score": 0},
            },
        )
        self.assertEqual(decision, "REVIEW")
        self.assertEqual(meta["review_reason_code_odte"], "equity_fallback_liquidity")
        self.assertTrue(meta.get("equity_fallback_liquidity"))
        self.assertIn("equity fallback", reason)

    def test_liquidity_reject_logs_when_news_weak(self) -> None:
        decision, reason, meta = apply_odte_decision_policy(
            decision="BUY",
            reason="ok",
            decayed_news_score=0.2,
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_bias="bullish",
            options_score=70.0,
            feature_values={
                "liquidity_reject": 1.0,
                "liquidity_ok": 0.0,
                "liquidity_reject_primary": "spread_too_wide",
            },
            setup_quality_score=80.0,
            settings={
                "trading": {"prefer_equity_on_liquidity_reject": True, "equity_fallback_min_news_score": 0.5},
                "execution": {"review_only_on_conflict": True},
                "odte_screener": {"min_setup_score": 0},
            },
        )
        self.assertEqual(decision, "LOG")
        self.assertEqual(meta["review_reason_code_odte"], "liquidity_reject")
        self.assertIn("liquidity floor failed", reason)

    def test_decide_trade_action_backward_compat_without_settings(self) -> None:
        decision, _, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="WATCH",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "x"},
            news_headline="h",
            news_source="s",
            buy_threshold=0.7,
            sell_threshold=-0.7,
            require_social_signal=True,
        )
        self.assertEqual(decision, "REVIEW")
        self.assertIn("action_probs", meta)


class RiskManagerTests(unittest.TestCase):
    def test_correlation_bucket(self) -> None:
        self.assertEqual(correlation_bucket("AAPL"), correlation_bucket("MSFT"))
        self.assertNotEqual(correlation_bucket("AAPL"), correlation_bucket("IWM"))

    def test_fixed_fractional(self) -> None:
        qty = fixed_fractional_contracts(
            equity=100000, premium=2.0, risk_fraction=0.01, stop_loss_pct=0.30
        )
        # risk $1000 / ($2*100*0.3=$60) => 16 contracts
        self.assertEqual(qty, 16)

    def test_max_concurrent_blocks(self) -> None:
        portfolio = {
            "positions": {
                f"OPT{i}": {"instrument_type": "option", "underlying": f"T{i}", "option_side": "call"}
                for i in range(4)
            }
        }
        allowed, reason, _ = check_new_trade_allowed(
            ticker="SPY",
            decision="BUY",
            portfolio=portfolio,
            settings={"risk": {"enabled": True, "max_concurrent_0dte": 4, "max_correlated_group": 2}},
            option_side="call",
        )
        self.assertFalse(allowed)
        self.assertIn("max_concurrent", reason)


class ScreenerScoreTests(unittest.TestCase):
    def test_illiquid_capped(self) -> None:
        q = score_setup_quality(
            {
                "liquidity_ok": 0.0,
                "atm_median_spread_pct": 0.2,
                "gex_available": 1.0,
                "gex_regime_code": -1.0,
                "max_pain_available": 1.0,
                "max_pain_distance_pct": 0.2,
                "iv_rank": 0.4,
                "flow_trend_available": 1.0,
                "flow_trend_score": 0.8,
                "nearest_dte": 0,
            },
            has_catalyst=False,
            settings={"odte_screener": {}},
        )
        self.assertLessEqual(q["setup_quality"], 42.0)

    def test_catalyst_illiquid_can_surface_higher(self) -> None:
        q = score_setup_quality(
            {
                "liquidity_ok": 0.0,
                "atm_median_spread_pct": 0.15,
                "gex_available": 0.0,
                "max_pain_available": 0.0,
                "iv_rank": 0.5,
                "flow_trend_available": 0.0,
                "call_volume_share": 0.7,
                "nearest_dte": 0,
            },
            has_catalyst=True,
            settings={"odte_screener": {}},
        )
        self.assertGreaterEqual(q["setup_quality"], 30.0)
        self.assertLessEqual(q["setup_quality"], 55.0)


if __name__ == "__main__":
    unittest.main()
