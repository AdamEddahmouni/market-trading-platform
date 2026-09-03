"""Integration tests for options confirmation layer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPTIONS_ENGINE_ROOT = PROJECT_ROOT.parent / "options_confirmation_engine"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import decide_trade_action
from agent import options_client


BUY_CLAUDE = {"score": 0.8, "confidence": "high", "reasoning": "Strong catalyst"}
SELL_CLAUDE = {"score": -0.8, "confidence": "high", "reasoning": "Material negative update"}


class OptionsGateTests(unittest.TestCase):
    """Validate options confirmation gate on top of news-only decisions."""

    def _buy_decision(self, **options_kwargs: object) -> tuple[str, str, dict]:
        return decide_trade_action(
            ticker="TEST",
            social_signal_level="HIGH_ALERT",
            claude_response=BUY_CLAUDE,
            news_headline="Headline",
            news_source="Source",
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_enabled=True,
            **options_kwargs,
        )

    def _sell_decision(self, **options_kwargs: object) -> tuple[str, str, dict]:
        return decide_trade_action(
            ticker="TEST",
            social_signal_level="HIGH_ALERT",
            claude_response=SELL_CLAUDE,
            news_headline="Headline",
            news_source="Source",
            buy_threshold=0.5,
            sell_threshold=-0.5,
            options_enabled=True,
            **options_kwargs,
        )

    def test_buy_bullish_stays_buy(self) -> None:
        decision, reason, _ = self._buy_decision(options_bias="bullish", options_score=72.0)
        self.assertEqual(decision, "BUY")
        self.assertIn("Options confirmed", reason)

    def test_buy_bearish_downgrades_to_review(self) -> None:
        decision, reason, _ = self._buy_decision(options_bias="bearish", options_score=30.0)
        self.assertEqual(decision, "REVIEW")
        self.assertIn("News BUY blocked", reason)

    def test_buy_no_data_downgrades_to_review(self) -> None:
        decision, reason, _ = self._buy_decision(options_bias="no_data", options_score=50.0)
        self.assertEqual(decision, "REVIEW")
        self.assertIn("News BUY blocked", reason)

    def test_buy_no_data_allow_news_only_when_chain_thin(self) -> None:
        decision, reason, _ = self._buy_decision(
            options_bias="no_data",
            options_score=50.0,
            options_data_quality=0.4,
            no_data_policy="allow_news_only",
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("news+social only", reason)

    def test_buy_no_data_still_blocks_on_engine_failure(self) -> None:
        decision, reason, _ = self._buy_decision(
            options_bias="no_data",
            options_score=50.0,
            options_data_quality=0.1,
            options_data_flags=["invalid_auth_token"],
            no_data_policy="allow_news_only",
        )
        self.assertEqual(decision, "REVIEW")
        self.assertIn("options unavailable", reason)

    def test_buy_no_data_allow_strong_news(self) -> None:
        decision, reason, _ = self._buy_decision(
            options_bias="no_data",
            options_score=50.0,
            options_data_quality=0.4,
            no_data_policy="allow_strong_news",
            no_data_strong_news_threshold=0.75,
        )
        self.assertEqual(decision, "BUY")
        self.assertIn("strong news", reason)

    def test_buy_neutral_low_score_downgrades_to_review(self) -> None:
        decision, reason, _ = self._buy_decision(options_bias="neutral", options_score=55.0)
        self.assertEqual(decision, "REVIEW")
        self.assertIn("options unclear", reason)

    def test_sell_bearish_stays_sell(self) -> None:
        decision, reason, _ = self._sell_decision(options_bias="bearish", options_score=30.0)
        self.assertEqual(decision, "SELL")
        self.assertIn("Options confirmed", reason)

    def test_sell_bullish_downgrades_to_review(self) -> None:
        decision, reason, _ = self._sell_decision(options_bias="bullish", options_score=72.0)
        self.assertEqual(decision, "REVIEW")
        self.assertIn("News SELL blocked", reason)

    def test_options_disabled_preserves_news_only(self) -> None:
        decision, _, _ = decide_trade_action(
            ticker="TEST",
            social_signal_level="HIGH_ALERT",
            claude_response=BUY_CLAUDE,
            news_headline="Headline",
            news_source="Source",
            options_enabled=False,
            options_bias="bearish",
            options_score=20.0,
        )
        self.assertEqual(decision, "BUY")


class OptionsClientTests(unittest.TestCase):
    """Validate options_client wrapper behavior."""

    def test_fallback_on_missing_engine_path(self) -> None:
        result = options_client.score_ticker("AAPL", {"options_confirmation": {}})
        self.assertEqual(result["options_bias"], "no_data")
        self.assertEqual(result["ticker"], "AAPL")

    def test_fallback_on_invalid_engine_path(self) -> None:
        settings = {
            "options_confirmation": {
                "engine_path": "/nonexistent/path/to/options_engine",
                "offline_mode": True,
            }
        }
        result = options_client.score_ticker("AAPL", settings)
        self.assertEqual(result["options_bias"], "no_data")

    @unittest.skipUnless(OPTIONS_ENGINE_ROOT.exists(), "options engine not present")
    def test_offline_replay_integration(self) -> None:
        settings = {
            "options_confirmation": {
                "engine_path": str(OPTIONS_ENGINE_ROOT),
                "offline_mode": True,
            }
        }
        result = options_client.score_ticker("AAPL", settings)
        self.assertIn(result["options_bias"], {"bullish", "bearish", "neutral", "no_data"})
        self.assertIsInstance(result["options_score"], float)


if __name__ == "__main__":
    unittest.main()
