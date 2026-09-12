"""Opportunity read-model and provisional ranking."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.read_model import (
    InMemoryOpportunitySummaryStore,
    OpportunitySummary,
    PROVISIONAL_RANKING_WEIGHTS,
    ftep_attention_candidate_to_summary,
    rank_opportunity_summaries,
)
from market_platform_foundation.news.contracts import (
    InstrumentLinkage,
    NewsArticleEvent,
    PipelineEventResult,
    PublicationTimeQuality,
)


class OpportunityReadModelTests(unittest.TestCase):
    def test_provisional_ranking_is_deterministic(self) -> None:
        low = OpportunitySummary(
            summary_id="b",
            instrument_id="MSFT",
            headline="short",
            catalyst_ids=("earnings",),
            accepted=True,
        )
        high = OpportunitySummary(
            summary_id="a",
            instrument_id="NVDA",
            headline="NVIDIA reports stronger than expected quarterly earnings outlook",
            catalyst_ids=("earnings", "guidance", "analyst"),
            accepted=True,
        )
        ranked = rank_opportunity_summaries((low, high))
        self.assertEqual(ranked[0].summary_id, "a")
        self.assertEqual(ranked[0].rank_order, 1)
        self.assertIsNotNone(ranked[0].rank_score)
        self.assertGreater(ranked[0].rank_score or 0.0, ranked[1].rank_score or 0.0)

    def test_weights_documented(self) -> None:
        self.assertAlmostEqual(sum(PROVISIONAL_RANKING_WEIGHTS.values()), 1.0)

    def test_in_memory_store_sorted_list(self) -> None:
        store = InMemoryOpportunitySummaryStore()
        store.upsert(
            OpportunitySummary(summary_id="z", instrument_id="AAPL", headline="z headline")
        )
        store.upsert(
            OpportunitySummary(summary_id="a", instrument_id="MSFT", headline="a headline")
        )
        self.assertEqual(
            tuple(item.summary_id for item in store.list_summaries()),
            ("a", "z"),
        )

    def test_ftep_pipeline_adapter(self) -> None:
        event = NewsArticleEvent(
            event_id="evt-1",
            provider_id="FINVIZ_ELITE",
            provider_native_id="native-1",
            source_id="finviz",
            published_time="2026-09-12T14:00:00Z",
            published_time_quality=PublicationTimeQuality.KNOWN,
            retrieved_time="2026-09-12T14:01:00Z",
            headline="Apple wins contract",
            instrument_linkages=(
                InstrumentLinkage(instrument_id="AAPL", provider_symbol="AAPL", asset_class="EQUITY"),
            ),
        )
        from market_platform_foundation.news.contracts import FilterDecision, FilterStage

        result = PipelineEventResult(
            event=event,
            accepted=True,
            decisions=(
                FilterDecision(
                    stage=FilterStage.CATALYST_KEYWORD,
                    accepted=True,
                    reason_code="MATCH",
                    matched_catalyst_ids=("contract",),
                ),
            ),
        )
        from market_platform_foundation.intelligence.opportunity.read_model import (
            ftep_pipeline_result_to_summary,
        )

        summary = ftep_pipeline_result_to_summary(result)
        self.assertEqual(summary.instrument_id, "AAPL")
        self.assertEqual(summary.catalyst_ids, ("contract",))
        self.assertEqual(summary.campaign_slug, "FTEP-V1-002")

    def test_ftep_attention_adapter(self) -> None:
        summary = ftep_attention_candidate_to_summary(
            {
                "attention_id": "att-catalyst-aapl",
                "symbol": "AAPL",
                "headline": "AAPL catalyst signal",
                "tier": 2,
            }
        )
        self.assertEqual(summary.summary_id, "att-catalyst-aapl")
        self.assertEqual(summary.instrument_id, "AAPL")


if __name__ == "__main__":
    unittest.main()
