"""Tests for action_probs and Path B override rules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import compute_action_probs, decide_trade_action


class UnifiedDecisionTests(unittest.TestCase):
    def test_action_probs_sum_to_one(self) -> None:
        probs = compute_action_probs(
            news_score=0.6,
            social_signal_level="HIGH_ALERT",
            options_bias="bullish",
            options_score=70,
            herd_urgency=65,
            decision="REVIEW",
        )
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=3)
        self.assertIn("BUY", probs)

    def test_review_includes_lean_percent(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="WATCH",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "Catalyst"},
            news_headline="Headline",
            news_source="Source",
            options_enabled=True,
            options_bias="bullish",
            options_score=70,
        )
        self.assertEqual(decision, "REVIEW")
        self.assertIn("Lean", reason)
        self.assertIn("action_probs", meta)
        self.assertGreater(meta["lean_pct"], 0)

    def test_path_b_overrides_review(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="IGNORE",
            claude_response={"score": 0.0, "confidence": "low", "reasoning": "No news"},
            news_headline="Path B",
            news_source="expiry",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bullish",
            options_score=80,
            options_data_quality=0.8,
            signal_source="expiry",
            dte=2,
            volume_oi_spike=4.0,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=60,
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("Path B", reason)
        self.assertEqual(meta["signal_source"], "expiry")
        self.assertEqual(meta["instrument_hint"], "call")

    def test_path_b_zero_dte_buy_at_urgency_45(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="SPY",
            social_signal_level="IGNORE",
            claude_response={"score": 0.0, "confidence": "low", "reasoning": "No news"},
            news_headline="0DTE Path B",
            news_source="expiry",
            require_social_signal=False,
            options_enabled=True,
            options_bias="bullish",
            options_score=70,
            options_data_quality=0.8,
            signal_source="expiry",
            dte=0,
            volume_oi_spike=0.0,
            expiry_override_review=True,
            expiry_buy_min_options_score=65,
            expiry_buy_min_urgency=45,
        )
        self.assertEqual(decision, "BUY")
        self.assertGreaterEqual(float(meta.get("herd_urgency", 0)), 55.0)
        self.assertEqual(meta["instrument_hint"], "call")

    def test_news_buy_options_conflict_stays_review_without_path_b(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="HIGH_ALERT",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "Catalyst"},
            news_headline="Headline",
            news_source="Source",
            options_enabled=True,
            options_bias="bearish",
            options_score=25,
            options_data_quality=0.8,
            relative_volume=1.6,
            expiry_override_review=False,
        )
        self.assertEqual(decision, "REVIEW")
        self.assertEqual(meta["review_reason_code"], "options_conflict")


if __name__ == "__main__":
    unittest.main()
