"""SOFTWARE_CONTROLLED / FIXTURE — Finviz HTTP ingest mode stamp selection.

Never prospective market evidence. Exercises only software-controlled clocks and
env gates against ``select_news_ingest_ingestion_mode`` / ``handle_news_ingest_post``.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_platform_foundation.intelligence.normalization.event_builder import provenance_from_event
from market_platform_foundation.intelligence.normalization.models import IngestionMode
from market_platform_foundation.news.contracts import PublicationTimeQuality
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import handle_news_ingest_post
from market_platform_foundation.ui_api.news_ingest_mode import (
    news_ingest_live_gates_active,
    parse_observation_window_start_ns,
    select_news_ingest_ingestion_mode,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

# SOFTWARE_CONTROLLED / FIXTURE clocks — not market evidence.
_WINDOW_START = "2026-09-22T15:07:24Z"
_PUBLISHED_AFTER = "2026-09-22T15:30:00Z"
# Slightly before arm so PIP/recency still admit, but mode stays historical.
_PUBLISHED_BEFORE = "2026-09-22T15:06:00Z"
_RETRIEVED = "2026-09-22T15:31:00Z"
_SERVER = "2026-09-22T15:31:05Z"

_LIVE_GATE_ENV = {
    "IMP_LIVE_OBSERVATIONAL": "1",
    "IMP_FINVIZ_LIVE": "1",
    "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
}


def _item(*, published: str | None, headline: str = "Example Corp reports quarterly earnings") -> dict:
    row: dict = {
        "headline": headline,
        "url": "https://example.com/story-mode",
        "tickers": ["AAPL"],
        "provider_native_id": "fv-mode-1",
    }
    if published is not None:
        row["published_time"] = published
    return row


class NewsIngestModeHelperTests(unittest.TestCase):
    """Pure mode rule — SOFTWARE_CONTROLLED / FIXTURE."""

    def test_live_gates_and_publication_at_or_after_window_is_live_observed(self) -> None:
        window_ns = epoch_ns_from_iso(_WINDOW_START)
        published_ns = epoch_ns_from_iso(_PUBLISHED_AFTER)
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=published_ns,
            published_time_quality=PublicationTimeQuality.KNOWN,
            observation_window_start_ns=window_ns,
            live_gates_active=True,
        )
        self.assertEqual(mode, IngestionMode.LIVE_OBSERVED)
        self.assertNotEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_live_gates_and_publication_before_window_is_historical(self) -> None:
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=epoch_ns_from_iso(_PUBLISHED_BEFORE),
            published_time_quality=PublicationTimeQuality.KNOWN,
            observation_window_start_ns=epoch_ns_from_iso(_WINDOW_START),
            live_gates_active=True,
        )
        self.assertEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_historical_path_without_live_gates_unchanged(self) -> None:
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=epoch_ns_from_iso(_PUBLISHED_AFTER),
            published_time_quality=PublicationTimeQuality.KNOWN,
            observation_window_start_ns=epoch_ns_from_iso(_WINDOW_START),
            live_gates_active=False,
        )
        self.assertEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_missing_publication_time_does_not_become_live(self) -> None:
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=None,
            published_time_quality=PublicationTimeQuality.UNKNOWN,
            observation_window_start_ns=epoch_ns_from_iso(_WINDOW_START),
            live_gates_active=True,
        )
        self.assertEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_inferred_publication_quality_does_not_become_live(self) -> None:
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=epoch_ns_from_iso("2026-09-22T00:00:00Z"),
            published_time_quality=PublicationTimeQuality.INFERRED_LOW_CONFIDENCE,
            observation_window_start_ns=epoch_ns_from_iso(_WINDOW_START),
            live_gates_active=True,
        )
        self.assertEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_missing_observation_window_does_not_become_live(self) -> None:
        mode = select_news_ingest_ingestion_mode(
            published_time_ns=epoch_ns_from_iso(_PUBLISHED_AFTER),
            published_time_quality=PublicationTimeQuality.KNOWN,
            observation_window_start_ns=None,
            live_gates_active=True,
        )
        self.assertEqual(mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_live_gates_require_all_three_campaign_flags(self) -> None:
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            self.assertTrue(news_ingest_live_gates_active())
        partial = dict(_LIVE_GATE_ENV)
        partial["IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"] = "0"
        with patch.dict(os.environ, partial, clear=False):
            self.assertFalse(news_ingest_live_gates_active())

    def test_parse_observation_window_iso_and_ns(self) -> None:
        expected = epoch_ns_from_iso(_WINDOW_START)
        self.assertEqual(
            parse_observation_window_start_ns({"observation_window_start": _WINDOW_START}),
            expected,
        )
        self.assertEqual(
            parse_observation_window_start_ns({"observation_window_start_ns": expected}),
            expected,
        )
        self.assertIsNone(parse_observation_window_start_ns({}))
        self.assertIsNone(parse_observation_window_start_ns({"observation_window_start_ns": "bad"}))


class NewsIngestModeHttpPathTests(unittest.TestCase):
    """HTTP path — SOFTWARE_CONTROLLED / FIXTURE."""

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

    def test_http_live_gates_publication_after_window_stamps_live_observed(self) -> None:
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(
                self.store,
                {
                    "retrieved_time": _RETRIEVED,
                    "observation_window_start": _WINDOW_START,
                    "articles": [_item(published=_PUBLISHED_AFTER)],
                },
            )
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertEqual(payload["events"][0]["ingestion_mode"], IngestionMode.LIVE_OBSERVED.value)
        event = self.store.strategy_repository.get_event(payload["events"][0]["event_id"])
        self.assertIsNotNone(event)
        provenance = provenance_from_event(event)
        self.assertIsNotNone(provenance)
        assert provenance is not None
        self.assertEqual(provenance.ingestion_mode, IngestionMode.LIVE_OBSERVED)

    def test_http_live_gates_publication_before_window_stamps_historical(self) -> None:
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(
                self.store,
                {
                    "retrieved_time": _RETRIEVED,
                    "observation_window_start": _WINDOW_START,
                    "articles": [_item(published=_PUBLISHED_BEFORE, headline="Pre-arm historical headline earnings")],
                },
            )
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertEqual(
            payload["events"][0]["ingestion_mode"],
            IngestionMode.HISTORICAL_RECONSTRUCTED.value,
        )
        event = self.store.strategy_repository.get_event(payload["events"][0]["event_id"])
        provenance = provenance_from_event(event)
        assert provenance is not None
        self.assertEqual(provenance.ingestion_mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_http_historical_cli_export_path_unchanged(self) -> None:
        # Live gates off → HISTORICAL_RECONSTRUCTED regardless of publication/window.
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "observation_window_start": _WINDOW_START,
                "articles": [_item(published=_PUBLISHED_AFTER)],
            },
        )
        self.assertEqual(payload["admitted_count"], 1, payload)
        self.assertEqual(
            payload["events"][0]["ingestion_mode"],
            IngestionMode.HISTORICAL_RECONSTRUCTED.value,
        )
        event = self.store.strategy_repository.get_event(payload["events"][0]["event_id"])
        provenance = provenance_from_event(event)
        assert provenance is not None
        self.assertEqual(provenance.ingestion_mode, IngestionMode.HISTORICAL_RECONSTRUCTED)

    def test_http_missing_publication_does_not_stamp_live(self) -> None:
        with patch.dict(os.environ, _LIVE_GATE_ENV, clear=False):
            payload = handle_news_ingest_post(
                self.store,
                {
                    "retrieved_time": _RETRIEVED,
                    "observation_window_start": _WINDOW_START,
                    "articles": [_item(published=None)],
                },
            )
        self.assertEqual(payload["admitted_count"], 0, payload)
        self.assertGreaterEqual(payload["skipped_count"], 1)
        for row in payload["events"]:
            self.assertNotEqual(row.get("ingestion_mode"), IngestionMode.LIVE_OBSERVED.value)


if __name__ == "__main__":
    unittest.main()
