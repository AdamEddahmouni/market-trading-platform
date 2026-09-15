"""Deterministic WATCH/DISMISS learning-loop plumbing acceptance.

Evidence class: FIXTURE / SOFTWARE only. This module never claims live
empirical evidence, FTEP EMPIRICAL_ACTIVE, or production ranking restoration.

Proves the already-wired Paper path:

    ranked fixture OpportunityV1
    → operator WATCH / DISMISS
    → durable operator ack
    → ExecutionDecisionTrace (WATCH / DISMISS, plus SURFACE on detail)
    → TradeReviewV1 (WATCHED_OPPORTUNITY / REJECTED_OPPORTUNITY)
    → SQLite persistence
    → process restart
    → readback

Live mutations stay fail-closed in LIVE_OBSERVATIONAL. No Live enablement.
No production opportunity_projections live-gate edit (P1-owned). No frozen
RTH mutation.

Known gaps (documented, not patched here — hooks would collide with P1):

- ``ExecutionDecisionTraceV1.review_id`` is not populated by
  ``apply_opportunity_ack`` (trace is recorded before TradeReview materialize).
- ``TradeReviewV1.execution_decision_trace_id`` is contract-forbidden on
  WATCHED_OPPORTUNITY / REJECTED_OPPORTUNITY. Correlation is opportunity_id
  + action, not a shared foreign key.
- Live ranked book remains UNAVAILABLE by design; this harness seeds fixture
  OpportunityV1 into ``strategy_repository`` so downstream plumbing is
  known-good once live ranking is restored elsewhere.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.lifecycle import (  # noqa: E402
    OperatorLifecycleState,
)
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    TRADE_REVIEW_DURABLE_LOOP_READY,
    TradeReviewMode,
    open_trade_review_repository,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    EXECUTION_DECISION_TRACE_RUNTIME_READY,
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    apply_opportunity_ack,
    build_opportunities_summary_payload,
    build_opportunity_detail_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    list_operator_acks,
    reset_operator_acks,
)
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from market_platform_foundation.ui_api.trade_review_projections import (  # noqa: E402
    build_trade_reviews_for_opportunity_payload,
)

from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402

WATCH_DISMISS_LEARNING_LOOP_ACCEPTANCE = "WATCH_DISMISS_LEARNING_LOOP_ACCEPTANCE"
_EVIDENCE_CLASS = "FIXTURE_SOFTWARE_PLUMBING"
_FIXTURE_AS_OF_NS = 1_700_000_000_000_000_000
_WATCH_OPP = "opp-wd-watch-1"
_DISMISS_OPP = "opp-wd-dismiss-1"


def _fixture_opportunity(*, opportunity_id: str, instrument_id: str, headline: str) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=_FIXTURE_AS_OF_NS,
        quality=QualitySummary(state=QualityState.GOOD),
        side=OpportunitySide.LONG,
        expected_return=0.11,
        expected_net_edge=0.07,
        reason_summary=headline,
        lineage_refs=(ContractReference(kind="forecast", id=f"fc-{opportunity_id}"),),
    )


class WatchDismissLearningLoopAcceptanceTests(unittest.TestCase):
    """Fixture-only plumbing. Not live empirical evidence."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        os.environ.pop("IMP_LIVE_EXECUTION", None)
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.execution_mode = "INTERNAL_SIMULATION"
        self.store.mode = "PAPER"
        self.store.data_mode = "FIXTURE_REPLAY"
        self.store.opportunity_source = "REPLAY"
        self.store.as_of_time_ns = _FIXTURE_AS_OF_NS
        self.store.last_source_time_ns = _FIXTURE_AS_OF_NS
        repo = InMemoryIntelligenceRepository()
        repo.put_opportunity(
            _fixture_opportunity(
                opportunity_id=_WATCH_OPP,
                instrument_id="AAPL",
                headline="fixture watch candidate",
            )
        )
        repo.put_opportunity(
            _fixture_opportunity(
                opportunity_id=_DISMISS_OPP,
                instrument_id="MSFT",
                headline="fixture dismiss candidate",
            )
        )
        self.store.strategy_repository = repo

    def tearDown(self) -> None:
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        self._tmp.cleanup()

    def _ranked_ids(self) -> list[str]:
        payload = build_opportunities_summary_payload(self.store)
        return [
            str(item.get("opportunity_id") or item["summary_id"])
            for item in (payload.get("items") or [])
            if item.get("opportunity_id") in {_WATCH_OPP, _DISMISS_OPP}
            or item.get("summary_id") in {_WATCH_OPP, _DISMISS_OPP}
        ]

    def _row_id(self, opportunity_id: str) -> str:
        payload = build_opportunities_summary_payload(self.store)
        for item in payload.get("items") or []:
            if item.get("opportunity_id") == opportunity_id or item.get("summary_id") == opportunity_id:
                return str(item["summary_id"])
        self.fail(f"fixture opportunity {opportunity_id} missing from ranked book")

    def test_acceptance_label_is_software_not_empirical(self) -> None:
        self.assertEqual(WATCH_DISMISS_LEARNING_LOOP_ACCEPTANCE, "WATCH_DISMISS_LEARNING_LOOP_ACCEPTANCE")
        self.assertEqual(_EVIDENCE_CLASS, "FIXTURE_SOFTWARE_PLUMBING")
        self.assertEqual(TRADE_REVIEW_DURABLE_LOOP_READY, "TRADE_REVIEW_DURABLE_LOOP_READY")
        self.assertEqual(EXECUTION_DECISION_TRACE_RUNTIME_READY, "EXECUTION_DECISION_TRACE_RUNTIME_READY")

    def test_ranked_fixture_watch_dismiss_ack_trace_review_persist_restart_readback(self) -> None:
        ranked = self._ranked_ids()
        self.assertEqual(set(ranked), {_WATCH_OPP, _DISMISS_OPP})
        summary = build_opportunities_summary_payload(self.store)
        self.assertNotEqual(summary.get("feed_status"), "UNAVAILABLE")
        self.assertNotEqual(summary.get("reason"), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        for item in summary.get("items") or []:
            if item.get("opportunity_id") not in {_WATCH_OPP, _DISMISS_OPP}:
                continue
            self.assertEqual(item.get("identity_kind"), "OPPORTUNITY_V1")
            self.assertNotIn("rank_score", item)
            self.assertNotIn("universal_score", item)
            self.assertNotIn("order_id", item)

        watch_row = self._row_id(_WATCH_OPP)
        dismiss_row = self._row_id(_DISMISS_OPP)
        watch_detail = build_opportunity_detail_payload(self.store, watch_row)
        self.assertEqual(watch_detail.get("opportunity_id"), _WATCH_OPP)

        watch_ack = apply_opportunity_ack(self.store, row_id=watch_row, action="WATCHED")
        self.assertEqual(watch_ack["action"], OperatorLifecycleState.WATCHED.value)
        self.assertEqual(watch_ack["opportunity_id"], _WATCH_OPP)
        self.assertIn("trade_review_id", watch_ack)
        watch_review_id = str(watch_ack["trade_review_id"])

        dismiss_ack = apply_opportunity_ack(self.store, row_id=dismiss_row, action="DISMISSED")
        self.assertEqual(dismiss_ack["action"], OperatorLifecycleState.DISMISSED.value)
        self.assertEqual(dismiss_ack["opportunity_id"], _DISMISS_OPP)
        dismiss_review_id = str(dismiss_ack["trade_review_id"])

        after_dismiss = self._ranked_ids()
        self.assertIn(_WATCH_OPP, after_dismiss)
        self.assertNotIn(_DISMISS_OPP, after_dismiss)

        acks = list_operator_acks()
        actions = {(row["opportunity_id"], row["action"]) for row in acks}
        self.assertIn((_WATCH_OPP, "WATCHED"), actions)
        self.assertIn((_DISMISS_OPP, "DISMISSED"), actions)

        watch_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            _WATCH_OPP
        )
        dismiss_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            _DISMISS_OPP
        )
        watch_kinds = {row.decision_kind for row in watch_traces}
        dismiss_kinds = {row.decision_kind for row in dismiss_traces}
        self.assertIn(ExecutionDecisionKind.SURFACE, watch_kinds)
        self.assertIn(ExecutionDecisionKind.WATCH, watch_kinds)
        self.assertIn(ExecutionDecisionKind.DISMISS, dismiss_kinds)
        self.assertNotIn(ExecutionDecisionKind.PAPER_REQUESTED, watch_kinds)
        self.assertNotIn(ExecutionDecisionKind.BROKER_ACCEPTED, dismiss_kinds)

        watch_trace = next(row for row in watch_traces if row.decision_kind == ExecutionDecisionKind.WATCH)
        dismiss_trace = next(
            row for row in dismiss_traces if row.decision_kind == ExecutionDecisionKind.DISMISS
        )
        self.assertEqual(watch_trace.operator_action, OperatorLifecycleState.WATCHED)
        self.assertEqual(dismiss_trace.operator_action, OperatorLifecycleState.DISMISSED)
        self.assertEqual(watch_trace.mode, "PAPER")
        self.assertEqual(dismiss_trace.mode, "PAPER")

        watch_reviews = build_trade_reviews_for_opportunity_payload(self.store, _WATCH_OPP)
        dismiss_reviews = build_trade_reviews_for_opportunity_payload(self.store, _DISMISS_OPP)
        self.assertEqual(watch_reviews["acceptance_label"], TRADE_REVIEW_DURABLE_LOOP_READY)
        self.assertEqual(len(watch_reviews["items"]), 1)
        self.assertEqual(len(dismiss_reviews["items"]), 1)
        self.assertEqual(watch_reviews["items"][0]["review_mode"], TradeReviewMode.WATCHED_OPPORTUNITY.value)
        self.assertEqual(dismiss_reviews["items"][0]["review_mode"], TradeReviewMode.REJECTED_OPPORTUNITY.value)
        self.assertIsNone(watch_reviews["items"][0].get("execution_attribution"))
        self.assertIsNone(dismiss_reviews["items"][0].get("execution_attribution"))

        post_watch_detail = build_opportunity_detail_payload(self.store, watch_row)
        self.assertEqual(post_watch_detail.get("lifecycle_state"), "WATCHED")
        self.assertTrue(post_watch_detail.get("trade_reviews"))

        watch_trace_id = watch_trace.decision_trace_id
        dismiss_trace_id = dismiss_trace.decision_trace_id

        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"

        restored_acks = list_operator_acks()
        restored_actions = {(row["opportunity_id"], row["action"]) for row in restored_acks}
        self.assertIn((_WATCH_OPP, "WATCHED"), restored_actions)
        self.assertIn((_DISMISS_OPP, "DISMISSED"), restored_actions)

        restored_watch_trace = execution_decision_trace_repository().get_execution_decision_trace(
            watch_trace_id
        )
        restored_dismiss_trace = execution_decision_trace_repository().get_execution_decision_trace(
            dismiss_trace_id
        )
        self.assertIsNotNone(restored_watch_trace)
        self.assertIsNotNone(restored_dismiss_trace)
        assert restored_watch_trace is not None
        assert restored_dismiss_trace is not None
        self.assertEqual(restored_watch_trace.decision_kind, ExecutionDecisionKind.WATCH)
        self.assertEqual(restored_dismiss_trace.decision_kind, ExecutionDecisionKind.DISMISS)
        self.assertEqual(restored_watch_trace.opportunity_id, _WATCH_OPP)
        self.assertEqual(restored_dismiss_trace.opportunity_id, _DISMISS_OPP)

        review_repo = open_trade_review_repository()
        restored_watch_review = review_repo.get_trade_review(watch_review_id)
        restored_dismiss_review = review_repo.get_trade_review(dismiss_review_id)
        self.assertIsNotNone(restored_watch_review)
        self.assertIsNotNone(restored_dismiss_review)
        assert restored_watch_review is not None
        assert restored_dismiss_review is not None
        self.assertEqual(restored_watch_review.review_mode, TradeReviewMode.WATCHED_OPPORTUNITY)
        self.assertEqual(restored_dismiss_review.review_mode, TradeReviewMode.REJECTED_OPPORTUNITY)
        self.assertEqual(restored_watch_review.opportunity_id, _WATCH_OPP)
        self.assertEqual(restored_dismiss_review.opportunity_id, _DISMISS_OPP)
        self.assertIsNone(restored_watch_review.execution_attribution)
        self.assertIsNone(restored_dismiss_review.execution_attribution)
        listed_watch = review_repo.list_trade_reviews_by_opportunity(_WATCH_OPP)
        listed_dismiss = review_repo.list_trade_reviews_by_opportunity(_DISMISS_OPP)
        self.assertEqual(len(listed_watch), 1)
        self.assertEqual(len(listed_dismiss), 1)

    def test_live_observational_watch_dismiss_fail_closed_without_mutation(self) -> None:
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        live_summary = build_opportunities_summary_payload(self.store)
        self.assertEqual(live_summary["feed_status"], "UNAVAILABLE")
        self.assertEqual(live_summary["reason"], "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        self.assertEqual(live_summary["items"], [])
        with self.assertRaises(KeyError) as detail_ctx:
            build_opportunity_detail_payload(self.store, _WATCH_OPP)
        self.assertEqual(str(detail_ctx.exception), "'LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE'")
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id=_WATCH_OPP, action="WATCHED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        with self.assertRaises(PermissionError) as dismiss_ctx:
            apply_opportunity_ack(self.store, row_id=_DISMISS_OPP, action="DISMISSED")
        self.assertEqual(str(dismiss_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        self.assertEqual(list_operator_acks(), ())
        self.assertEqual(
            execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(_WATCH_OPP),
            (),
        )
        self.assertEqual(open_trade_review_repository().list_trade_reviews_by_opportunity(_WATCH_OPP), ())
        live_reviews = build_trade_reviews_for_opportunity_payload(self.store, _WATCH_OPP)
        self.assertEqual(live_reviews["items"], [])
        self.assertEqual(live_reviews["reason"], "LIVE_OBSERVATIONAL_NO_TRADE_REVIEW")

    def test_demo_mutations_fail_closed(self) -> None:
        self.store.execution_mode = "NONE"
        self.store.mode = "REPLAY"
        with self.assertRaises(PermissionError) as ctx:
            apply_opportunity_ack(self.store, row_id=_WATCH_OPP, action="WATCHED")
        self.assertEqual(str(ctx.exception), "DEMO_MUTATIONS_PROHIBITED")
        self.assertEqual(list_operator_acks(), ())

    def test_documented_gap_trace_review_foreign_key_unwired(self) -> None:
        """Current software: traces and reviews correlate by opportunity_id.

        P1 owns ``opportunity_projections`` live-gate. This lane does not edit
        that file to back-fill ``review_id`` on the trace after materialize.
        """
        row_id = self._row_id(_WATCH_OPP)
        build_opportunity_detail_payload(self.store, row_id)
        ack = apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            _WATCH_OPP
        )
        watch_trace = next(row for row in traces if row.decision_kind == ExecutionDecisionKind.WATCH)
        review = open_trade_review_repository().get_trade_review(str(ack["trade_review_id"]))
        assert review is not None
        self.assertIsNone(watch_trace.review_id)
        self.assertIsNone(review.execution_decision_trace_id)
        self.assertEqual(watch_trace.opportunity_id, review.opportunity_id)
        self.assertEqual(review.decision, OperatorLifecycleState.WATCHED.value)


if __name__ == "__main__":
    unittest.main()
