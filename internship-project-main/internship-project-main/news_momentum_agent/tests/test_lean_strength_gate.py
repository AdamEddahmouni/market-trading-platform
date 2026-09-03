"""Regression: lean strength must not be substituted by agreement confidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import decide_trade_action
from agent.odte_decision import confidence_from_agreement


def _path_b_settings() -> dict:
    return {
        "execution": {
            "review_only_on_conflict": True,
            "min_confidence_for_action": 40,
            "min_confidence_for_path_b": 65,
            "min_lean_pct_for_path_b_execute": 60,
            "min_lean_over_wait_pct": 10,
            "require_options_bias_to_autoresolve": True,
            "force_review_all": False,
        },
        "odte_screener": {"min_setup_score": 0},
        "unified_decision": {
            "expiry_override_review": True,
            "expiry_buy_min_options_score": 65,
            "expiry_buy_min_urgency": 45,
        },
        "news_decay": {"enabled": False},
    }


def _morning_features(**extra) -> dict:
    """Features yielding ≥3 directional bearish votes so agreement_conf can clear 65.

    Lean gate is then the gate under test (coin-flip SELL lean still fails).
    """
    feats = {
        "liquidity_ok": 1.0,
        "liquidity_reject": 0.0,
        "tod_confidence_multiplier": 1.0,
        "regime_trust_multiplier": 1.0,
        "iv_rank": 0.5,
        "gex_regime_code": -1.0,
        "gex_available": 1.0,
        "max_pain_available": 1.0,
        "max_pain_distance_pct": -0.5,  # bearish vote
        "flow_trend_available": 1.0,
        "flow_trend_score": 0.30,  # bearish vote
        "tod_theta_remaining_frac": 0.95,
    }
    feats.update(extra)
    return feats


class AgreementSampleSizeTests(unittest.TestCase):
    def test_n_dir_2_cannot_clear_path_b_bar(self) -> None:
        conf, _ = confidence_from_agreement(1.0, n_directional=2, data_quality=1.0)
        self.assertLess(conf, 65.0)

    def test_n_dir_1_is_zero(self) -> None:
        conf, _ = confidence_from_agreement(1.0, n_directional=1, data_quality=1.0)
        self.assertEqual(conf, 0.0)

    def test_n_dir_4_can_be_high(self) -> None:
        conf, label = confidence_from_agreement(1.0, n_directional=4, data_quality=1.0)
        self.assertGreaterEqual(conf, 70.0)
        self.assertEqual(label, "high")


class Jul21LeanGateRegressionTests(unittest.TestCase):
    """Replay Jul 21 Path B losers → must LOG weak_lean; afternoon shadows stay blocked."""

    def test_qqq_1003_style_loser_is_weak_lean_log(self) -> None:
        # Bearish score ~32, high urgency → Path B override proposes SELL;
        # action probs stay coin-flip (~45% SELL) → lean gate blocks.
        decision, reason, meta = decide_trade_action(
            ticker="QQQ",
            social_signal_level="IGNORE",
            claude_response={
                "score": 0.0,
                "label": "neutral",
                "confidence": "low",
                "reasoning": "Path B near-expiry options scan",
            },
            news_headline="Path B near-expiry options scan",
            news_source="expiry_screener",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bearish",
            options_score=32.237,
            options_data_quality=1.0,
            signal_source="expiry",
            relative_volume=2.0,
            dte=0,
            volume_oi_spike=1.5,
            setup_quality_score=67.5,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=45,
            options_features=_morning_features(),
            settings=_path_b_settings(),
            apply_odte_layer=True,
        )
        self.assertEqual(decision, "LOG")
        self.assertEqual(meta.get("decision_reason_code") or meta.get("review_reason_code"), "weak_lean")
        self.assertIn("weak_lean", reason)
        self.assertLess(int(meta.get("lean_pct") or 0), 60)
        self.assertIn("agreement_confidence", meta)
        self.assertIn("n_dir", meta)

    def test_iwm_1255_style_loser_is_weak_lean_log(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="IWM",
            social_signal_level="IGNORE",
            claude_response={
                "score": 0.0,
                "label": "neutral",
                "confidence": "low",
                "reasoning": "Path B near-expiry options scan",
            },
            news_headline="Path B near-expiry options scan",
            news_source="expiry_screener",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bearish",
            options_score=27.91,
            options_data_quality=1.0,
            signal_source="expiry",
            relative_volume=2.5,
            dte=0,
            volume_oi_spike=2.0,
            setup_quality_score=66.8,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=45,
            options_features=_morning_features(tod_theta_remaining_frac=0.67),
            settings=_path_b_settings(),
            apply_odte_layer=True,
        )
        self.assertEqual(decision, "LOG")
        self.assertEqual(meta.get("decision_reason_code") or meta.get("review_reason_code"), "weak_lean")
        self.assertIn("weak_lean", reason)

    def test_afternoon_shadow_style_still_blocked(self) -> None:
        # Late-day floor + WAIT-dominant lean; must remain LOG (not newly actionable).
        decision, reason, meta = decide_trade_action(
            ticker="QQQ",
            social_signal_level="IGNORE",
            claude_response={
                "score": 0.0,
                "label": "neutral",
                "confidence": "low",
                "reasoning": "Path B near-expiry options scan",
            },
            news_headline="Path B near-expiry options scan",
            news_source="expiry_screener",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bearish",
            options_score=28.4,
            options_data_quality=1.0,
            signal_source="expiry",
            relative_volume=3.0,
            dte=0,
            volume_oi_spike=3.0,
            setup_quality_score=67.4,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=45,
            options_features=_morning_features(
                tod_confidence_multiplier=1.25,  # late-day raises effective min
                tod_theta_remaining_frac=0.42,
                flow_trend_available=0.0,
            ),
            settings=_path_b_settings(),
            apply_odte_layer=True,
        )
        self.assertEqual(decision, "LOG")
        self.assertNotEqual(decision, "SELL")
        code = str(meta.get("decision_reason_code") or meta.get("review_reason_code") or "")
        self.assertIn(code, {"weak_lean", "low_confidence", "options_not_clear", "no_lean"})


class SyntheticCoinFlipBugLockTests(unittest.TestCase):
    def test_high_agreement_low_n_dir_near_50_lean_not_sell(self) -> None:
        conf, _ = confidence_from_agreement(1.0, n_directional=2)
        self.assertLess(conf, 65.0)

        decision, reason, meta = decide_trade_action(
            ticker="SPY",
            social_signal_level="IGNORE",
            claude_response={
                "score": 0.0,
                "label": "neutral",
                "confidence": "low",
                "reasoning": "synthetic",
            },
            news_headline="synthetic",
            news_source="expiry_screener",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bearish",
            options_score=30.0,
            options_data_quality=1.0,
            signal_source="expiry",
            relative_volume=2.0,
            dte=0,
            volume_oi_spike=2.0,
            setup_quality_score=70.0,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=45,
            # Only options + max_pain bearish → n_dir around 2 if both vote
            options_features={
                "liquidity_ok": 1.0,
                "liquidity_reject": 0.0,
                "tod_confidence_multiplier": 1.0,
                "regime_trust_multiplier": 1.0,
                "iv_rank": 0.5,
                "max_pain_available": 1.0,
                "max_pain_distance_pct": -0.4,
                "gex_available": 0.0,
                "flow_trend_available": 0.0,
            },
            settings=_path_b_settings(),
            apply_odte_layer=True,
        )
        self.assertEqual(decision, "LOG")
        self.assertNotEqual(decision, "SELL")
        # Either lean gate or agreement-conf / n_dir floor blocks execute.
        self.assertTrue(
            "weak_lean" in reason
            or "actionable blocked" in reason
            or str(meta.get("decision_reason_code")) in {"weak_lean", "low_confidence"}
        )


if __name__ == "__main__":
    unittest.main()
