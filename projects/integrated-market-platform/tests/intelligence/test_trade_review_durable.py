"""Durable trade review loop — SQLite, dismiss/watch materialization, API projections."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import ContractReference  # noqa: E402
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult  # noqa: E402
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    TRADE_REVIEW_DURABLE_LOOP_READY,
    TradeReviewMode,
    build_rejected_opportunity_review,
    build_watched_opportunity_review,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.intelligence.trade_review.sqlite_repository import (  # noqa: E402
    SqliteTradeReviewRepository,
)
from market_platform_foundation.local_state.schema import SCHEMA_VERSION  # noqa: E402
from market_platform_foundation.local_state.startup import open_local_state, reset_local_state_for_tests  # noqa: E402
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks  # noqa: E402
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    apply_opportunity_ack,
    build_opportunity_detail_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from market_platform_foundation.ui_api.trade_review_projections import (  # noqa: E402
    apply_trade_review_operator_patch,
    build_trade_reviews_for_opportunity_payload,
)  # noqa: E402

from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402


class TradeReviewDurableTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reset_local_state_for_tests()
        reset_trade_review_repository_for_tests()
        reset_operator_acks()

    def tearDown(self) -> None:
        reset_trade_review_repository_for_tests()
        reset_local_state_for_tests()
        reset_operator_acks()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        self._tmp.cleanup()

    def test_acceptance_label(self) -> None:
        self.assertEqual(TRADE_REVIEW_DURABLE_LOOP_READY, "TRADE_REVIEW_DURABLE_LOOP_READY")

    def test_schema_version_eight_includes_trade_reviews(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(local.connection.schema_version(), SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION, 8)
        tables = {
            str(row[0])
            for row in local.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("trade_reviews", tables)
        self.assertIn("trade_review_operator_edits", tables)

    def test_sqlite_restart_safe_put_get_list(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        repo = SqliteTradeReviewRepository(local.connection)
        review = build_watched_opportunity_review(
            opportunity_id="opp-durable-1",
            strategy_id="news_deterministic_baseline",
            decision_time_ns=100,
            created_at_ns=200,
            evidence_snapshot_refs=(ContractReference(kind="snapshot", id="snap-1"),),
        )
        self.assertEqual(repo.put_trade_review(review), RepositoryPutResult.INSERTED)
        reset_local_state_for_tests()
        restarted = open_local_state(force=True)
        assert restarted is not None
        repo2 = SqliteTradeReviewRepository(restarted.connection)
        restored = repo2.get_trade_review(review.review_id)
        assert restored is not None
        self.assertEqual(restored.review_mode, TradeReviewMode.WATCHED_OPPORTUNITY)
        self.assertIsNone(restored.execution_attribution)
        listed = repo2.list_trade_reviews_by_opportunity("opp-durable-1")
        self.assertEqual(len(listed), 1)

    def test_dismiss_materializes_without_execution_metrics(self) -> None:
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.execution_mode = "INTERNAL_SIMULATION"
        store.load()
        summary = __import__(
            "market_platform_foundation.ui_api.opportunity_projections",
            fromlist=["build_opportunities_summary_payload"],
        ).build_opportunities_summary_payload(store)
        if not summary.get("items"):
            self.skipTest("no ranked rows in replay fixture")
        row = summary["items"][0]
        opportunity_id = row.get("opportunity_id") or row["summary_id"]
        ack = apply_opportunity_ack(store, row_id=row["summary_id"], action="DISMISSED")
        self.assertIn("trade_review_id", ack)
        payload = build_trade_reviews_for_opportunity_payload(store, str(opportunity_id))
        self.assertEqual(payload["acceptance_label"], TRADE_REVIEW_DURABLE_LOOP_READY)
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["review_mode"], "REJECTED_OPPORTUNITY")
        self.assertIsNone(item.get("execution_attribution"))

    def test_operator_notes_append_only(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        repo = SqliteTradeReviewRepository(local.connection)
        review = build_rejected_opportunity_review(
            opportunity_id="opp-notes",
            strategy_id=None,
            decision_time_ns=1,
            created_at_ns=2,
        )
        repo.put_trade_review(review)
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        patched = apply_trade_review_operator_patch(
            store,
            review.review_id,
            {"notes": "Spread too wide; pass."},
        )
        self.assertEqual(patched["notes"], "Spread too wide; pass.")
        canonical = repo.get_trade_review_projection(review.review_id)
        assert canonical is not None
        self.assertTrue(canonical.get("canonical_immutable"))

    def test_detail_overlay_includes_trade_reviews(self) -> None:
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.execution_mode = "INTERNAL_SIMULATION"
        store.load()
        summary = __import__(
            "market_platform_foundation.ui_api.opportunity_projections",
            fromlist=["build_opportunities_summary_payload"],
        ).build_opportunities_summary_payload(store)
        if not summary.get("items"):
            self.skipTest("no ranked rows")
        row_id = summary["items"][0]["summary_id"]
        apply_opportunity_ack(store, row_id=row_id, action="WATCHED")
        detail = build_opportunity_detail_payload(store, row_id)
        self.assertTrue(detail.get("trade_reviews"))


if __name__ == "__main__":
    unittest.main()
