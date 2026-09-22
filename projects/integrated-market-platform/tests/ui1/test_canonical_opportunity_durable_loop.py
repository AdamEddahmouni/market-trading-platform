"""Software-controlled EventV1 → OpportunityV1 durable loop (not market evidence)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from market_platform_foundation.intelligence.live_execution_safety.preflight_controls import (
    evaluate_live_preflight_bundle,
)
from market_platform_foundation.intelligence.opportunity.engine import OpportunityEngine
from market_platform_foundation.intelligence.persistence import (
    LocalStateIntelligenceRepository,
    opportunity_book_storage,
    reset_local_state_intelligence_repository_for_tests,
)
from market_platform_foundation.intelligence.trade_review import (
    TradeReviewMode,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.intelligence.trade_review.store import open_trade_review_repository
from market_platform_foundation.local_state.schema import SCHEMA_VERSION
from market_platform_foundation.local_state.startup import open_local_state, reset_local_state_for_tests
from market_platform_foundation.news.contracts import (
    InstrumentLinkage,
    NewsArticleEvent,
    PublicationTimeQuality,
)
from market_platform_foundation.news.observational_admit import admit_news_article_for_observation
from market_platform_foundation.news.observational_opportunity import (
    qualifies_observational_news_opportunity,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.rt01.execution_decision_trace import ExecutionDecisionKind
from market_platform_foundation.rt01.execution_decision_trace.runtime import (
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import handle_news_ingest_post
from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import (
    list_operator_acks,
    reset_operator_acks,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"
_SERVER = "2026-09-15T14:05:10Z"
_T = int(epoch_ns_from_iso(_SERVER) or 0)


def _article(*, headline: str, native_id: str, tickers: list[str] | None = None) -> dict:
    return {
        "headline": headline,
        "published_time": _PUBLISHED,
        "url": f"https://example.com/{native_id}",
        "tickers": tickers if tickers is not None else ["AAPL"],
        "publisher_source": "Wire",
        "provider_native_id": native_id,
    }


class CanonicalOpportunityDurableLoopTests(unittest.TestCase):
    """Controlled fixture path through production ingress. Not prospective/Paper/Live proof."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reset_local_state_intelligence_repository_for_tests()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.opportunity_source = "FIXTURE"
        self.store.execution_mode = "INTERNAL_SIMULATION"
        bind_ui_api_intelligence(self.store)
        self._clock_patch = patch(
            "market_platform_foundation.ui_api.news_ingest.monotonic_wall_ns",
            return_value=_T,
        )
        self._admit_clock_patch = patch(
            "market_platform_foundation.news.observational_admit.monotonic_wall_ns",
            return_value=_T,
        )
        self._clock_patch.start()
        self._admit_clock_patch.start()

    def tearDown(self) -> None:
        self._admit_clock_patch.stop()
        self._clock_patch.stop()
        reset_trade_review_repository_for_tests()
        reset_local_state_intelligence_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        self._tmp.cleanup()

    def _restart_store(self) -> ReplayStore:
        reset_local_state_intelligence_repository_for_tests()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        restarted = ReplayStore(collection_root=COLLECTION_ROOT)
        restarted.load()
        restarted.opportunity_source = "FIXTURE"
        restarted.execution_mode = "INTERNAL_SIMULATION"
        bind_ui_api_intelligence(restarted)
        return restarted

    def test_schema_v9_intelligence_book_tables(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(SCHEMA_VERSION, 9)
        self.assertEqual(local.connection.schema_version(), 9)
        tables = {
            str(row[0])
            for row in local.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("intelligence_events", tables)
        self.assertIn("intelligence_opportunities", tables)
        self.assertEqual(opportunity_book_storage(), "DURABLE_SQLITE")

    def test_valid_provider_like_event_admitted_and_minted(self) -> None:
        self.assertIsInstance(self.store.strategy_repository, LocalStateIntelligenceRepository)
        with patch.object(OpportunityEngine, "assess") as assess:
            payload = handle_news_ingest_post(
                self.store,
                {
                    "retrieved_time": _RETRIEVED,
                    "articles": [
                        _article(
                            headline="Example Corp reports quarterly earnings",
                            native_id="fv-durable-valid",
                        )
                    ],
                },
            )
        assess.assert_not_called()
        self.assertEqual(payload["admitted_count"], 1)
        self.assertEqual(payload["opportunity_count"], 1)
        self.assertFalse(payload["live_authority"])
        self.assertEqual(payload["news_event_build09"], "INACTIVE")
        self.assertEqual(payload["events"][0]["detector_detail"], "NEWS_ARTICLE_OPPORTUNITY_MINTED")
        event_id = payload["events"][0]["event_id"]
        stored = self.store.strategy_repository.get_event(event_id)
        self.assertIsNotNone(stored)
        opportunity_id = payload["opportunity_ids"][0]
        minted = self.store.strategy_repository.get_opportunity(opportunity_id)
        self.assertIsNotNone(minted)
        assert minted is not None
        self.assertEqual(minted.metadata.get("news_event_build09"), "INACTIVE")
        self.assertFalse(minted.metadata.get("live_authority"))
        self.assertEqual(self.store.opportunity_source, "FIXTURE")
        summary = build_opportunities_summary_payload(self.store)
        ids = [item.get("opportunity_id") for item in summary["items"]]
        self.assertIn(opportunity_id, ids)

    def test_malformed_item_and_missing_source_rejected(self) -> None:
        malformed = handle_news_ingest_post(
            self.store,
            {"retrieved_time": _RETRIEVED, "articles": ["not-an-object"]},
        )
        self.assertEqual(malformed["admitted_count"], 0)
        self.assertEqual(malformed["skipped"][0]["reason"], "NEWS_INGEST_ITEM_NOT_OBJECT")
        missing_retrieved = handle_news_ingest_post(
            self.store,
            {"articles": [_article(headline="Example Corp reports quarterly earnings", native_id="fv-no-retr")]},
        )
        self.assertEqual(missing_retrieved["admitted_count"], 0)
        self.assertEqual(missing_retrieved["skipped"][0]["reason"], "NEWS_RETRIEVED_TIME_REQUIRED")
        article = NewsArticleEvent(
            event_id="missing-source-1",
            provider_id="unknown-provider",
            provider_native_id="u-1",
            source_id="",
            published_time=_PUBLISHED,
            published_time_quality=PublicationTimeQuality.KNOWN,
            retrieved_time=_RETRIEVED,
            headline="Example Corp reports quarterly earnings",
            instrument_linkages=(InstrumentLinkage(instrument_id="AAPL", provider_symbol="AAPL", asset_class="EQUITY"),),
            publisher_source="",
        )
        outcome = admit_news_article_for_observation(
            article,
            router=self.store.observation_ingress_router,
            store=self.store,
            server_received_time_ns=_T,
        )
        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.reason_code, "SOURCE_UNKNOWN")

    def test_pit_violation_rejected(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": "2026-09-15T14:05:20Z",
                "articles": [
                    _article(
                        headline="Example Corp reports quarterly earnings",
                        native_id="fv-pit",
                    )
                ],
            },
        )
        self.assertEqual(payload["admitted_count"], 0)
        self.assertEqual(payload["skipped"][0]["reason"], "NEWS_RETRIEVED_AFTER_SERVER_RECEIVE")

    def test_duplicate_event_does_not_fork_identity(self) -> None:
        body = {
            "retrieved_time": _RETRIEVED,
            "articles": [
                _article(
                    headline="Example Corp reports quarterly earnings",
                    native_id="fv-dup",
                )
            ],
        }
        first = handle_news_ingest_post(self.store, body)
        second = handle_news_ingest_post(self.store, body)
        self.assertEqual(first["opportunity_ids"], second["opportunity_ids"])
        self.assertEqual(first["events"][0]["event_id"], second["events"][0]["event_id"])
        listed = self.store.strategy_repository.list_opportunities()
        matching = [row for row in listed if row.opportunity_id == first["opportunity_ids"][0]]
        self.assertEqual(len(matching), 1)

    def test_qualifying_vs_non_qualifying_detector_deterministic(self) -> None:
        non_catalyst = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [
                    _article(
                        headline="Example Corp beats estimates",
                        native_id="fv-nonqual",
                    )
                ],
            },
        )
        self.assertEqual(non_catalyst["admitted_count"], 0)
        self.assertGreaterEqual(non_catalyst["skipped_count"], 1)
        admitted_no_instrument = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [
                    _article(
                        headline="Example Corp reports quarterly earnings",
                        native_id="fv-no-inst",
                        tickers=[],
                    )
                ],
            },
        )
        self.assertEqual(admitted_no_instrument["admitted_count"], 1)
        self.assertEqual(admitted_no_instrument["opportunity_count"], 0)
        self.assertEqual(
            admitted_no_instrument["events"][0]["detector_detail"],
            "NEWS_ARTICLE_ADMITTED",
        )
        event = self.store.strategy_repository.get_event(admitted_no_instrument["events"][0]["event_id"])
        self.assertIsNotNone(event)
        self.assertFalse(qualifies_observational_news_opportunity(event))
        qualifying = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [
                    _article(
                        headline="Example Corp reports quarterly earnings",
                        native_id="fv-qual",
                    )
                ],
            },
        )
        self.assertEqual(qualifying["opportunity_count"], 1)
        self.assertEqual(qualifying["events"][0]["detector_detail"], "NEWS_ARTICLE_OPPORTUNITY_MINTED")

    def test_persist_restart_ranked_watch_dismiss_trace_review(self) -> None:
        watch_payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [
                    _article(
                        headline="Example Corp reports quarterly earnings",
                        native_id="fv-watch",
                    )
                ],
            },
        )
        dismiss_payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [
                    _article(
                        headline="Peer Co announces quarterly earnings call",
                        native_id="fv-dismiss",
                        tickers=["MSFT"],
                    )
                ],
            },
        )
        watch_id = watch_payload["opportunity_ids"][0]
        dismiss_id = dismiss_payload["opportunity_ids"][0]
        self.assertNotEqual(watch_id, dismiss_id)
        watch_ack = apply_opportunity_ack(self.store, row_id=watch_id, action="WATCHED")
        dismiss_ack = apply_opportunity_ack(self.store, row_id=dismiss_id, action="DISMISSED")
        self.assertEqual(watch_ack["action"], "WATCHED")
        self.assertEqual(dismiss_ack["action"], "DISMISSED")
        self.assertIn("trade_review_id", watch_ack)
        self.assertIn("trade_review_id", dismiss_ack)

        before = build_opportunities_summary_payload(self.store)
        before_ids = [item.get("opportunity_id") for item in before["items"]]
        self.assertIn(watch_id, before_ids)
        self.assertNotIn(dismiss_id, before_ids)

        restarted = self._restart_store()
        self.assertIsInstance(restarted.strategy_repository, LocalStateIntelligenceRepository)
        self.assertIsNotNone(restarted.strategy_repository.get_opportunity(watch_id))
        self.assertIsNotNone(restarted.strategy_repository.get_opportunity(dismiss_id))
        after = build_opportunities_summary_payload(restarted)
        after_ids = [item.get("opportunity_id") for item in after["items"]]
        self.assertIn(watch_id, after_ids)
        self.assertEqual(after_ids.count(watch_id), 1)
        self.assertNotIn(dismiss_id, after_ids)

        acks = {(row["opportunity_id"], row["action"]) for row in list_operator_acks()}
        self.assertIn((watch_id, "WATCHED"), acks)
        self.assertIn((dismiss_id, "DISMISSED"), acks)

        traces = execution_decision_trace_repository()
        watch_traces = traces.list_execution_decision_traces_by_opportunity(watch_id)
        dismiss_traces = traces.list_execution_decision_traces_by_opportunity(dismiss_id)
        self.assertTrue(any(row.decision_kind == ExecutionDecisionKind.WATCH for row in watch_traces))
        self.assertTrue(any(row.decision_kind == ExecutionDecisionKind.DISMISS for row in dismiss_traces))

        reviews = open_trade_review_repository()
        watch_reviews = reviews.list_trade_reviews_by_opportunity(watch_id)
        dismiss_reviews = reviews.list_trade_reviews_by_opportunity(dismiss_id)
        self.assertEqual(len(watch_reviews), 1)
        self.assertEqual(len(dismiss_reviews), 1)
        self.assertEqual(watch_reviews[0].review_mode, TradeReviewMode.WATCHED_OPPORTUNITY)
        self.assertEqual(dismiss_reviews[0].review_mode, TradeReviewMode.REJECTED_OPPORTUNITY)
        for review in (*watch_reviews, *dismiss_reviews):
            self.assertIsNone(review.execution_attribution)
            body = review.metadata or {}
            self.assertNotIn("fill", str(body).lower())
            self.assertNotIn("pnl", str(body).lower())
            self.assertNotIn("p&l", str(body).lower())

    def test_live_network_submit_still_false(self) -> None:
        report = evaluate_live_preflight_bundle(
            reference_price_minor=150_00,
            quote_as_of_ns=_T - 100,
            decision_time_ns=_T,
            max_quote_age_ns=1_000_000_000,
            quantity=1,
            max_quantity=10,
            required_notional_minor=150_00,
            buying_power_minor=1_000_000,
            session_state="RTH_OPEN",
            side="BUY",
            order_type="MARKET",
            limit_price_minor=None,
            confirmation_present=True,
            confirmation_expired=False,
            confirmation_matches_intent=True,
        )
        self.assertFalse(report.allows_network_submit)
        codes = {finding.reason_code for finding in report.findings}
        self.assertIn("BUILD28_LIVE_SUBMIT_FORBIDDEN", codes)


if __name__ == "__main__":
    unittest.main()
