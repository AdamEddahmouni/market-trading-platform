"""NewsAggregator → NewsArticleEvent bridge tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.aggregator_bridge import (  # noqa: E402
    aggregator_item_to_event,
    received_time_to_retrieved_iso,
)


class AggregatorBridgeTests(unittest.TestCase):
    def test_received_time_ns_maps_to_retrieved_iso(self) -> None:
        iso = received_time_to_retrieved_iso(1_700_000_000_000_000_000)
        self.assertTrue(iso.endswith("Z"))

    def test_aggregator_item_preserves_separate_times(self) -> None:
        item = {
            "provider": "finviz",
            "provider_news_id": "fv-1",
            "headline": "Example headline",
            "published_time": "2024-01-15T14:30:00Z",
            "received_time": "2024-01-15T14:30:05Z",
            "url": "https://example.com/news/1",
            "tickers": ["ACME"],
        }
        event = aggregator_item_to_event(item)
        self.assertEqual(event.retrieved_time, "2024-01-15T14:30:05Z")
        self.assertEqual(event.published_time, "2024-01-15T14:30:00Z")
        self.assertEqual(event.provider_id, "finviz")


if __name__ == "__main__":
    unittest.main()
