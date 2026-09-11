"""Canonical news foundation — contracts, timestamps, filters, replay, safety."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.news.catalysts import CatalystRegistry  # noqa: E402
from market_platform_foundation.news.config import (  # noqa: E402
    default_pipeline_config,
    verify_news_config,
)
from market_platform_foundation.news.contracts import (  # noqa: E402
    NewsArticleEvent,
    PipelineConfig,
    PublicationTimeQuality,
)
from market_platform_foundation.news.dedupe import dedupe_events  # noqa: E402
from market_platform_foundation.news.filters import (  # noqa: E402
    CatalystKeywordFilter,
    FilterChain,
    RecencyFilter,
    SourcePolicyFilter,
)
from market_platform_foundation.news.fixture_provider import FixtureNewsProvider  # noqa: E402
from market_platform_foundation.news.normalize import normalize_raw_item  # noqa: E402
from market_platform_foundation.news.pipeline import NewsPipeline, order_accepted_events  # noqa: E402
from market_platform_foundation.news.replay import NewsReplayHarness  # noqa: E402
from market_platform_foundation.news.service import NewsIntelligenceService  # noqa: E402
from market_platform_foundation.news.sources import SourceTrustCatalog  # noqa: E402
from market_platform_foundation.news.timestamps import (  # noqa: E402
    age_seconds_at,
    classify_publication_time,
    epoch_ns_from_iso,
    is_observable_at,
    parse_utc_iso,
    to_utc_iso,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402


def _event(
    *,
    event_id: str = "evt-1",
    published: str = "2026-09-09T12:00:00Z",
    retrieved: str = "2026-09-09T12:01:00Z",
    headline: str = "ACME reports earnings beat",
    source_id: str = "fixture_wire",
    quality: PublicationTimeQuality = PublicationTimeQuality.KNOWN,
) -> NewsArticleEvent:
    return NewsArticleEvent(
        event_id=event_id,
        provider_id="news.fixture",
        provider_native_id=event_id,
        source_id=source_id,
        published_time=published,
        published_time_quality=quality,
        retrieved_time=retrieved,
        headline=headline,
        publisher_source="Fixture Wire",
        url=f"https://fixture.example/{event_id}",
    )


class NewsContractTests(unittest.TestCase):
    def test_missing_publication_time_is_unknown_not_retrieval(self) -> None:
        published, quality, flags = classify_publication_time(
            "",
            retrieved_time="2026-09-09T12:00:00Z",
        )
        self.assertEqual(published, "")
        self.assertEqual(quality, PublicationTimeQuality.UNKNOWN)
        self.assertIn("PUBLICATION_TIME_MISSING", flags)

    def test_normalize_raw_item_preserves_separate_times(self) -> None:
        event = normalize_raw_item(
            {
                "headline": "ACME earnings",
                "published_time": "",
                "tickers": ["ACME"],
            },
            provider_id="news.fixture",
            source_id="fixture_wire",
            retrieved_time="2026-09-09T12:05:00Z",
        )
        self.assertEqual(event.published_time, "")
        self.assertEqual(event.retrieved_time, "2026-09-09T12:05:00Z")
        self.assertEqual(event.published_time_quality, PublicationTimeQuality.UNKNOWN)


class TimestampTests(unittest.TestCase):
    def test_dst_boundary_parses_ny_wall_to_utc(self) -> None:
        ny = ZoneInfo("America/New_York")
        local = datetime(2026, 3, 8, 9, 30, tzinfo=ny)
        iso = to_utc_iso(local)
        parsed = parse_utc_iso(iso)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_observable_uses_retrieved_time(self) -> None:
        event = _event(
            published="2026-09-09T10:00:00Z",
            retrieved="2026-09-09T14:00:00Z",
        )
        as_of = iso_to_epoch_ns("2026-09-09T13:00:00Z")
        self.assertFalse(is_observable_at(event, as_of))
        as_of_later = iso_to_epoch_ns("2026-09-09T14:30:00Z")
        self.assertTrue(is_observable_at(event, as_of_later))


class FilterTests(unittest.TestCase):
    def test_recency_rejects_stale_and_accepts_fresh(self) -> None:
        config = PipelineConfig(recency_max_age_seconds=3600, enabled_source_ids=frozenset({"fixture_wire"}))
        fresh = _event(published="2026-09-09T13:30:00Z", retrieved="2026-09-09T13:31:00Z")
        stale = _event(
            event_id="evt-stale",
            published="2026-09-01T10:00:00Z",
            retrieved="2026-09-01T10:05:00Z",
        )
        as_of = iso_to_epoch_ns("2026-09-09T14:00:00Z")
        recency = RecencyFilter()
        self.assertTrue(recency.evaluate(fresh, as_of_ns=as_of, config=config).accepted)
        self.assertFalse(recency.evaluate(stale, as_of_ns=as_of, config=config).accepted)

    def test_source_policy_rejects_disabled_source(self) -> None:
        config = default_pipeline_config()
        event = _event(source_id="unsupported_blog", headline="rumor")
        decision = SourcePolicyFilter().evaluate(event, config=config)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason_code, "SOURCE_DISABLED")

    def test_catalyst_filter_matches_keywords(self) -> None:
        config = default_pipeline_config()
        event = _event(headline="ACME reports earnings beat and guidance")
        decision = CatalystKeywordFilter().evaluate(event, config=config)
        self.assertTrue(decision.accepted)
        self.assertIn("earnings", decision.matched_catalyst_ids)


class DedupeTests(unittest.TestCase):
    def test_dedupe_by_url(self) -> None:
        first = _event(event_id="a", headline="Shared headline")
        second = NewsArticleEvent(
            event_id="b",
            provider_id="news.fixture",
            provider_native_id="",
            source_id="fixture_wire",
            published_time="2026-09-09T12:00:00Z",
            published_time_quality=PublicationTimeQuality.KNOWN,
            retrieved_time="2026-09-09T12:02:00Z",
            headline="Shared headline",
            publisher_source="Fixture Wire",
            url="https://fixture.example/a",
        )
        unique, dup_map = dedupe_events([first, second])
        self.assertEqual(len(unique), 1)
        self.assertEqual(dup_map["b"], "a")


class ReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FixtureNewsProvider()
        self.events = self.provider.fetch_events()
        self.config = default_pipeline_config()

    def test_replay_prevents_lookahead_and_delayed_retrieval(self) -> None:
        harness = NewsReplayHarness()
        early = harness.replay(self.events, as_of="2026-09-09T14:00:00Z", config=self.config)
        late = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=self.config)
        early_ids = {event.event_id for event in early.accepted_events}
        late_ids = {event.event_id for event in late.accepted_events}
        self.assertLessEqual(len(early_ids), len(late_ids))

        lookahead = [
            result
            for result in early.results
            if result.decisions
            and result.decisions[0].reason_code == "OBSERVABILITY_LOOKAHEAD"
        ]
        self.assertTrue(lookahead)

    def test_replay_is_deterministic(self) -> None:
        harness = NewsReplayHarness()
        first = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=self.config)
        second = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=self.config)
        self.assertEqual(
            [event.event_id for event in first.accepted_events],
            [event.event_id for event in second.accepted_events],
        )
        self.assertEqual(first.stats.to_dict(), second.stats.to_dict())

    def test_fresh_trusted_catalyst_survives_filters(self) -> None:
        harness = NewsReplayHarness()
        replay = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=self.config)
        headlines = [event.headline for event in replay.accepted_events]
        self.assertTrue(any("earnings" in headline.lower() for headline in headlines))
        self.assertTrue(any("fda approval" in headline.lower() for headline in headlines))
        self.assertTrue(any("fomc" in headline.lower() for headline in headlines))

    def test_config_change_alters_output(self) -> None:
        harness = NewsReplayHarness()
        strict = PipelineConfig(
            recency_max_age_seconds=3600,
            enabled_source_ids=self.config.enabled_source_ids,
            enabled_catalyst_ids=self.config.enabled_catalyst_ids,
        )
        loose = PipelineConfig(
            recency_max_age_seconds=30 * 24 * 3600,
            enabled_source_ids=self.config.enabled_source_ids,
            enabled_catalyst_ids=self.config.enabled_catalyst_ids,
        )
        strict_result = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=strict)
        loose_result = harness.replay(self.events, as_of="2026-09-09T15:30:00Z", config=loose)
        self.assertLess(len(strict_result.accepted_events), len(loose_result.accepted_events))


class ServiceTests(unittest.TestCase):
    def test_read_only_service_has_no_execution_flags(self) -> None:
        service = NewsIntelligenceService()
        payload = service.query_fixture_pack(
            as_of="2026-09-09T15:30:00Z",
            config=default_pipeline_config(),
        )
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["execution_authority"])
        self.assertFalse(payload["ai_authority"])
        self.assertIn("items", payload)
        self.assertIn("stats", payload)


class SafetyRegressionTests(unittest.TestCase):
    def test_no_ai_or_broker_modules_imported(self) -> None:
        forbidden = (
            "anthropic",
            "openai",
            "market_platform_foundation.paper.broker",
            "market_platform_foundation.providers.adapters.tradovate",
        )
        imported = set(sys.modules)
        for name in forbidden:
            self.assertNotIn(name, imported)

    def test_verify_news_config_ok(self) -> None:
        report = verify_news_config()
        self.assertTrue(report["ok"])


class OrderingTests(unittest.TestCase):
    def test_stable_ordering(self) -> None:
        events = [
            _event(event_id="b", retrieved="2026-09-09T13:00:00Z"),
            _event(event_id="a", retrieved="2026-09-09T14:00:00Z"),
        ]
        ordered = order_accepted_events(events)
        self.assertEqual(ordered[0].event_id, "a")


if __name__ == "__main__":
    unittest.main()
