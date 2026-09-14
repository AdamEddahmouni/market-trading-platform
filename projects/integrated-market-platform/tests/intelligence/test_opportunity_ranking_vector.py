"""Explainable ranking vector. No displayed scalar score."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
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
    PROVISIONAL_ORDER_COPY,
    RANKING_BASIS_ATTENTION,
    RANKING_BASIS_COMPARATOR,
    RANKING_BASIS_STUB,
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
        self.assertNotIn("copy", payload["ranking_vector"])

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
        self.assertNotIn("copy", ranked[0].to_dict()["ranking_vector"])
        self.assertEqual(ranked[1].to_dict()["ranking_vector"]["copy"], PROVISIONAL_ORDER_COPY)
        self.assertEqual(ranked[1].to_dict()["ranking_vector"]["basis"], RANKING_BASIS_ATTENTION)

    def test_stub_without_sidecar_serializes_provisional_copy_not_rank_score(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-stub"),),
            assessments_by_opportunity={"opp-stub": AssessmentAction.EMIT},
        )
        ranked = rank_review_rows(rows)
        payload = ranked[0].to_dict()
        self.assertEqual(payload["ranking_vector"]["basis"], RANKING_BASIS_STUB)
        self.assertEqual(payload["ranking_vector"]["copy"], PROVISIONAL_ORDER_COPY)
        self.assertNotIn("rank_score", payload)
        self.assertNotIn("universal_score", payload)

    def test_internal_stub_score_is_not_serialized(self) -> None:
        ranked = rank_opportunity_summaries(
            (OpportunitySummary(summary_id="a", instrument_id="AAPL", headline="alpha"),)
        )
        self.assertIsNotNone(ranked[0].rank_score)
        self.assertNotIn("rank_score", ranked[0].to_dict())

    def test_missing_repository_sidecar_does_not_fabricate_comparator_vector(self) -> None:
        from market_platform_foundation.intelligence.opportunity.ranking import (
            comparison_vectors_from_repository,
        )

        self.assertEqual(comparison_vectors_from_repository(None), {})
        self.assertEqual(comparison_vectors_from_repository(object()), {})

    def test_shared_explicit_thesis_keeps_ranked_winner_not_summary_id(self) -> None:
        def _with_thesis(opportunity_id: str, thesis: str) -> OpportunityV1:
            return OpportunityV1(
                opportunity_id=opportunity_id,
                schema_version="1",
                scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
                created_at_ns=10_000,
                quality=QUALITY,
                side=OpportunitySide.LONG,
                reason_summary=f"{opportunity_id} candidate",
                source_forecast_refs=(ContractReference(kind="forecast", id=f"fc-{opportunity_id}"),),
                metadata={"underlying_thesis_id": thesis},
            )

        rows = assemble_opportunity_review_rows(
            opportunities=(_with_thesis("opp-a", "earnings-aapl"), _with_thesis("opp-z", "earnings-aapl")),
            assessments_by_opportunity={
                "opp-a": AssessmentAction.EMIT,
                "opp-z": AssessmentAction.EMIT,
            },
        )
        self.assertEqual({row.metadata.get("thesis_identity") for row in rows}, {"underlying:earnings-aapl"})
        ranked = rank_review_rows(
            rows,
            comparison_vectors={"opp-a": _vector(pnl=10), "opp-z": _vector(pnl=900)},
        )
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].opportunity_id, "opp-z")
        self.assertEqual(ranked[0].duplicates, ("opp-a",))
        self.assertNotIn("rank_score", ranked[0].to_dict())
        self.assertEqual(ranked[0].rank_order, 1)


if __name__ == "__main__":
    unittest.main()
