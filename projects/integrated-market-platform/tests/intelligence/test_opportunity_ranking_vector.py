"""Explainable ranking vector: no serialized rank_score."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.economic_assessment import AccountActionability, LiquidityState
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import RANKING_BASIS_COMPARATOR
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.opportunity.comparison import ComparisonVectorV1


def _vector(pnl: int) -> ComparisonVectorV1:
    return ComparisonVectorV1(
        actionability=AccountActionability.ACTIONABLE,
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
    def test_serialized_payload_has_dimensions_not_rank_score(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-a",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
            created_at_ns=1,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            reason_summary="AAPL",
        )
        rows = assemble_opportunity_review_rows(
            opportunities=(opportunity,),
            assessments_by_opportunity={"opp-a": AssessmentAction.EMIT},
        )
        ranked = rank_review_rows(rows, comparison_vectors={"opp-a": _vector(10)})
        payload = ranked[0].to_dict()
        self.assertNotIn("rank_score", payload)
        self.assertEqual(payload["ranking_vector"]["basis"], RANKING_BASIS_COMPARATOR)
        self.assertTrue(payload["ranking_vector"]["dimensions"])


if __name__ == "__main__":
    unittest.main()
