"""NewsAPI and Finnhub provider tests — no live credentials."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.news.aggregator import aggregate_news_items  # noqa: E402
from market_platform_foundation.news.providers import (  # noqa: E402
    FinnhubNewsClient,
    NewsApiClient,
)


class NewsProviderTests(unittest.TestCase):
    def test_newsapi_normalizes_articles_without_exposing_key(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_get(url: str, **kwargs: object) -> SimpleNamespace:
            calls.append({"url": url, **kwargs})
            return SimpleNamespace(
                status_code=200,
                text=json.dumps(
                    {
                        "status": "ok",
                        "totalResults": 1,
                        "articles": [
                            {
                                "source": {"id": "wire", "name": "Wire News"},
                                "author": "Reporter",
                                "title": "AAPL reports results",
                                "description": "Company update",
                                "url": "https://news.example/aapl",
                                "publishedAt": "2026-09-01T18:00:00Z",
                                "content": "AAPL content",
                            }
                        ],
                    }
                ),
                headers={"content-type": "application/json"},
            )

        result = NewsApiClient(
            api_key="news-secret",
            http_getter=fake_get,
            live_enabled=True,
            min_interval_s=0.0,
        ).fetch_news("AAPL")

        self.assertTrue(result["success"])
        self.assertEqual(result["items"][0]["provider"], "NEWSAPI")
        self.assertEqual(result["items"][0]["tickers"], ["AAPL"])
        self.assertEqual(result["items"][0]["published_time"], "2026-09-01T18:00:00Z")
        self.assertNotIn("news-secret", json.dumps(result))
        self.assertEqual(calls[0]["params"]["q"], '"AAPL"')

    def test_finnhub_normalizes_company_news(self) -> None:
        def fake_get(url: str, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                status_code=200,
                text=json.dumps(
                    [
                        {
                            "id": 42,
                            "category": "company",
                            "datetime": 1788285600,
                            "headline": "AAPL launches product",
                            "image": "",
                            "related": "AAPL",
                            "source": "Finnhub Wire",
                            "summary": "Product update",
                            "url": "https://news.example/product",
                        }
                    ]
                ),
                headers={"content-type": "application/json"},
            )

        result = FinnhubNewsClient(
            api_key="finnhub-secret",
            http_getter=fake_get,
            live_enabled=True,
            min_interval_s=0.0,
        ).fetch_news("AAPL")

        self.assertTrue(result["success"])
        self.assertEqual(result["items"][0]["provider"], "FINNHUB")
        self.assertEqual(result["items"][0]["provider_news_id"], "finnhub:42")
        self.assertEqual(result["items"][0]["tickers"], ["AAPL"])
        self.assertNotIn("finnhub-secret", json.dumps(result))

    def test_disabled_provider_does_not_call_transport(self) -> None:
        calls = 0

        def fake_get(*args: object, **kwargs: object) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            raise AssertionError("disabled provider called transport")

        result = NewsApiClient(
            api_key="news-secret",
            http_getter=fake_get,
            live_enabled=False,
            min_interval_s=0.0,
        ).fetch_news("AAPL")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "LIVE_DISABLED")
        self.assertEqual(calls, 0)

    def test_aggregate_deduplicates_and_preserves_provider_provenance(self) -> None:
        items = [
            {
                "headline": "AAPL reports results",
                "published_time": "2026-09-01T18:00:00Z",
                "url": "https://news.example/aapl",
                "provider": "NEWSAPI",
                "provider_news_id": "newsapi:aapl",
                "publisher_source": "Wire News",
            },
            {
                "headline": "AAPL reports results",
                "published_time": "2026-09-01T18:00:00Z",
                "url": "https://news.example/aapl",
                "provider": "FINNHUB",
                "provider_news_id": "finnhub:99",
                "publisher_source": "Finnhub Wire",
            },
        ]

        merged = aggregate_news_items(items)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["provider"], "NEWS_AGGREGATE")
        self.assertEqual(merged[0]["providers"], ["FINNHUB", "NEWSAPI"])
        self.assertEqual(
            merged[0]["provider_news_ids"],
            ["finnhub:99", "newsapi:aapl"],
        )
        self.assertEqual(len(merged[0]["source_provenance"]), 2)


if __name__ == "__main__":
    unittest.main()
