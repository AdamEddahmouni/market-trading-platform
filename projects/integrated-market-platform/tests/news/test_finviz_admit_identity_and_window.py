"""SOFTWARE_CONTROLLED / FIXTURE — Finviz admit identity stability + window plumbing.

Never prospective market evidence. Covers:
- process-stable provider_news_id / event_id / opportunity_id
- prospective body builder → handle_news_ingest_post ingestion_mode stamp
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_platform_foundation.finviz.news import parse_news_csv, stable_finviz_provider_news_id
from market_platform_foundation.intelligence.normalization.event_builder import provenance_from_event
from market_platform_foundation.intelligence.normalization.models import IngestionMode
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    CLASS_SUCCESS,
    ProspectiveCatalystIngressResult,
)
from market_platform_foundation.news.normalize import normalize_finviz_export_item
from market_platform_foundation.news.observational_opportunity import observational_news_opportunity_id
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.cockpit_admit import (
    build_news_ingest_body_from_prospective_ingress,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import handle_news_ingest_post
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

# SOFTWARE_CONTROLLED / FIXTURE clocks — not market evidence.
_WINDOW_START = "2026-09-22T15:07:24Z"
_PUBLISHED_AFTER = "2026-09-22T15:30:00Z"
_PUBLISHED_BEFORE = "2026-09-22T15:06:00Z"
_RETRIEVED = "2026-09-22T15:31:00Z"
_SERVER = "2026-09-22T15:31:05Z"

_LIVE_GATE_ENV = {
    "IMP_LIVE_OBSERVATIONAL": "1",
    "IMP_FINVIZ_LIVE": "1",
    "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
}

_CSV_ROW = (
    "Date,Title,Ticker,Url,Source\n"
    "2026-09-22 15:30:00,Example Corp reports quarterly earnings,AAPL,"
    "https://example.com/story-identity,Wire\n"
)


def _sample_ingress(*, published: str, headline: str = "Example Corp reports quarterly earnings") -> ProspectiveCatalystIngressResult:
    return ProspectiveCatalystIngressResult(
        attempted=True,
        ready=True,
        reason=None,
        source_label="live:finviz_elite_prospective",
        rows=(
            {
                "symbol": "AAPL",
                "headline": headline,
                "published_time": published,
                "retrieved_time": _RETRIEVED,
                "url": "https://example.com/story-identity",
                "source_event_id": "fv-stable-fixture-1",
            },
        ),
        stats={"as_of_ns": 1},
        classification=CLASS_SUCCESS,
    )


class FinvizStableIdentityTests(unittest.TestCase):
    """Identity must not depend on process-salted ``hash()``."""

    def test_stable_id_prefers_canonical_url_across_invocations(self) -> None:
        first = stable_finviz_provider_news_id(
            url="https://Example.com/story-identity/",
            headline="ignored when url present",
        )
        second = stable_finviz_provider_news_id(
            url="https://example.com/story-identity",
            headline="different headline must not diverge when url matches",
        )
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertTrue(str(first).startswith("finviz:"))
        # Must not be the old 8-hex process-salt pattern alone.
        self.assertGreaterEqual(len(str(first).split(":", 1)[1]), 16)

    def test_headline_fallback_is_salt_free_and_deterministic(self) -> None:
        a = stable_finviz_provider_news_id(headline="Example Corp reports quarterly earnings")
        b = stable_finviz_provider_news_id(headline="Example Corp reports quarterly earnings")
        self.assertEqual(a, b)
        self.assertIsNotNone(a)

    def test_missing_identity_inputs_fail_closed(self) -> None:
        self.assertIsNone(stable_finviz_provider_news_id(url="", headline=""))
        self.assertIsNone(stable_finviz_provider_news_id(url="not-a-url", headline=""))

    def test_parse_news_csv_stable_across_two_invocations(self) -> None:
        items_a, err_a = parse_news_csv(_CSV_ROW)
        items_b, err_b = parse_news_csv(_CSV_ROW)
        self.assertIsNone(err_a)
        self.assertIsNone(err_b)
        self.assertEqual(len(items_a), 1)
        self.assertEqual(items_a[0]["provider_news_id"], items_b[0]["provider_news_id"])
        article_a = normalize_finviz_export_item(items_a[0], retrieved_time=_RETRIEVED)
        article_b = normalize_finviz_export_item(items_b[0], retrieved_time=_RETRIEVED)
        self.assertEqual(article_a.event_id, article_b.event_id)
        self.assertEqual(
            observational_news_opportunity_id(article_a.event_id),
            observational_news_opportunity_id(article_b.event_id),
        )

    def test_distinct_urls_do_not_collapse(self) -> None:
        a = stable_finviz_provider_news_id(url="https://example.com/story-a", headline="Same")
        b = stable_finviz_provider_news_id(url="https://example.com/story-b", headline="Same")
        self.assertNotEqual(a, b)

    def test_distinct_headlines_without_url_do_not_collapse(self) -> None:
        a = stable_finviz_provider_news_id(headline="Alpha Corp reports quarterly earnings")
        b = stable_finviz_provider_news_id(headline="Beta Corp reports quarterly earnings")
        self.assertNotEqual(a, b)

    def test_normalize_rejects_empty_identity_material(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_finviz_export_item({}, retrieved_time=_RETRIEVED)
        self.assertEqual(str(ctx.exception), "NEWS_IDENTITY_INPUTS_REQUIRED")


class FinvizAdmitIdempotencyAndWindowTests(unittest.TestCase):
    """HTTP admit path — SOFTWARE_CONTROLLED / FIXTURE."""

    def setUp(self) -> None:
        self._persist_env_patch = patch.dict(
            os.environ,
            {"IMP_PERSIST_STATE": "0", "IMP_STATE_DIR": ""},
            clear=False,
        )
        self._persist_env_patch.start()
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

    def tearDown(self) -> None:
        self._clock_patch.stop()
        self._persist_env_patch.stop()

    def test_same_article_ingested_twice_does_not_grow_book(self) -> None:
        items, err = parse_news_csv(_CSV_ROW)
        self.assertIsNone(err)
        item = dict(items[0])
        body = {
            "retrieved_time": _RETRIEVED,
            "articles": [item],
        }
        first = handle_news_ingest_post(self.store, body)
        second = handle_news_ingest_post(self.store, body)
        self.assertEqual(first["admitted_count"], 1, first)
        self.assertEqual(first["events"][0]["event_id"], second["events"][0]["event_id"])
        self.assertEqual(first["opportunity_ids"], second["opportunity_ids"])
        opp_id = first["opportunity_ids"][0]
        listed = self.store.strategy_repository.list_opportunities()
        matching = [row for row in listed if row.opportunity_id == opp_id]
        self.assertEqual(len(matching), 1)

    def test_two_different_headlines_urls_two_ids(self) -> None:
        csv_text = (
            "Date,Title,Ticker,Url,Source\n"
            "2026-09-22 15:30:00,Example Corp reports quarterly earnings,AAPL,"
            "https://example.com/story-one,Wire\n"
            "2026-09-22 15:31:00,Other Corp announces guidance update,MSFT,"
            "https://example.com/story-two,Wire\n"
        )
        items, err = parse_news_csv(csv_text)
        self.assertIsNone(err)
        self.assertEqual(len(items), 2)
        self.assertNotEqual(items[0]["provider_news_id"], items[1]["provider_news_id"])
        payload = handle_news_ingest_post(
            self.store,
            {"retrieved_time": _RETRIEVED, "articles": items},
        )
        self.assertEqual(payload["admitted_count"], 2, payload)
        ids = {row["event_id"] for row in payload["events"]}
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(payload["opportunity_ids"])), 2)

    def test_prospective_body_builder_with_window_stamps_live_observed(self) -> None:
        body = build_news_ingest_body_from_prospective_ingress(
            _sample_ingress(published=_PUBLISHED_AFTER),
            observation_window_start=_WINDOW_START,
        )
        self.assertEqual(body.get("observation_window_start"), _WINDOW_START)
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(self.store, body)
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertEqual(payload["events"][0]["ingestion_mode"], IngestionMode.LIVE_OBSERVED.value)
        event = self.store.strategy_repository.get_event(payload["events"][0]["event_id"])
        provenance = provenance_from_event(event)
        assert provenance is not None
        self.assertEqual(provenance.ingestion_mode, IngestionMode.LIVE_OBSERVED)

    def test_prospective_body_publication_before_window_is_historical(self) -> None:
        body = build_news_ingest_body_from_prospective_ingress(
            _sample_ingress(
                published=_PUBLISHED_BEFORE,
                headline="Pre-arm historical headline earnings",
            ),
            observation_window_start=_WINDOW_START,
        )
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(self.store, body)
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertEqual(
            payload["events"][0]["ingestion_mode"],
            IngestionMode.HISTORICAL_RECONSTRUCTED.value,
        )

    def test_prospective_body_missing_window_not_live_observed(self) -> None:
        body = build_news_ingest_body_from_prospective_ingress(
            _sample_ingress(published=_PUBLISHED_AFTER),
        )
        self.assertNotIn("observation_window_start", body)
        self.assertNotIn("observation_window_start_ns", body)
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(self.store, body)
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertNotEqual(payload["events"][0]["ingestion_mode"], IngestionMode.LIVE_OBSERVED.value)

    def test_prospective_body_missing_publication_not_live_observed(self) -> None:
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=True,
            reason=None,
            source_label="live:finviz_elite_prospective",
            rows=(
                {
                    "symbol": "AAPL",
                    "headline": "Example Corp reports quarterly earnings",
                    "retrieved_time": _RETRIEVED,
                    "url": "https://example.com/story-identity",
                    "source_event_id": "fv-no-pub",
                },
            ),
            stats={},
            classification=CLASS_SUCCESS,
        )
        body = build_news_ingest_body_from_prospective_ingress(
            ingress,
            observation_window_start=_WINDOW_START,
        )
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(self.store, body)
        for row in payload["events"]:
            self.assertNotEqual(row.get("ingestion_mode"), IngestionMode.LIVE_OBSERVED.value)


if __name__ == "__main__":
    unittest.main()
