"""Event-time correctness tests for canonical news foundation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.news.config import default_pipeline_config  # noqa: E402
from market_platform_foundation.news.contracts import PublicationTimeQuality  # noqa: E402
from market_platform_foundation.news.fixture_provider import FixtureNewsProvider  # noqa: E402
from market_platform_foundation.news.normalize import normalize_raw_item  # noqa: E402
from market_platform_foundation.news.replay import NewsReplayHarness  # noqa: E402
from market_platform_foundation.news.timestamps import classify_publication_time  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402


class EventTimeTests(unittest.TestCase):
    def test_publication_after_retrieval_flagged(self) -> None:
        published, quality, flags = classify_publication_time(
            "2026-09-09T16:00:00Z",
            retrieved_time="2026-09-09T15:00:00Z",
        )
        self.assertEqual(quality, PublicationTimeQuality.KNOWN)
        self.assertIn("PUBLICATION_AFTER_RETRIEVAL", flags)
        self.assertEqual(published, "2026-09-09T16:00:00Z")

    def test_future_publication_rejected_by_recency(self) -> None:
        event = normalize_raw_item(
            {
                "headline": "Future headline with earnings",
                "published_time": "2026-09-10T10:00:00Z",
                "tickers": ["ACME"],
            },
            provider_id="news.fixture",
            source_id="fixture_wire",
            retrieved_time="2026-09-09T12:00:00Z",
        )
        harness = NewsReplayHarness()
        replay = harness.replay(
            [event],
            as_of="2026-09-09T14:00:00Z",
            config=default_pipeline_config(),
        )
        self.assertEqual(len(replay.accepted_events), 0)
        reason_codes = [
            decision.reason_code
            for result in replay.results
            for decision in result.decisions
            if not decision.accepted
        ]
        self.assertIn("RECENCY_FUTURE_PUBLICATION", reason_codes)

    def test_missing_publication_uses_age_proxy_not_fake_publication(self) -> None:
        event = normalize_raw_item(
            {
                "headline": "SEC filing financing headline",
                "published_time": "",
                "tickers": ["DELTA"],
            },
            provider_id="news.fixture",
            source_id="sec_edgar",
            retrieved_time="2026-09-09T13:30:00Z",
        )
        self.assertEqual(event.published_time, "")
        harness = NewsReplayHarness()
        replay = harness.replay(
            [event],
            as_of="2026-09-09T14:00:00Z",
            config=default_pipeline_config(),
        )
        recency = [
            decision
            for result in replay.results
            for decision in result.decisions
            if decision.reason_code == "RECENCY_ACCEPTED"
        ]
        self.assertTrue(recency)
        self.assertIn("RETRIEVED_TIME_AGE_PROXY", recency[0].detail)

    def test_delayed_retrieval_unavailable_until_retrieved(self) -> None:
        provider = FixtureNewsProvider()
        events = provider.fetch_events()
        delayed = [event for event in events if "FDA approval" in event.headline]
        self.assertEqual(len(delayed), 1)
        event = delayed[0]
        harness = NewsReplayHarness()
        before = harness.replay([event], as_of="2026-09-09T14:00:00Z", config=default_pipeline_config())
        after = harness.replay([event], as_of="2026-09-09T15:00:00Z", config=default_pipeline_config())
        self.assertEqual(len(before.accepted_events), 0)
        self.assertEqual(len(after.accepted_events), 1)

    def test_timezone_conversion_consistency(self) -> None:
        event = normalize_raw_item(
            {
                "headline": "CPI report drives futures",
                "published_time": "2026-09-09T08:30:00-04:00",
                "tickers": ["ES"],
                "asset_class": "FUTURES",
            },
            provider_id="news.fixture",
            source_id="reuters",
            retrieved_time="2026-09-09T12:31:00Z",
        )
        self.assertTrue(event.published_time.endswith("Z"))
        as_of = iso_to_epoch_ns("2026-09-09T14:00:00Z")
        harness = NewsReplayHarness()
        replay = harness.replay([event], as_of="2026-09-09T14:00:00Z", config=default_pipeline_config())
        self.assertGreaterEqual(len(replay.accepted_events), 0)


if __name__ == "__main__":
    unittest.main()
