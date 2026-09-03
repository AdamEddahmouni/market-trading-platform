"""Tests for Path A pipeline health observability."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import path_a_pipeline_health as pah
from agent.eod_summary import build_eod_summary, format_telegram_summary
from agent.path_a_pipeline_health import (
    format_funnel_line,
    record_pipeline_cycle,
    record_screener_cycle,
    score_bucket,
)


class PathAPipelineHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmpdir.name)
        self.health_path = self.state_dir / "path_a_pipeline_health.json"
        self._patches = [
            patch.object(pah, "STATE_DIR", self.state_dir),
            patch.object(pah, "HEALTH_PATH", self.health_path),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()
        self._tmpdir.cleanup()

    def test_consecutive_zero_increments_and_resets(self) -> None:
        settings = {"agent": {"path_a_zero_alert_cycles": 3}}
        empty = {
            "cycle_id": 1,
            "finviz": {
                "raw": 0,
                "after_filters": 0,
                "scrape_ok": True,
                "scrape_error": None,
                "provider": "scraper",
                "elapsed_sec": 1.0,
            },
            "stocktwits": {
                "tickers_checked": 0,
                "api_ok": 0,
                "api_errors": {},
                "keyword_hits": 0,
                "keywords_matched": [],
                "reason_counts": {},
            },
            "tagging": {"HIGH_ALERT": 0, "WATCH": 0, "IGNORE": 0},
            "zero_reason": "no_screener_matches",
        }
        h1 = record_screener_cycle(empty, settings)
        self.assertEqual(h1["consecutive_zero"]["finviz_raw"], 1)
        h2 = record_screener_cycle(empty, settings)
        self.assertEqual(h2["consecutive_zero"]["finviz_raw"], 2)

        recovered = dict(empty)
        recovered["finviz"] = {
            "raw": 40,
            "after_filters": 12,
            "scrape_ok": True,
            "scrape_error": None,
            "provider": "scraper",
            "elapsed_sec": 2.0,
        }
        recovered["stocktwits"] = {
            "tickers_checked": 12,
            "api_ok": 10,
            "api_errors": {},
            "keyword_hits": 2,
            "keywords_matched": ["breakout"],
            "reason_counts": {"ok": 8, "no_keywords_matched": 2},
        }
        recovered["tagging"] = {"HIGH_ALERT": 1, "WATCH": 2, "IGNORE": 9}
        h3 = record_screener_cycle(recovered, settings)
        self.assertEqual(h3["consecutive_zero"]["finviz_raw"], 0)
        self.assertEqual(h3["consecutive_zero"]["finviz_filtered"], 0)
        self.assertEqual(h3["consecutive_zero"]["stocktwits_keyword_hits"], 0)
        self.assertEqual(h3["consecutive_zero"]["high_alert"], 0)

    def test_keyword_and_high_alert_zero_rules(self) -> None:
        settings = {"agent": {"path_a_zero_alert_cycles": 3}}
        stats = {
            "cycle_id": 2,
            "finviz": {
                "raw": 20,
                "after_filters": 8,
                "scrape_ok": True,
                "scrape_error": None,
                "provider": "scraper",
                "elapsed_sec": 1.5,
            },
            "stocktwits": {
                "tickers_checked": 8,
                "api_ok": 8,
                "api_errors": {},
                "keyword_hits": 0,
                "keywords_matched": [],
                "reason_counts": {"no_keywords_matched": 8},
            },
            "tagging": {"HIGH_ALERT": 0, "WATCH": 0, "IGNORE": 8},
            "zero_reason": "no_social_high_alerts:no_keywords_matched",
        }
        h = record_screener_cycle(stats, settings)
        self.assertEqual(h["consecutive_zero"]["stocktwits_keyword_hits"], 1)
        self.assertEqual(h["consecutive_zero"]["high_alert"], 1)
        self.assertEqual(h["consecutive_zero"]["finviz_raw"], 0)

    def test_notify_latch_fires_once_at_threshold(self) -> None:
        settings = {"agent": {"path_a_zero_alert_cycles": 3, "path_a_zero_alerts_rth_only": False}}
        empty = {
            "cycle_id": 1,
            "finviz": {
                "raw": 0,
                "after_filters": 0,
                "scrape_ok": False,
                "scrape_error": "TimeoutError: timed out",
                "provider": "scraper",
                "elapsed_sec": 8.0,
            },
            "stocktwits": {
                "tickers_checked": 0,
                "api_ok": 0,
                "api_errors": {},
                "keyword_hits": 0,
                "keywords_matched": [],
                "reason_counts": {},
            },
            "tagging": {"HIGH_ALERT": 0, "WATCH": 0, "IGNORE": 0},
            "zero_reason": "no_screener_matches",
        }
        self.assertFalse(record_screener_cycle(empty, settings).get("_should_notify"))
        self.assertFalse(record_screener_cycle(empty, settings).get("_should_notify"))
        third = record_screener_cycle(empty, settings)
        self.assertTrue(third.get("_should_notify"))
        self.assertIn("finviz_raw=3", third.get("_notify_messages") or [])
        fourth = record_screener_cycle(empty, settings)
        self.assertFalse(fourth.get("_should_notify"))
        self.assertTrue(fourth["alerted_stages"]["finviz_raw"])

    def test_pipeline_zeros_suppressed_outside_rth(self) -> None:
        settings = {"agent": {"path_a_zero_alert_cycles": 2, "path_a_zero_alerts_rth_only": True}}
        zero_news = {
            "tag": "HIGH_ALERT",
            "tickers_in": 3,
            "news": {"tickers_with_news": 0, "tickers_no_news": 3, "by_source": {}, "errors": []},
            "claude": {"scored": 0, "score_buckets": {}, "errors": 0},
            "social_gate": {"require_social_signal": True, "blocked": 0, "passed": 0},
            "decisions": {"BUY": 0, "SELL": 0, "REVIEW": 0, "LOG": 0},
            "log_reason_codes": {},
        }
        with patch("agent.path_a_pipeline_health._in_rth_for_alerts", return_value=False):
            h1 = record_pipeline_cycle(zero_news, settings)
            h2 = record_pipeline_cycle(zero_news, settings)
            h3 = record_pipeline_cycle(zero_news, settings)
        self.assertFalse(h1.get("_should_notify"))
        self.assertFalse(h2.get("_should_notify"))
        self.assertFalse(h3.get("_should_notify"))
        self.assertTrue(h3.get("_alerts_suppressed_outside_rth"))
        self.assertEqual(h3["consecutive_zero"]["news_with_headlines"], 0)
        self.assertFalse(h3["alerted_stages"]["news_with_headlines"])

    def test_pipeline_zeros_only_when_tickers_in(self) -> None:
        settings = {"agent": {"path_a_zero_alert_cycles": 2, "path_a_zero_alerts_rth_only": False}}
        empty_run = {
            "tag": "HIGH_ALERT",
            "tickers_in": 0,
            "news": {"tickers_with_news": 0, "tickers_no_news": 0, "by_source": {}, "errors": []},
            "claude": {"scored": 0, "score_buckets": {}, "errors": 0},
            "social_gate": {"require_social_signal": True, "blocked": 0, "passed": 0},
            "decisions": {"BUY": 0, "SELL": 0, "REVIEW": 0, "LOG": 0},
            "log_reason_codes": {},
        }
        h0 = record_pipeline_cycle(empty_run, settings)
        self.assertEqual(h0["consecutive_zero"]["news_with_headlines"], 0)

        zero_news = {
            "tag": "HIGH_ALERT",
            "tickers_in": 3,
            "news": {"tickers_with_news": 0, "tickers_no_news": 3, "by_source": {}, "errors": []},
            "claude": {"scored": 0, "score_buckets": {}, "errors": 0},
            "social_gate": {"require_social_signal": True, "blocked": 0, "passed": 0},
            "decisions": {"BUY": 0, "SELL": 0, "REVIEW": 0, "LOG": 0},
            "log_reason_codes": {},
        }
        h1 = record_pipeline_cycle(zero_news, settings)
        self.assertEqual(h1["consecutive_zero"]["news_with_headlines"], 1)
        h2 = record_pipeline_cycle(zero_news, settings)
        self.assertTrue(h2.get("_should_notify"))
        self.assertIn("news_with_headlines=2", h2.get("_notify_messages") or [])

    def test_format_funnel_line_shape(self) -> None:
        health = {
            "last_screener": {
                "finviz": {"raw": 40, "after_filters": 12},
                "tagging": {"HIGH_ALERT": 1, "WATCH": 2},
            },
            "last_pipeline": {
                "tickers_in": 3,
                "news": {"tickers_with_news": 2},
                "claude": {"scored": 2},
                "social_gate": {"passed": 0},
                "decisions": {"BUY": 0, "SELL": 0},
            },
        }
        line = format_funnel_line(health)
        self.assertIn("Finviz: 40→12 filtered", line)
        self.assertIn("1 HIGH_ALERT / 2 WATCH", line)
        self.assertIn("pipeline 3 in", line)
        self.assertIn("2 news", line)
        self.assertIn("2 scored", line)
        self.assertIn("0 cleared social", line)
        self.assertIn("0 BUY/SELL", line)

    def test_score_bucket(self) -> None:
        self.assertEqual(score_bucket(-0.6), "lt_-0.5")
        self.assertEqual(score_bucket(-0.3), "-0.5_to_-0.2")
        self.assertEqual(score_bucket(0.0), "-0.2_to_0.2")
        self.assertEqual(score_bucket(0.3), "0.2_to_0.5")
        self.assertEqual(score_bucket(0.7), "gt_0.5")

    def test_eod_includes_path_a_funnel(self) -> None:
        record_screener_cycle(
            {
                "cycle_id": 9,
                "finviz": {
                    "raw": 10,
                    "after_filters": 4,
                    "scrape_ok": True,
                    "scrape_error": None,
                    "provider": "scraper",
                    "elapsed_sec": 1.0,
                },
                "stocktwits": {
                    "tickers_checked": 4,
                    "api_ok": 4,
                    "api_errors": {},
                    "keyword_hits": 1,
                    "keywords_matched": ["premarket"],
                    "reason_counts": {"ok": 1, "no_keywords_matched": 3},
                },
                "tagging": {"HIGH_ALERT": 1, "WATCH": 0, "IGNORE": 3},
                "zero_reason": "ok",
            },
            {"agent": {"path_a_zero_alert_cycles": 3}},
        )
        summary = build_eod_summary(session_date="2026-07-21", executions=[], trade_log=[])
        self.assertIn("path_a_funnel", summary)
        self.assertIn("Finviz:", summary["path_a_funnel"].get("funnel_line", ""))
        text = format_telegram_summary(summary)
        self.assertIn("Path A:", text)

    def test_aggregator_returns_source_counts(self) -> None:
        from news.news_aggregator import aggregate_news_for_ticker

        articles = [
            {
                "source": "PR Newswire",
                "headline": "Acme announces deal",
                "url": "https://example.com/a",
            }
        ]
        with patch("news.news_aggregator.find_recent_ticker_articles", return_value=articles), patch(
            "news.news_aggregator.scrape_article_text", return_value="body"
        ), patch("news.news_aggregator.scrape_yahoo_finance_news", return_value="yahoo body"), patch(
            "news.news_aggregator.scrape_benzinga_news", side_effect=TimeoutError("timed out")
        ), patch("news.news_aggregator.scrape_marketwatch_news", return_value=""):
            result = aggregate_news_for_ticker("ACME", "Acme Corp")

        self.assertTrue(result["has_news"])
        self.assertIn("source_counts", result)
        self.assertGreaterEqual(int(result["source_counts"].get("PR Newswire", 0)), 1)
        self.assertGreaterEqual(int(result["source_counts"].get("Yahoo", 0)), 1)
        self.assertTrue(any(e.get("source") == "Benzinga" for e in result.get("errors") or []))

        with patch("news.news_aggregator.find_recent_ticker_articles", return_value=[]), patch(
            "news.news_aggregator.scrape_yahoo_finance_news", return_value=""
        ), patch("news.news_aggregator.scrape_benzinga_news", return_value=""), patch(
            "news.news_aggregator.scrape_marketwatch_news", return_value=""
        ):
            empty = aggregate_news_for_ticker("ZZZ", "Zed")
        self.assertFalse(empty["has_news"])
        self.assertEqual(empty.get("source_counts"), {})
        self.assertEqual(empty.get("errors"), [])


if __name__ == "__main__":
    unittest.main()
