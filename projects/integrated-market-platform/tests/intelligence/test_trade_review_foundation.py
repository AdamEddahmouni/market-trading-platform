"""Trade review foundation — contracts, honesty, persistence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import ContractReference  # noqa: E402
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult  # noqa: E402
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    TRADE_REVIEW_FOUNDATION_READY,
    TradeExecutionAttribution,
    TradeReviewMode,
    TradeReviewV1,
    build_paper_trade_review,
    build_rejected_opportunity_review,
    build_watched_opportunity_review,
    derive_trade_review_id,
    InMemoryTradeReviewRepository,
    trade_review_v1_from_dict,
    trade_review_v1_to_dict,
)


class TradeReviewFoundationTests(unittest.TestCase):
    def test_acceptance_label_constant(self) -> None:
        self.assertEqual(TRADE_REVIEW_FOUNDATION_READY, "TRADE_REVIEW_FOUNDATION_READY")

    def test_rejected_review_has_no_execution_metrics(self) -> None:
        review = build_rejected_opportunity_review(
            opportunity_id="opp-1",
            strategy_id="strat-1",
            decision_time_ns=1_000,
            created_at_ns=2_000,
            notes="Spread too wide at decision time.",
        )
        self.assertEqual(review.review_mode, TradeReviewMode.REJECTED_OPPORTUNITY)
        self.assertIsNone(review.execution_attribution)
        with self.assertRaises(ValueError):
            TradeReviewV1(
                review_id="bad",
                schema_version=review.schema_version,
                review_mode=TradeReviewMode.WATCHED_OPPORTUNITY,
                decision="WATCHED",
                decision_time_ns=1,
                created_at_ns=2,
                execution_attribution=TradeExecutionAttribution(realized_pnl_minor=100),
            )

    def test_watched_review_round_trip(self) -> None:
        ref = ContractReference(kind="snapshot", id="snap-1")
        review = build_watched_opportunity_review(
            opportunity_id="opp-2",
            strategy_id=None,
            decision_time_ns=10,
            created_at_ns=20,
            evidence_snapshot_refs=(ref,),
        )
        payload = trade_review_v1_to_dict(review)
        restored = trade_review_v1_from_dict(payload)
        self.assertEqual(restored.review_id, review.review_id)
        self.assertEqual(restored.evidence_snapshot_refs[0].id, "snap-1")

    def test_paper_review_requires_attribution(self) -> None:
        attribution = TradeExecutionAttribution(
            order_refs=(ContractReference(kind="paper_order", id="ord-1"),),
            fill_refs=(ContractReference(kind="paper_fill", id="fill-1"),),
            entry_price_minor=10_500,
            exit_price_minor=10_700,
            realized_pnl_minor=200,
            mae_bps=-12.5,
            mfe_bps=30.0,
            slippage_bps=1.2,
            decision_to_submit_latency_ns=50_000_000,
            exit_reason="TARGET",
        )
        review = build_paper_trade_review(
            opportunity_id="opp-3",
            strategy_id="FORECAST_MOMENTUM",
            decision="CLOSED",
            decision_time_ns=100,
            created_at_ns=200,
            execution_attribution=attribution,
            preview_refs=(ContractReference(kind="paper_preview", id="prev-1"),),
        )
        self.assertEqual(review.review_mode, TradeReviewMode.PAPER_TRADE)
        self.assertEqual(review.execution_attribution.realized_pnl_minor, 200)

    def test_derive_trade_review_id_is_stable(self) -> None:
        first = derive_trade_review_id(
            review_mode=TradeReviewMode.REJECTED_OPPORTUNITY,
            opportunity_id="opp-x",
            strategy_id="s",
            decision="DISMISSED",
            decision_time_ns=99,
        )
        second = derive_trade_review_id(
            review_mode=TradeReviewMode.REJECTED_OPPORTUNITY,
            opportunity_id="opp-x",
            strategy_id="s",
            decision="DISMISSED",
            decision_time_ns=99,
        )
        self.assertEqual(first, second)

    def test_in_memory_repository_idempotent_put(self) -> None:
        repo = InMemoryTradeReviewRepository()
        review = build_rejected_opportunity_review(
            opportunity_id="opp-repo",
            strategy_id=None,
            decision_time_ns=1,
            created_at_ns=2,
        )
        self.assertEqual(repo.put_trade_review(review), RepositoryPutResult.INSERTED)
        self.assertEqual(repo.put_trade_review(review), RepositoryPutResult.ALREADY_PRESENT)
        listed = repo.list_trade_reviews_by_opportunity("opp-repo")
        self.assertEqual(len(listed), 1)
        self.assertEqual(repo.get_trade_review(review.review_id), review)


if __name__ == "__main__":
    unittest.main()
