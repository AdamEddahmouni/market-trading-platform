"""UiApiHandler request-path Finviz/news → EventV1 → observational OpportunityV1."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.news.event_v1 import news_article_to_event_v1
from market_platform_foundation.news.normalize import normalize_finviz_export_item
from market_platform_foundation.news.observational_opportunity import (
    build_observational_news_opportunity,
    observational_news_opportunity_id,
    qualifies_observational_news_opportunity,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import (
    NEWS_INGEST_MAX_BODY_BYTES,
    NEWS_INGEST_ROUTE,
    handle_news_ingest_post,
)
from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.projections import LIVE_AS_OF_UNAVAILABLE, build_attention_page
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"


def _raw_article(*, headline: str, tickers: list[str] | None = None) -> dict:
    return {
        "headline": headline,
        "published_time": _PUBLISHED,
        "url": "https://example.com/story",
        "tickers": tickers if tickers is not None else ["AAPL"],
        "publisher_source": "Wire",
        "provider_native_id": "fv-news-path-1",
    }


class ObservationalNewsOpportunityUnitTests(unittest.TestCase):
    def test_zero_qualifying_headline_does_not_mint(self) -> None:
        article = normalize_finviz_export_item(
            _raw_article(headline="Example Corp beats estimates"),
            retrieved_time=_RETRIEVED,
        )
        event = news_article_to_event_v1(article)
        self.assertNotEqual(event.event_time_ns, event.available_time_ns)
        self.assertEqual(event.event_time_ns, epoch_ns_from_iso(_PUBLISHED))
        self.assertEqual(event.available_time_ns, epoch_ns_from_iso(_RETRIEVED))
        self.assertFalse(qualifies_observational_news_opportunity(event))
        self.assertIsNone(build_observational_news_opportunity(event))

    def test_catalyst_and_instrument_mint_observational_opportunity(self) -> None:
        article = normalize_finviz_export_item(
            _raw_article(headline="Example Corp reports quarterly earnings"),
            retrieved_time=_RETRIEVED,
        )
        event = news_article_to_event_v1(article)
        opportunity = build_observational_news_opportunity(event)
        self.assertIsNotNone(opportunity)
        assert opportunity is not None
        self.assertEqual(opportunity.opportunity_id, observational_news_opportunity_id(event.event_id))
        self.assertEqual(opportunity.scope.instrument_ids, ("AAPL",))
        self.assertIsNone(opportunity.side)
        self.assertFalse(opportunity.metadata.get("live_authority"))
        self.assertEqual(opportunity.lineage_refs[0].id, event.event_id)


class NewsIngestRequestPathTests(unittest.TestCase):
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

    def test_handler_admits_put_event_and_zero_qualifying_stays_empty(self) -> None:
        repo = self.store.strategy_repository
        self.assertIsNotNone(repo)
        with patch.object(InMemoryIntelligenceRepository, "put_event", wraps=repo.put_event) as put_event:
            payload = handle_news_ingest_post(
                self.store,
                {"retrieved_time": _RETRIEVED, "articles": [_raw_article(headline="Example Corp beats estimates")]},
            )
        put_event.assert_called_once()
        self.assertEqual(payload["admitted_count"], 1)
        self.assertEqual(payload["opportunity_count"], 0)
        self.assertEqual(payload["zero_qualifying_count"], 1)
        self.assertFalse(payload["auto_fetch"])
        self.assertFalse(payload["live_authority"])
        event_id = payload["events"][0]["event_id"]
        stored = repo.get_event(event_id)
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored.event_time_ns, stored.available_time_ns)
        summary = build_opportunities_summary_payload(self.store)
        self.assertEqual(summary["feed_status"], "EMPTY")
        self.assertEqual(summary["items"], [])
        self.assertNotIn("2026-07-21", str(summary["as_of_context"]["as_of_time"]))

    def test_qualifying_news_ranks_without_fixture_cards_and_mutations_stay_blocked(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [_raw_article(headline="Example Corp reports quarterly earnings")],
            },
        )
        self.assertEqual(payload["admitted_count"], 1)
        self.assertEqual(payload["opportunity_count"], 1)
        self.assertEqual(payload["events"][0]["detector_detail"], "NEWS_ARTICLE_OPPORTUNITY_MINTED")
        summary = build_opportunities_summary_payload(self.store)
        self.assertEqual(summary["feed_status"], "READY")
        self.assertNotEqual(summary["as_of_context"]["as_of_time"], LIVE_AS_OF_UNAVAILABLE)
        self.assertNotIn("2026-07-21", str(summary["as_of_context"]["as_of_time"]))
        self.assertEqual(len(summary["items"]), 1)
        self.assertEqual(summary["items"][0]["identity_kind"], "OPPORTUNITY_V1")
        self.assertEqual(summary["items"][0]["instrument_id"], "AAPL")
        self.assertFalse(
            any(row.get("attention_id") == "att-replay-context" for row in summary["items"])
        )
        attention = build_attention_page(self.store, limit=50)
        current_ids = [item.get("attention_id") for item in (attention.get("items") or [])]
        self.assertNotIn("att-replay-context", current_ids)
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id=payload["opportunity_ids"][0], action="WATCHED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")


class NewsIngestHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        bind_ui_api_intelligence(self.store)
        UiApiHandler.store = self.store
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._runtime_patch.start()
        self._auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        self._auth_patch.start()

    def tearDown(self) -> None:
        self._auth_patch.stop()
        self._runtime_patch.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _request(self, method: str, path: str, *, body: bytes, content_length: int | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"}
        headers["Content-Length"] = str(content_length if content_length is not None else len(body))
        conn.request(method, path, body=body, headers=headers)
        return conn.getresponse()

    def test_http_post_admits_event_v1_then_summary_is_ready(self) -> None:
        body = json.dumps(
            {
                "retrieved_time": _RETRIEVED,
                "articles": [_raw_article(headline="Example Corp reports quarterly earnings")],
            }
        ).encode("utf-8")
        response = self._request("POST", NEWS_INGEST_ROUTE, body=body)
        self.assertEqual(response.status, 200)
        ingest = json.loads(response.read().decode("utf-8"))
        self.assertEqual(ingest["admitted_count"], 1)
        self.assertEqual(ingest["opportunity_count"], 1)
        event_id = ingest["events"][0]["event_id"]
        stored = self.store.strategy_repository.get_event(event_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.event_type, "NEWS_ARTICLE")
        self.assertNotEqual(stored.event_time_ns, stored.available_time_ns)
        summary = build_opportunities_summary_payload(self.store)
        self.assertEqual(summary["feed_status"], "READY")
        self.assertEqual(summary["items"][0]["opportunity_id"], ingest["opportunity_ids"][0])
        ack = self._request(
            "POST",
            f"/opportunities/{ingest['opportunity_ids'][0]}/watch",
            body=b"{}",
        )
        self.assertEqual(ack.status, 403)
        denied = json.loads(ack.read().decode("utf-8"))
        self.assertIn("LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE", str(denied))

    def test_http_post_rejects_oversized_body(self) -> None:
        response = self._request(
            "POST",
            NEWS_INGEST_ROUTE,
            body=b"{}",
            content_length=NEWS_INGEST_MAX_BODY_BYTES + 1,
        )
        self.assertEqual(response.status, 413)


if __name__ == "__main__":
    unittest.main()
