"""Finviz export → NewsArticleEvent canonical contract tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.news.normalize import normalize_finviz_export_item


class FinvizNewsNormalizeTests(unittest.TestCase):
    def test_finviz_row_maps_to_canonical_event(self) -> None:
        row = {
            "headline": "Example Corp beats estimates",
            "published_time": "2026-09-12T14:30:00Z",
            "url": "https://example.com/story",
            "tickers": ["EXM"],
            "publisher_source": "Wire",
        }
        event = normalize_finviz_export_item(row, retrieved_time="2026-09-12T14:31:00Z")
        self.assertEqual(event.provider_id, "finviz")
        self.assertEqual(event.source_id, "finviz_elite")
        self.assertEqual(event.headline, row["headline"])
        self.assertEqual(len(event.instrument_linkages), 1)


if __name__ == "__main__":
    unittest.main()
