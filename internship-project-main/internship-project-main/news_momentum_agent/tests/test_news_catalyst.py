"""Tests for Path A.2 news-catalyst decision rules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import _decide_news_catalyst, decide_trade_action


class NewsCatalystDecisionTests(unittest.TestCase):
    def test_strong_news_buys_without_social(self) -> None:
        decision, reason = _decide_news_catalyst(
            ticker="NVDA",
            social_signal_level="IGNORE",
            claude_response={"score": 0.72, "confidence": "high", "reasoning": "Beat"},
            news_headline="NVDA raises guidance",
            news_source="PR Newswire",
            buy_threshold=0.55,
            sell_threshold=-0.55,
            review_threshold=0.35,
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("Path A.2", reason)

    def test_weak_news_logs(self) -> None:
        decision, _ = _decide_news_catalyst(
            ticker="XYZ",
            social_signal_level="IGNORE",
            claude_response={"score": 0.1, "confidence": "low", "reasoning": "Meh"},
            news_headline="Routine update",
            news_source="wire",
            buy_threshold=0.55,
            sell_threshold=-0.55,
            review_threshold=0.35,
        )
        self.assertEqual(decision, "LOG")

    def test_decide_trade_action_news_catalyst_source(self) -> None:
        decision, reason, meta = decide_trade_action(
            ticker="AAPL",
            social_signal_level="IGNORE",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "Major deal"},
            news_headline="AAPL announces acquisition",
            news_source="BusinessWire",
            require_social_signal=True,
            options_enabled=True,
            options_bias="bullish",
            options_score=68.0,
            signal_source="news_catalyst",
            settings={
                "news_catalyst": {
                    "buy_threshold": 0.55,
                    "sell_threshold": -0.55,
                    "review_threshold": 0.35,
                },
                "execution": {"review_only_on_conflict": True, "min_confidence_for_action": 40},
                "odte_screener": {"min_setup_score": 0},
            },
            apply_odte_layer=True,
        )
        self.assertEqual(meta["signal_source"], "news_catalyst")
        self.assertIn(decision, {"BUY", "REVIEW", "LOG"})
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
