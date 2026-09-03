"""Tests for decision explanation cards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_explainer import build_decision_explanation, format_explanation_text


class DecisionExplainerTests(unittest.TestCase):
    def test_0dte_buy_call_card(self) -> None:
        card = build_decision_explanation(
            ticker="SPY",
            decision="BUY",
            reason="Path B override: expiry bullish+urgent",
            instrument_hint="call",
            action_probs={"BUY": 0.62, "SELL": 0.1, "WAIT": 0.2, "AVOID": 0.08},
            lean="BUY",
            lean_pct=62,
            signal_source="expiry",
            herd_stage="coiled",
            quadrant="Q1",
            options_bias="bullish",
            options_score=78,
            dte=0,
            exits={"take_profit_pct": 0.4, "stop_loss_pct": 0.3, "eod_flatten_et": "15:45"},
        )
        self.assertIn("0DTE", card["instrument"])
        self.assertIn("call", card["instrument"])
        self.assertEqual(card["confidence_label"], "medium")
        self.assertGreaterEqual(card["confidence_pct"], 60)
        self.assertIn("take-profit", card["exit_plan"].lower())
        text = format_explanation_text(card)
        self.assertIn("Why:", text)
        self.assertIn("Expect:", text)

    def test_merges_advisor_rationale(self) -> None:
        card = build_decision_explanation(
            ticker="AAPL",
            decision="BUY",
            instrument_hint="call",
            lean="BUY",
            lean_pct=70,
            signal_source="news",
            news_headline="AAPL beats earnings",
            news_score=0.8,
            news_confidence="high",
            options_bias="bullish",
            options_score=72,
            dte=0,
            advisor={"next_step": "Hold above 210 into close.", "rationale": "Flow confirms upside.", "confidence": 0.8},
        )
        self.assertIn("Flow confirms", card["why"])
        self.assertIn("Hold above 210", card["what_to_expect"])
        self.assertEqual(card["confidence_label"], "high")


if __name__ == "__main__":
    unittest.main()
