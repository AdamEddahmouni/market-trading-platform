"""Regression tests for micro-cap news source coverage (CLDI / GRML / ZBAO gap)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from news.news_aggregator import aggregate_news_for_ticker, dedupe_articles
from news.rss_monitor import (
    DEFAULT_SOURCES,
    find_recent_ticker_articles,
    headline_matches_ticker,
    resolve_source_configs,
)
from agent.path_a_pipeline_health import format_funnel_line


class HeadlineMatchTests(unittest.TestCase):
    def test_word_boundary_ticker(self) -> None:
        self.assertTrue(headline_matches_ticker("CLDI announces 1-for-16 reverse stock split", "CLDI"))
        self.assertTrue(headline_matches_ticker("$CLDI reverse split effective Monday", "CLDI"))
        self.assertFalse(headline_matches_ticker("SCLDIM news", "CLDI"))

    def test_company_name_match(self) -> None:
        self.assertTrue(
            headline_matches_ticker(
                "Calidi Biotherapeutics Announces Reverse Stock Split",
                "CLDI",
                "Calidi Biotherapeutics Inc",
            )
        )
        self.assertTrue(
            headline_matches_ticker(
                "Zhibao Technology Receives Nasdaq Deficiency Notice",
                "ZBAO",
                "Zhibao Technology Inc",
            )
        )
        self.assertTrue(
            headline_matches_ticker(
                "Greenland Mines updates mineral resource estimate",
                "GRML",
                "Greenland Mines Ltd",
            )
        )


class DedupeTests(unittest.TestCase):
    def test_dedupe_same_headline_across_sources(self) -> None:
        articles = [
            {
                "source": "Globe Newswire",
                "headline": "CLDI Announces Reverse Stock Split",
                "url": "https://example.com/a",
            },
            {
                "source": "Yahoo",
                "headline": "CLDI announces reverse stock split!",
                "url": "https://example.com/b",
            },
        ]
        out = dedupe_articles(articles)
        self.assertEqual(len(out), 1)
        self.assertIn("Yahoo", out[0].get("also_seen_on") or [])


class RegistryToggleTests(unittest.TestCase):
    def test_disabled_source_omitted_from_configs(self) -> None:
        settings = {
            "news": {
                "sources": {
                    "globe_newswire": {"enabled": False},
                    "newsfile": {"enabled": True},
                }
            }
        }
        cfg = resolve_source_configs(settings)
        self.assertFalse(cfg["globe_newswire"]["enabled"])
        self.assertTrue(cfg["newsfile"]["enabled"])
        self.assertIn("sec_edgar", cfg)
        self.assertEqual(cfg["sec_edgar"]["kind"], DEFAULT_SOURCES["sec_edgar"]["kind"])


class FixtureFeedMatchTests(unittest.TestCase):
    """Simulate wire entries that would have covered today's HIGH_ALERT gaps."""

    def test_fixture_entries_match_microcaps(self) -> None:
        fixtures = [
            (
                "CLDI",
                "Calidi Biotherapeutics Inc",
                "Globe Newswire",
                "Calidi Biotherapeutics Announces 1-for-16 Reverse Stock Split",
                "https://www.globenewswire.com/news-release/cldi-reverse-split",
            ),
            (
                "ZBAO",
                "Zhibao Technology Inc",
                "Newsfile",
                "Zhibao Technology Receives Nasdaq Minimum Bid Price Deficiency Notice",
                "https://www.newsfilecorp.com/release/zbao-nasdaq",
            ),
            (
                "GRML",
                "Greenland Mines Ltd",
                "Newsfile",
                "Greenland Mines Ltd. Announces Updated Resource Estimate and Share Exchange",
                "https://www.newsfilecorp.com/release/grml-resource",
            ),
        ]

        def fake_parse(url: str, source_name: str, source_key: str):
            out = []
            for ticker, company, src, headline, link in fixtures:
                if src != source_name:
                    continue
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                out.append(
                    {
                        "source": source_name,
                        "source_key": source_key,
                        "headline": headline,
                        "url": link,
                        "published_utc": now.isoformat(),
                        "_published_dt": now,
                    }
                )
            return out

        settings = {
            "news": {
                "sources": {
                    "pr_newswire": {"enabled": False},
                    "business_wire": {"enabled": False},
                    "access_newswire": {"enabled": False},
                    "sec_edgar": {"enabled": False},
                    "yahoo": {"enabled": False},
                    "benzinga": {"enabled": False},
                    "marketwatch": {"enabled": False},
                    "globe_newswire": {"enabled": True},
                    "newsfile": {"enabled": True},
                }
            }
        }

        with patch("news.rss_monitor._parse_feed_entries", side_effect=fake_parse):
            for ticker, company, expected_source, _headline, _url in fixtures:
                hits = find_recent_ticker_articles(
                    ticker=ticker,
                    company_name=company,
                    max_article_age_hours=24,
                    settings=settings,
                    persist_seen=False,
                    include_edgar=False,
                )
                self.assertTrue(hits, msg=f"expected hits for {ticker}")
                sources = {h.get("source") for h in hits}
                self.assertIn(expected_source, sources)


class AggregatorEarlyReturnFixTests(unittest.TestCase):
    def test_empty_rss_still_calls_html_scrapers(self) -> None:
        settings = {
            "news": {
                "sources": {
                    "pr_newswire": {"enabled": False},
                    "globe_newswire": {"enabled": False},
                    "business_wire": {"enabled": False},
                    "newsfile": {"enabled": False},
                    "access_newswire": {"enabled": False},
                    "sec_edgar": {"enabled": False},
                    "yahoo": {"enabled": True},
                    "benzinga": {"enabled": False},
                    "marketwatch": {"enabled": False},
                }
            }
        }
        with patch("news.news_aggregator.find_recent_ticker_articles", return_value=[]):
            with patch(
                "news.news_aggregator.scrape_yahoo_finance_news",
                return_value="Yahoo headline about CLDI reverse split",
            ) as yahoo:
                result = aggregate_news_for_ticker(
                    ticker="CLDI",
                    company_name="Calidi Biotherapeutics Inc",
                    settings=settings,
                )
        yahoo.assert_called_once()
        self.assertTrue(result["has_news"])
        self.assertIn("Yahoo", result["source_counts"])


class FunnelSourceSuffixTests(unittest.TestCase):
    def test_funnel_includes_by_source_counts(self) -> None:
        line = format_funnel_line(
            {
                "last_screener": {
                    "finviz": {"raw": 100, "after_filters": 40},
                    "tagging": {"HIGH_ALERT": 2, "WATCH": 1},
                },
                "last_pipeline": {
                    "tickers_in": 2,
                    "news": {
                        "tickers_with_news": 1,
                        "by_source": {"Globe Newswire": 1, "SEC EDGAR": 2},
                    },
                    "claude": {"scored": 1},
                    "social_gate": {"passed": 0},
                    "decisions": {"BUY": 0, "SELL": 0},
                },
            }
        )
        self.assertIn("globe=1", line)
        self.assertIn("edgar=2", line)


if __name__ == "__main__":
    unittest.main()
