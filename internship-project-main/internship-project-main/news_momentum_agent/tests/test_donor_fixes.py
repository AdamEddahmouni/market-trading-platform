"""Regression tests for donor-project hygiene fixes (headline, gates, equity fallback)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.decision_engine import resolve_instrument_hint
from agent.portfolio import _attach_nbbo
from agent.telegram_notifier import _pending_confidence_pct, apply_approval
from news.news_aggregator import extract_primary_headline


class DonorFixesTests(unittest.TestCase):
    def test_extract_primary_headline_from_matched_article(self) -> None:
        aggregated = {
            "matched_articles": [{"headline": "Earnings beat expectations", "source": "RSS"}],
            "combined_text": "Headline: ignored scrape title",
        }
        self.assertEqual(extract_primary_headline(aggregated), "Earnings beat expectations")

    def test_extract_primary_headline_from_combined_text(self) -> None:
        aggregated = {
            "matched_articles": [],
            "combined_text": "[YAHOO]\nHeadline: COIN drops on guidance\nText: body",
        }
        self.assertEqual(extract_primary_headline(aggregated), "COIN drops on guidance")

    def test_resolve_instrument_hint_equity_on_liquidity_reject(self) -> None:
        self.assertEqual(
            resolve_instrument_hint(
                decision="BUY",
                options_bias="bullish",
                options_score=70.0,
                herd_urgency=50.0,
                liquidity_reject=True,
            ),
            "stock",
        )

    def test_resolve_instrument_hint_equity_on_fallback_flag(self) -> None:
        self.assertEqual(
            resolve_instrument_hint(
                decision="BUY",
                options_bias="bullish",
                options_score=70.0,
                herd_urgency=50.0,
                equity_fallback=True,
            ),
            "stock",
        )

    def test_attach_nbbo_adds_bid_ask(self) -> None:
        fill = _attach_nbbo({}, {"bid": 10.5, "ask": 10.7, "last": 10.6})
        self.assertEqual(fill["bid"], 10.5)
        self.assertEqual(fill["ask"], 10.7)
        self.assertEqual(fill["last"], 10.6)

    def test_telegram_approve_blocked_below_confidence_floor(self) -> None:
        settings = {"execution": {"min_confidence_for_telegram_approve": 40}}
        row = {
            "id": "p1",
            "status": "pending",
            "ticker": "NWL",
            "price_at_signal": 5.6,
            "decision_meta": {"confidence_pct": 12},
        }
        with patch("agent.telegram_notifier.load_pending", return_value=[row]):
            with patch("agent.telegram_notifier._update_pending"):
                result = apply_approval("p1", "BUY", "call", settings=settings)
        self.assertFalse(result["ok"])
        self.assertIn("below the 40% floor", result["message"])

    def test_pending_confidence_pct_resolves_nested_meta(self) -> None:
        row = {"in_depth_rationale": {"confidence_pct": 33.0}}
        self.assertEqual(_pending_confidence_pct(row), 33.0)


if __name__ == "__main__":
    unittest.main()
