"""Unit tests for StockTwits scanner social funnel outputs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import social.stocktwits_scanner as scanner


class StocktwitsScannerTests(unittest.TestCase):
    """Validate reason codes and counters without network calls."""

    def test_no_recent_posts_reason(self) -> None:
        original_fetch = scanner.fetch_stocktwits_posts

        def fake_fetch(**_: object) -> dict:
            return {
                "posts": [{"id": 1, "created_at": "2000-01-01T00:00:00Z", "body": "old post"}],
                "reason_code": "ok",
                "posts_fetched": 1,
            }

        scanner.fetch_stocktwits_posts = fake_fetch
        try:
            result = scanner.scan_ticker_social_signal(
                ticker="TEST",
                posts_to_fetch=5,
                max_post_age_hours=24,
                high_alert_threshold=3,
                watch_threshold=1,
            )
            self.assertEqual(result["reason_code"], "no_recent_posts")
            self.assertEqual(result["posts_fetched"], 1)
            self.assertEqual(result["recent_posts_scanned"], 0)
        finally:
            scanner.fetch_stocktwits_posts = original_fetch

    def test_keyword_match_counts(self) -> None:
        original_fetch = scanner.fetch_stocktwits_posts

        def fake_fetch(**_: object) -> dict:
            return {
                "posts": [{"id": 2, "created_at": "2030-01-01T00:00:00Z", "body": "short squeeze incoming"}],
                "reason_code": "ok",
                "posts_fetched": 1,
            }

        scanner.fetch_stocktwits_posts = fake_fetch
        try:
            result = scanner.scan_ticker_social_signal(
                ticker="TEST",
                posts_to_fetch=5,
                max_post_age_hours=24,
                high_alert_threshold=3,
                watch_threshold=1,
            )
            self.assertEqual(result["posts_fetched"], 1)
            self.assertEqual(result["posts_matched"], 1)
            self.assertEqual(result["reason_code"], "ok")
        finally:
            scanner.fetch_stocktwits_posts = original_fetch


if __name__ == "__main__":
    unittest.main()
