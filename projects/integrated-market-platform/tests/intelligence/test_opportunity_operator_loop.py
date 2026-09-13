"""Operator loop ranking, ingest, lifecycle, quality, and safety tests."""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.data_quality import (
    project_opportunity_data_quality,
)
from market_platform_foundation.intelligence.opportunity.dedup import dedup_review_rows
from market_platform_foundation.intelligence.opportunity.economic_assessment import (
    AccountActionability,
    LiquidityState,
)
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.lifecycle import (
    OperatorLifecycleState,
    apply_operator_ack,
    derive_lifecycle_from_assessment,
)
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import (
    OpportunitySummary,
    RANKING_BASIS_COMPARATOR,
    RANKING_BASIS_STUB,
    rank_opportunity_summaries,
)
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.opportunity.comparison import ComparisonVectorV1
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
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


class OperatorLoopTests(unittest.TestCase):
    def test_ranking_is_deterministic(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-b"), _opportunity("opp-a")),
            assessments_by_opportunity={
                "opp-a": AssessmentAction.EMIT,
                "opp-b": AssessmentAction.EMIT,
            },
        )
        vectors = {
            "opp-a": _vector(pnl=900),
            "opp-b": _vector(pnl=100),
        }
        first = rank_review_rows(rows, comparison_vectors=vectors)
        second = rank_review_rows(rows, comparison_vectors=vectors)
        self.assertEqual([row.opportunity_id for row in first], [row.opportunity_id for row in second])
        self.assertEqual(first[0].opportunity_id, "opp-a")
        payload = first[0].to_dict()
        self.assertNotIn("rank_score", payload)
        self.assertEqual(payload["ranking_vector"]["basis"], RANKING_BASIS_COMPARATOR)
        self.assertFalse(any(key in payload for key in ("universal_score", "opaque_score")))

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

    def test_missing_stale_degraded_do_not_fabricate_quotes(self) -> None:
        quality = project_opportunity_data_quality(
            source="RECORDED_ARTIFACTS",
            live_observational_env=True,
        )
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["source"], "RECORDED_ARTIFACTS")
        self.assertNotIn("quote", quality)
        live = project_opportunity_data_quality(source="LIVE_OBSERVATIONAL")
        self.assertEqual(live["status"], "UNAVAILABLE")

    def test_abstention_is_ineligible_and_not_ranked(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-abstain"),),
            assessments_by_opportunity={"opp-abstain": AssessmentAction.ABSTAIN},
        )
        self.assertEqual(rows[0].lifecycle_state, OperatorLifecycleState.INELIGIBLE.value)
        ranked = rank_review_rows(rows)
        self.assertEqual(ranked, ())

    def test_no_fabricated_evidence_or_matched_rows(self) -> None:
        empty = assemble_opportunity_review_rows()
        self.assertEqual(empty, ())
        ignored = assemble_opportunity_review_rows(
            attention_rows=(
                {
                    "attention_id": "discover-1",
                    "symbol": "MSFT",
                    "headline": "screener",
                    "attention_score": 99,
                    "screen_ids": ["foo"],
                },
            )
        )
        self.assertEqual(ignored, ())

    def test_unknown_instrument_fail_closed(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-bad", instrument_id="UNKNOWN"),)
        )
        self.assertEqual(rows, ())

    def test_ingest_does_not_import_scanner(self) -> None:
        import market_platform_foundation.intelligence.opportunity.ingest as ingest

        source = inspect.getsource(ingest)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("StrategyPaperRuntime", source)

    def test_lifecycle_ack_does_not_change_opportunity_v1(self) -> None:
        original = _opportunity("opp-1")
        state = derive_lifecycle_from_assessment(AssessmentAction.EMIT)
        watched = apply_operator_ack(state, OperatorLifecycleState.WATCHED)
        self.assertEqual(watched, OperatorLifecycleState.WATCHED)
        self.assertEqual(original.opportunity_id, "opp-1")

    def test_dedup_same_opportunity_id(self) -> None:
        a = OpportunitySummary(summary_id="s1", instrument_id="AAPL", headline="a", opportunity_id="opp-1")
        b = OpportunitySummary(summary_id="s2", instrument_id="AAPL", headline="b", opportunity_id="opp-1")
        deduped = dedup_review_rows((a, b))
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(deduped[0].duplicates), 1)

    def test_repository_storage_id_is_stripped(self) -> None:
        opportunity = _opportunity("opp-store")
        from market_platform_foundation.intelligence.contracts import opportunity_v1_to_dict

        class _Repo:
            _stores = {"opportunities": {"opp-store": {**opportunity_v1_to_dict(opportunity), "_id": "opp-store"}}}

        rows = assemble_opportunity_review_rows(
            repository=_Repo(),
            assessments_by_opportunity={"opp-store": AssessmentAction.EMIT},
        )
        self.assertEqual([row.opportunity_id for row in rows], ["opp-store"])

    def test_repository_does_not_mint_second_opportunity(self) -> None:
        repo = InMemoryIntelligenceRepository()
        opportunity = _opportunity("opp-repo")
        repo.put_opportunity(opportunity)
        rows = assemble_opportunity_review_rows(
            opportunities=(opportunity,),
            repository=repo,
            assessments_by_opportunity={"opp-repo": AssessmentAction.EMIT},
        )
        ids = [row.opportunity_id for row in rows]
        self.assertEqual(ids.count("opp-repo"), 1)

    def test_read_model_omits_rank_score(self) -> None:
        ranked = rank_opportunity_summaries(
            (
                OpportunitySummary(summary_id="a", instrument_id="AAPL", headline="alpha"),
            )
        )
        self.assertIsNotNone(ranked[0].rank_score)
        self.assertNotIn("rank_score", ranked[0].to_dict())
        self.assertNotIn("rank_score", ranked[0].to_dict().get("metadata", {}))


class OpportunityEngineInvariantsTests(unittest.TestCase):
    def test_opportunity_metadata_rejects_universal_score(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityV1(
                opportunity_id="opp-score",
                schema_version="1",
                scope=SCOPE,
                created_at_ns=10_000,
                quality=QUALITY,
                metadata={"universal_score": 88},
            )


if __name__ == "__main__":
    unittest.main()
