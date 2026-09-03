"""Unit tests for decision threshold wiring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import decide_trade_action


class DecisionEngineTests(unittest.TestCase):
    """Validate configurable buy/sell thresholds and social requirement."""

    def test_buy_requires_high_alert(self) -> None:
        decision, _, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="HIGH_ALERT",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "Strong catalyst"},
            news_headline="Headline",
            news_source="Source",
            buy_threshold=0.7,
            sell_threshold=-0.7,
            require_social_signal=True,
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("action_probs", meta)

    def test_watch_positive_is_review(self) -> None:
        decision, _, meta = decide_trade_action(
            ticker="TEST",
            social_signal_level="WATCH",
            claude_response={"score": 0.8, "confidence": "high", "reasoning": "Strong catalyst"},
            news_headline="Headline",
            news_source="Source",
            buy_threshold=0.7,
            sell_threshold=-0.7,
            require_social_signal=True,
        )
        self.assertEqual(decision, "REVIEW")
        self.assertGreater(meta["lean_pct"], 0)

    def test_ignore_social_logs_when_required(self) -> None:
        decision, _, _ = decide_trade_action(
            ticker="TEST",
            social_signal_level="IGNORE",
            claude_response={"score": 0.9, "confidence": "high", "reasoning": "Strong catalyst"},
            news_headline="Headline",
            news_source="Source",
            buy_threshold=0.7,
            sell_threshold=-0.7,
            require_social_signal=True,
        )
        self.assertEqual(decision, "LOG")


if __name__ == "__main__":
    unittest.main()
