"""Evidence class promotion on operator review rows."""

from __future__ import annotations

import unittest
from dataclasses import replace

from market_platform_foundation.intelligence.opportunity.comparison import ComparisonVectorV1
from market_platform_foundation.intelligence.opportunity.economic_assessment import (
    AccountActionability,
    LiquidityState,
)
from market_platform_foundation.intelligence.opportunity.evidence_promotion import (
    EVIDENCE_CLASS_CANDIDATE,
    EVIDENCE_CLASS_VERIFIED,
    GATE_COMPARATOR_EVIDENCE_ABSENT,
    GATE_FRESHNESS_NOT_FRESH,
    PROMOTION_VERIFIED,
    apply_evidence_promotion,
    evaluate_evidence_promotion,
)
from market_platform_foundation.intelligence.opportunity.family_lookup import STATUS_ADMITTED
from market_platform_foundation.intelligence.opportunity.freshness import FRESHNESS_FRESH
from market_platform_foundation.intelligence.opportunity.lifecycle import OperatorLifecycleState
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import (
    RANKING_BASIS_COMPARATOR,
    RANKING_BASIS_STUB,
    OpportunitySummary,
    RankingVectorV1,
)


def _comparison_vector() -> ComparisonVectorV1:
    return ComparisonVectorV1(
        actionability=AccountActionability.ACTIONABLE,
        expected_net_pnl_minor=100,
        expected_return_bps=100.0,
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


def _row(**overrides: object) -> OpportunitySummary:
    base = OpportunitySummary(
        summary_id="sum-1",
        instrument_id="AAPL",
        headline="h",
        opportunity_id="opp-1",
        identity_kind="OPPORTUNITY_V1",
        evidence_class=EVIDENCE_CLASS_CANDIDATE,
        lifecycle_state=OperatorLifecycleState.ELIGIBLE.value,
        eligibility_state=OperatorLifecycleState.ELIGIBLE.value,
        accepted=True,
        data_quality={
            "freshness_evaluation": {"status": FRESHNESS_FRESH, "actionable": True},
        },
        metadata={"family_admission_status": STATUS_ADMITTED},
        ranking_vector=RankingVectorV1(basis=RANKING_BASIS_COMPARATOR, dimensions=()),
    )
    if not overrides:
        return base
    return replace(base, **overrides)


class EvidencePromotionTests(unittest.TestCase):
    def test_verified_when_all_gates_pass(self) -> None:
        evidence_class, reason = evaluate_evidence_promotion(_row())
        self.assertEqual(evidence_class, EVIDENCE_CLASS_VERIFIED)
        self.assertEqual(reason, PROMOTION_VERIFIED)
        promoted = apply_evidence_promotion(_row())
        self.assertEqual(promoted.evidence_class, EVIDENCE_CLASS_VERIFIED)
        self.assertEqual(promoted.metadata["evidence_promotion_from"], EVIDENCE_CLASS_CANDIDATE)

    def test_stale_freshness_stays_candidate(self) -> None:
        row = _row(
            data_quality={"freshness_evaluation": {"status": "STALE", "actionable": False}},
        )
        evidence_class, reason = evaluate_evidence_promotion(row)
        self.assertEqual(evidence_class, EVIDENCE_CLASS_CANDIDATE)
        self.assertEqual(reason, GATE_FRESHNESS_NOT_FRESH)

    def test_stub_ranking_stays_candidate(self) -> None:
        row = _row(ranking_vector=RankingVectorV1(basis=RANKING_BASIS_STUB, dimensions=()))
        evidence_class, reason = evaluate_evidence_promotion(row)
        self.assertEqual(evidence_class, EVIDENCE_CLASS_CANDIDATE)
        self.assertEqual(reason, GATE_COMPARATOR_EVIDENCE_ABSENT)

    def test_rank_review_rows_promotes_with_comparator(self) -> None:
        row = _row(ranking_vector=None)
        ranked = rank_review_rows((row,), comparison_vectors={"opp-1": _comparison_vector()})
        self.assertEqual(ranked[0].evidence_class, EVIDENCE_CLASS_VERIFIED)


if __name__ == "__main__":
    unittest.main()
