"""Observational live news ingress scaffolding (mocked providers only)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.aggregator import NewsAggregator  # noqa: E402
from market_platform_foundation.news.observational_ingress import (  # noqa: E402
    build_observational_aggregator,
    fetch_observational_news_events,
    observational_ingress_diagnostics,
    observational_ingress_ready,
)


class _StubNewsSource:
    provider_id = "stub"

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def fetch_news(self, symbol: str) -> dict[str, Any]:
        return {
            "success": True,
            "error": None,
            "items": self._items,
            "provider": self.provider_id,
        }


class ObservationalIngressTests(unittest.TestCase):
    def test_default_gates_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = fetch_observational_news_events("AAPL")
        self.assertFalse(result.enabled)
        self.assertEqual(result.reason, "INGRESS_DISABLED")
        self.assertEqual(result.events, ())

    def test_ingress_on_without_provider_gates(self) -> None:
        env = {"IMP_OBSERVATIONAL_NEWS_INGRESS": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            result = fetch_observational_news_events("AAPL")
        self.assertTrue(result.enabled)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason, "NO_LIVE_PROVIDER_GATES")

    def test_normalize_through_bridge_with_mock_aggregator(self) -> None:
        item = {
            "provider": "newsapi",
            "provider_news_id": "n-1",
            "headline": "Stub headline",
            "published_time": "2024-01-15T14:30:00Z",
            "received_time": "2024-01-15T14:30:05Z",
            "url": "https://example.com/news/1",
            "tickers": ["AAPL"],
        }
        aggregator = NewsAggregator(sources=(_StubNewsSource([item]),))
        env = {
            "IMP_OBSERVATIONAL_NEWS_INGRESS": "1",
            "IMP_NEWSAPI_LIVE": "1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(observational_ingress_ready())
            result = fetch_observational_news_events("AAPL", aggregator=aggregator)
        self.assertTrue(result.ready)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].retrieved_time, "2024-01-15T14:30:05Z")
        self.assertEqual(result.events[0].headline, "Stub headline")

    def test_build_aggregator_includes_only_live_gated_clients(self) -> None:
        env = {"IMP_NEWSAPI_LIVE": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            agg = build_observational_aggregator()
        self.assertEqual(len(agg._sources), 1)
        self.assertEqual(agg._sources[0].provider_id, "newsapi")

    def test_diagnostics_not_wired_to_forward_test(self) -> None:
        diag = observational_ingress_diagnostics()
        self.assertFalse(diag["wired_to_forward_test_bridge"])
        self.assertTrue(diag["campaign_connectivity_deferred"])


if __name__ == "__main__":
    unittest.main()
