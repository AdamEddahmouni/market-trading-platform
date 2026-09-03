"""Tests for law-firm solicitation headline filter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from news.solicitation_filter import filter_solicitation_articles, is_law_firm_solicitation


class SolicitationFilterTests(unittest.TestCase):
    def test_be_kaplan_fox_headline_is_solicitation(self) -> None:
        headline = (
            "Kaplan Fox & Kilsheimer LLP Alerts Bloom Energy Corporation (BE) Investors "
            "to a Securities Class Action Deadline on September 28, 2026"
        )
        self.assertTrue(is_law_firm_solicitation(headline))

    def test_pics_cross_ticker_kaplan_fox_is_solicitation(self) -> None:
        headline = (
            "Kaplan Fox Alerts Investors to an Upcoming Deadline of August 4, 2026 "
            "in the PicS N.V. (NASDAQ: PICS) Securities Class Action"
        )
        self.assertTrue(is_law_firm_solicitation(headline))

    def test_real_company_news_not_filtered(self) -> None:
        self.assertFalse(
            is_law_firm_solicitation(
                "Bloom Energy reports record Q2 revenue and raises 2026 guidance"
            )
        )
        self.assertFalse(
            is_law_firm_solicitation("Apple unveils new iPhone lineup at product event")
        )

    def test_filter_articles_keeps_real_news(self) -> None:
        articles = [
            {
                "headline": (
                    "Kaplan Fox & Kilsheimer LLP Alerts Bloom Energy Corporation (BE) "
                    "Investors to a Securities Class Action Deadline on September 28, 2026"
                ),
                "source": "Newsfile",
            },
            {
                "headline": "Bloom Energy raises full-year guidance after strong Q2",
                "source": "BusinessWire",
            },
        ]
        kept, dropped = filter_solicitation_articles(articles)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("raises full-year", kept[0]["headline"])

    def test_can_disable_via_settings(self) -> None:
        articles = [
            {
                "headline": (
                    "Rosen Law Firm Encourages The Ensign Group, Inc. Investors "
                    "to Inquire About Securities Class Action Investigation"
                )
            }
        ]
        kept, dropped = filter_solicitation_articles(
            articles, settings={"news": {"exclude_law_firm_solicitations": False}}
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 0)


if __name__ == "__main__":
    unittest.main()
