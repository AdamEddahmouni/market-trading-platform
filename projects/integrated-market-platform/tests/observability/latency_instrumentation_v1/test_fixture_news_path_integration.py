"""FIXTURE ingress integration for latency instrumentation v1.

Evidence: SOFTWARE_CONTROLLED / FIXTURE. Not live market. Not prospective.
Does not bind campaign ports or touch campaign sqlite.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.observability.latency_instrumentation_v1 import (
    EligibilityClockId,
    LatencyInstrumentationCollector,
    LatencyStageId,
    UNAVAILABLE_OPERATOR_STAGES,
)
from market_platform_foundation.observability.latency_instrumentation_v1.context import (
    STORE_ATTR,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import handle_news_ingest_post
from market_platform_foundation.ui_api.opportunity_projections import (
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"
_SERVER = "2026-09-15T14:05:10Z"


def _fixture_article() -> dict:
    return {
        "headline": "Example Corp reports quarterly earnings",
        "published_time": _PUBLISHED,
        "url": "https://example.com/fixture-latency-v1",
        "tickers": ["AAPL"],
        "publisher_source": "Wire",
        "provider_native_id": "fv-latency-fixture-1",
    }


class LatencyFixtureNewsPathIntegrationTests(unittest.TestCase):
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
        # Software book cursor so ranked summary is READY without live receive clock.
        self.store.as_of_time_ns = int(epoch_ns_from_iso(_SERVER) or 0)
        self.store.last_source_time_ns = int(epoch_ns_from_iso(_SERVER) or 0)
        bind_ui_api_intelligence(self.store)
        self.collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        setattr(self.store, STORE_ATTR, self.collector)
        self.server_ns = int(epoch_ns_from_iso(_SERVER) or 0)
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

    def test_fixture_ingress_correlates_software_stages(self) -> None:
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [_fixture_article()],
            },
        )
        self.assertEqual(payload["news_event_build09"], "INACTIVE")
        self.assertGreaterEqual(payload["admitted_count"], 1)
        self.assertGreaterEqual(payload["opportunity_count"], 1)
        event_id = payload["events"][0]["event_id"]
        opportunity_id = payload["opportunity_ids"][0]

        summary = build_opportunities_summary_payload(self.store)
        self.assertIn("items", summary)

        trace = self.collector.get_trace(event_id)
        self.assertIsNotNone(trace)
        assert trace is not None
        self.assertEqual(trace.evidence_class, "FIXTURE")
        self.assertEqual(trace.opportunity_id, opportunity_id)
        self.assertEqual(
            trace.eligibility_ns[str(EligibilityClockId.SOURCE_PUBLICATION)],
            epoch_ns_from_iso(_PUBLISHED),
        )
        self.assertEqual(
            trace.eligibility_ns[str(EligibilityClockId.PROVIDER_RETRIEVED)],
            epoch_ns_from_iso(_RETRIEVED),
        )
        self.assertEqual(
            trace.eligibility_ns[str(EligibilityClockId.IMP_SERVER_RECEIVED)],
            self.server_ns,
        )

        # Causal order: persist stamps before detector_completed (consumer exits after put).
        required = (
            LatencyStageId.NORMALIZATION_COMPLETED,
            LatencyStageId.PIT_COMPLETED,
            LatencyStageId.DETECTOR_STARTED,
            LatencyStageId.OPPORTUNITY_PERSISTED,
            LatencyStageId.DETECTOR_COMPLETED,
            LatencyStageId.RANK_GENERATED,
            LatencyStageId.API_PAYLOAD_GENERATED,
        )
        wall_times: list[int] = []
        for stage_id in required:
            stamp = trace.stages.get(str(stage_id))
            self.assertIsNotNone(stamp, msg=f"missing stage {stage_id}")
            assert stamp is not None
            self.assertIsNotNone(stamp.wall_ns, msg=f"no wall for {stage_id}")
            self.assertIsNotNone(stamp.mono_ns, msg=f"no mono for {stage_id}")
            assert stamp.wall_ns is not None
            wall_times.append(int(stamp.wall_ns))

        # Processing stages advance in wall domain within the guarded clock.
        self.assertEqual(wall_times, sorted(wall_times))
        self.assertGreaterEqual(
            self.collector.mono_delta_ns(
                event_id,
                LatencyStageId.NORMALIZATION_COMPLETED,
                LatencyStageId.API_PAYLOAD_GENERATED,
            )
            or -1,
            0,
        )

        coverage = trace.coverage_note()
        for name in UNAVAILABLE_OPERATOR_STAGES:
            self.assertEqual(coverage["operator_ui_stages"][name], "UNAVAILABLE")

        self.assertTrue(self.collector.summary_requests)
        request = self.collector.summary_requests[-1]
        self.assertEqual(request["evidence_class"], "FIXTURE")
        self.assertIn(event_id, request["correlated_event_ids"])

    def test_unbound_collector_still_admits_fixture_news(self) -> None:
        """Finviz ingest fail-closed path works when no collector is bound."""

        if hasattr(self.store, STORE_ATTR):
            delattr(self.store, STORE_ATTR)
        payload = handle_news_ingest_post(
            self.store,
            {
                "retrieved_time": _RETRIEVED,
                "articles": [_fixture_article()],
            },
        )
        self.assertEqual(payload["news_event_build09"], "INACTIVE")
        self.assertGreaterEqual(payload["admitted_count"], 1)
        self.assertEqual(payload["events"][0]["ingestion_mode"], "HISTORICAL_RECONSTRUCTED")


if __name__ == "__main__":
    unittest.main()
