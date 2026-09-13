"""Explainable ranking vector. No displayed scalar score."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.economic_assessment import (
    AccountActionability,
    LiquidityState,
)
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import (
    OpportunitySummary,
    RANKING_BASIS_COMPARATOR,
    rank_opportunity_summaries,
)
from market_platform_foundation.intelligence.opportunity.comparison import ComparisonVectorV1
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction


QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str, instrument_id: str = "AAPL") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary=f"{instrument_id} candidate",
    )


def _vector(*, pnl: int, actionability: AccountActionability = AccountActionability.ACTIONABLE) -> ComparisonVectorV1:
    return ComparisonVectorV1(
        actionability=actionability,
        expected_net_pnl_minor=pnl,
        expected_return_bps=100,
        maximum_loss_minor=50,
        capital_required_minor=1000,
        buying_power_required_minor=1000,
        initial_margin_required_minor=None,
        maintenance_margin_required_minor=None,
        expected_hold_ns=100,
        maximum_hold_ns=200,
        capital_lock_ns=200,
        fill_probability=0.8,
        liquidity_state=LiquidityState.AVAILABLE,
        uncertainty=None,
    )


class OpportunityRankingVectorTests(unittest.TestCase):
    def test_serialized_payload_has_dimensions_and_no_rank_score(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-b"), _opportunity("opp-a")),
            assessments_by_opportunity={
                "opp-a": AssessmentAction.EMIT,
                "opp-b": AssessmentAction.EMIT,
            },
        )
        ranked = rank_review_rows(
            rows,
            comparison_vectors={"opp-a": _vector(pnl=900), "opp-b": _vector(pnl=100)},
        )
        payload = ranked[0].to_dict()
        self.assertEqual(ranked[0].opportunity_id, "opp-a")
        self.assertNotIn("rank_score", payload)
        self.assertEqual(payload["ranking_vector"]["basis"], RANKING_BASIS_COMPARATOR)
        self.assertTrue(payload["ranking_vector"]["dimensions"])

    def test_stub_cannot_outrank_actionable_comparator_row(self) -> None:
        governed = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-governed"),),
            assessments_by_opportunity={"opp-governed": AssessmentAction.EMIT},
        )
        attention = assemble_opportunity_review_rows(
            attention_rows=(
                {
                    "attention_id": "att-loud",
                    "symbol": "NVDA",
                    "headline": "very long headline that would win the stub heuristic if it were allowed to outrank",
                    "catalyst_ids": ("a", "b", "c", "d", "e"),
                },
            )
        )
        ranked = rank_review_rows(
            (*governed, *attention),
            comparison_vectors={"opp-governed": _vector(pnl=50)},
        )
        self.assertEqual(ranked[0].opportunity_id, "opp-governed")
        self.assertEqual(ranked[1].identity_kind, "NOT_OPPORTUNITY_V1")

    def test_internal_stub_score_is_not_serialized(self) -> None:
        ranked = rank_opportunity_summaries(
            (OpportunitySummary(summary_id="a", instrument_id="AAPL", headline="alpha"),)
        )
        self.assertIsNotNone(ranked[0].rank_score)
        self.assertNotIn("rank_score", ranked[0].to_dict())


if __name__ == "__main__":
    unittest.main()
