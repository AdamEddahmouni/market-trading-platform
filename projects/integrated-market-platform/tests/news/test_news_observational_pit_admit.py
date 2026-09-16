"""PIT clocks + pipeline rejections for observational news admit."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_platform_foundation.intelligence.observation_ingress.production_wire import (
    build_production_observation_ingress_router,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.news.event_v1 import news_article_to_event_v1
from market_platform_foundation.news.normalize import normalize_finviz_export_item
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    CLASS_SUCCESS,
    ProspectiveCatalystIngressResult,
)
from market_platform_foundation.news.observational_admit import (
    admit_finviz_export_item_for_observation,
    admit_prospective_catalyst_ingress_result,
    validate_news_pit_clocks,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.opportunity_projections import (
    LIVE_OBSERVATIONAL_OPERATOR_ACCOUNT,
    apply_opportunity_ack,
)
from market_platform_foundation.ui_api.operator_opportunity_state import list_operator_acks, reset_operator_acks
from market_platform_foundation.ui_api.news_ingest import handle_news_ingest_post
from market_platform_foundation.ui_api.trade_review_projections import (
    build_trade_reviews_for_opportunity_payload,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.rt01.execution_decision_trace.runtime import (
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)

from tests.ui1.test_ui_api import COLLECTION_ROOT

_SERVER = "2026-09-15T14:00:10Z"
_RETRIEVED = "2026-09-15T14:00:08Z"
_PUBLISHED = "2026-09-15T14:00:05Z"
_JULY_PUBLISHED = "2026-07-21T15:00:00Z"


def _item(*, published: str = _PUBLISHED, headline: str = "Example Corp reports quarterly earnings") -> dict:
    return {
        "headline": headline,
        "published_time": published,
        "url": "https://example.com/story",
        "tickers": ["AAPL"],
        "provider_native_id": "fv-pit-1",
    }


class NewsObservationalPitAdmitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._persist_env_patch = patch.dict(
            os.environ,
            {"IMP_PERSIST_STATE": "0", "IMP_STATE_DIR": ""},
            clear=False,
        )
        self._persist_env_patch.start()
        reset_operator_acks()
        reset_execution_decision_trace_runtime_for_tests()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        bind_ui_api_intelligence(self.store)
        self.server_ns = int(epoch_ns_from_iso(_SERVER))
        self._clock_patch = patch(
            "market_platform_foundation.ui_api.news_ingest.monotonic_wall_ns",
            return_value=self.server_ns,
        )
        self._clock_patch.start()
        self._admit_clock_patch = patch(
            "market_platform_foundation.news.observational_admit.monotonic_wall_ns",
            return_value=self.server_ns,
        )
        self._admit_clock_patch.start()

    def tearDown(self) -> None:
        self._admit_clock_patch.stop()
        self._clock_patch.stop()
        self._persist_env_patch.stop()

    def test_server_receive_differs_from_client_retrieved(self) -> None:
        article = normalize_finviz_export_item(_item(), retrieved_time=_RETRIEVED)
        event = news_article_to_event_v1(article, server_received_time_ns=self.server_ns)
        self.assertEqual(event.available_time_ns, epoch_ns_from_iso(_RETRIEVED))
        self.assertEqual(event.received_time_ns, self.server_ns)
        self.assertNotEqual(event.received_time_ns, event.available_time_ns)

    def test_publication_after_retrieval_rejected(self) -> None:
        article = normalize_finviz_export_item(
            _item(published="2026-09-15T14:00:12Z"),
            retrieved_time=_RETRIEVED,
        )
        self.assertEqual(
            validate_news_pit_clocks(article, server_received_time_ns=self.server_ns),
            "NEWS_PUBLICATION_AFTER_RETRIEVAL",
        )

    def test_july_publication_with_now_retrieve_rejected_by_pipeline(self) -> None:
        router = build_production_observation_ingress_router(InMemoryIntelligenceRepository())
        outcome = admit_finviz_export_item_for_observation(
            _item(published=_JULY_PUBLISHED),
            retrieved_time=_RETRIEVED,
            router=router,
            server_received_time_ns=self.server_ns,
        )
        self.assertFalse(outcome.accepted)
        self.assertIn(
            str(outcome.reason_code),
            {"RECENCY_EXCEEDS_TTL", "NEWS_PIPELINE_REJECTED"},
        )

    def test_july_retrieve_as_live_does_not_ready_cockpit(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _JULY_PUBLISHED,
                "articles": [_item(published=_JULY_PUBLISHED)],
            },
        )
        self.assertEqual(payload["admitted_count"], 0)
        self.assertGreaterEqual(payload["skipped_count"], 1)

    def test_watch_after_lawful_admit_without_broker_execution(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {"retrieved_time": _RETRIEVED, "articles": [_item()]},
        )
        self.assertEqual(payload["opportunity_count"], 1)
        opp_id = payload["opportunity_ids"][0]
        ack = apply_opportunity_ack(self.store, row_id=opp_id, action="WATCHED")
        self.assertEqual(ack["action"], "WATCHED")
        self.assertIn("trade_review_id", ack)
        traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(opp_id)
        self.assertTrue(any(row.mode == "LIVE_OBSERVATIONAL" for row in traces))
        acks = list_operator_acks(paper_account_id=LIVE_OBSERVATIONAL_OPERATOR_ACCOUNT)
        self.assertEqual(len(acks), 1)

    def test_prospective_ingress_receipt_row_admits_event_v1(self) -> None:
        router = self.store.observation_ingress_router
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=True,
            reason=None,
            source_label="live:finviz_elite_prospective",
            rows=(
                {
                    "symbol": "AAPL",
                    "headline": "Example Corp reports quarterly earnings",
                    "published_time": _PUBLISHED,
                    "retrieved_time": _RETRIEVED,
                    "source_event_id": "evt-prospective-1",
                },
            ),
            stats={"as_of_ns": self.server_ns},
            classification=CLASS_SUCCESS,
        )
        outcomes = admit_prospective_catalyst_ingress_result(
            ingress,
            router=router,
            store=self.store,
        )
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0].accepted)
        self.assertIsNotNone(outcomes[0].event)
        assert outcomes[0].event is not None
        self.assertEqual(outcomes[0].event.received_time_ns, self.server_ns)
        self.assertNotEqual(outcomes[0].event.received_time_ns, outcomes[0].event.available_time_ns)

    def test_post_rejects_forged_server_receive_time(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            handle_news_ingest_post(
                self.store,
                {
                    "retrieved_time": _RETRIEVED,
                    "server_received_time_ns": self.server_ns,
                    "articles": [_item()],
                },
            )
        self.assertEqual(str(ctx.exception), "NEWS_INGEST_FORGED_SERVER_RECEIVE_TIME")

    def test_watch_trade_review_readable_on_live_observational(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {"retrieved_time": _RETRIEVED, "articles": [_item()]},
        )
        opp_id = payload["opportunity_ids"][0]
        apply_opportunity_ack(self.store, row_id=opp_id, action="WATCHED")
        reviews = build_trade_reviews_for_opportunity_payload(self.store, opp_id)
        self.assertEqual(len(reviews["items"]), 1)
        self.assertNotIn("reason", reviews)

    def test_duplicate_watch_fail_closed(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {"retrieved_time": _RETRIEVED, "articles": [_item()]},
        )
        opp_id = payload["opportunity_ids"][0]
        apply_opportunity_ack(self.store, row_id=opp_id, action="WATCHED")
        with self.assertRaises(PermissionError) as ctx:
            apply_opportunity_ack(self.store, row_id=opp_id, action="WATCHED")
        self.assertEqual(str(ctx.exception), "LIVE_OBSERVATIONAL_OPERATOR_ACK_DUPLICATE")


if __name__ == "__main__":
    unittest.main()
