"""Finviz NewsArticleEvent → EventV1 mapper and helper used by the request path."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from market_platform_foundation.intelligence.observation_ingress.consumers import (
    accepts_news_article_event,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.news.event_v1 import NEWS_EVENT_TYPE, news_article_to_event_v1
from market_platform_foundation.news.event_v1_ingress import admit_news_article_event
from market_platform_foundation.news.normalize import normalize_finviz_export_item
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.projections import LIVE_AS_OF_UNAVAILABLE, build_attention_page
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"


def _sample_article():
    return normalize_finviz_export_item(
        {
            "headline": "Example Corp beats estimates",
            "published_time": _PUBLISHED,
            "url": "https://example.com/story",
            "tickers": ["AAPL"],
            "publisher_source": "Wire",
            "provider_native_id": "fv-news-1",
        },
        retrieved_time=_RETRIEVED,
    )


class FinvizNewsEventV1IngressTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        bind_ui_api_intelligence(self.store)
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._runtime_patch.start()

    def tearDown(self) -> None:
        self._runtime_patch.stop()

    def test_news_article_maps_pit_clocks_without_conflating_publication(self) -> None:
        article = _sample_article()
        event = news_article_to_event_v1(article)
        published_ns = epoch_ns_from_iso(_PUBLISHED)
        retrieved_ns = epoch_ns_from_iso(_RETRIEVED)
        self.assertEqual(event.event_type, NEWS_EVENT_TYPE)
        self.assertEqual(event.event_time_ns, published_ns)
        self.assertEqual(event.provider_time_ns, published_ns)
        self.assertEqual(event.available_time_ns, retrieved_ns)
        self.assertEqual(event.received_time_ns, retrieved_ns)
        self.assertNotEqual(event.event_time_ns, event.available_time_ns)
        self.assertTrue(accepts_news_article_event(event))

    def test_ftep_news_helper_dispatches_put_event_once_and_detector_is_not_observed_noop(self) -> None:
        # Helper used by POST /intelligence/ingest/news. Zero-qualifying stays admitted EventV1.
        article = _sample_article()
        repo = self.store.strategy_repository
        self.assertIsNotNone(repo)
        with patch.object(InMemoryIntelligenceRepository, "put_event", wraps=repo.put_event) as put_event:
            event, receipt = admit_news_article_event(
                article,
                router=self.store.observation_ingress_router,
                store=self.store,
            )
        put_event.assert_called_once()
        stored = repo.get_event(event.event_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.event_type, NEWS_EVENT_TYPE)
        detector_rows = [
            row for row in receipt.outcomes if str(row.kind) == "DETECTOR"
        ]
        self.assertEqual(len(detector_rows), 1)
        self.assertEqual(detector_rows[0].detail, "NEWS_ARTICLE_ADMITTED")
        self.assertNotEqual(detector_rows[0].detail, "OBSERVED")
        self.assertEqual(self.store.last_source_time_ns, event.received_time_ns)

    def test_zero_qualifying_news_does_not_substitute_fixture_ranked_book(self) -> None:
        article = _sample_article()
        admit_news_article_event(
            article,
            router=self.store.observation_ingress_router,
            store=self.store,
        )
        payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "EMPTY")
        self.assertEqual(payload["items"], [])
        self.assertNotEqual(payload["as_of_context"]["as_of_time"], LIVE_AS_OF_UNAVAILABLE)
        self.assertNotIn("2026-07-21", str(payload["as_of_context"]["as_of_time"]))
        attention = build_attention_page(self.store, limit=50)
        current_ids = [item.get("attention_id") for item in (attention.get("items") or [])]
        self.assertNotIn("att-replay-context", current_ids)
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id="any-id", action="WATCHED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")


if __name__ == "__main__":
    unittest.main()
