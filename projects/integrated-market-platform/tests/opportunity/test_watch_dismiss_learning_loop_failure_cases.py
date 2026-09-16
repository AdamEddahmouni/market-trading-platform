"""Failure-case WATCH/DISMISS plumbing. Fixture / SOFTWARE only.

Not live empirical evidence. Not FTEP EMPIRICAL_ACTIVE. Live stays off.
Does not edit P1-owned opportunity_projections live-gate. Persistence
restart is covered by the happy-path acceptance module and is not repeated.
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
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.freshness import (  # noqa: E402
    DEFAULT_STALE_AFTER_NS,
    FRESHNESS_STALE,
)
from market_platform_foundation.intelligence.opportunity.lifecycle import (  # noqa: E402
    OperatorLifecycleState,
)
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    open_trade_review_repository,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    apply_opportunity_ack,
    build_opportunities_summary_payload,
    build_opportunity_detail_payload,
    build_opportunity_evidence_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    list_operator_acks,
    reset_operator_acks,
)
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from market_platform_foundation.ui_api.trade_review_projections import (  # noqa: E402
    build_trade_reviews_for_opportunity_payload,
)

from tests.opportunity.test_watch_dismiss_learning_loop_acceptance import (  # noqa: E402
    _DISMISS_OPP,
    _EVIDENCE_CLASS,
    _FIXTURE_AS_OF_NS,
    _WATCH_OPP,
    _fixture_opportunity,
)
from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402

_STALE_OPP = "opp-wd-stale-1"
_NO_EVIDENCE_OPP = "opp-wd-no-evidence-1"
_INVALID_INSTRUMENT_OPP = "opp-wd-unknown-instrument-1"


class WatchDismissLearningLoopFailureCaseTests(unittest.TestCase):
    """Fixture-only fail-closed cases. Not live empirical evidence."""

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
        self.repo = InMemoryIntelligenceRepository()
        self.repo.put_opportunity(
            _fixture_opportunity(
                opportunity_id=_WATCH_OPP,
                instrument_id="AAPL",
                headline="fixture watch candidate",
            )
        )
        self.store.strategy_repository = self.repo

    def tearDown(self) -> None:
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        self._tmp.cleanup()

    def _summary_ids(self) -> set[str]:
        payload = build_opportunities_summary_payload(self.store)
        ids: set[str] = set()
        for item in payload.get("items") or []:
            if item.get("opportunity_id"):
                ids.add(str(item["opportunity_id"]))
            if item.get("summary_id"):
                ids.add(str(item["summary_id"]))
        return ids

    def _row_id(self, opportunity_id: str) -> str:
        payload = build_opportunities_summary_payload(self.store)
        for item in payload.get("items") or []:
            if item.get("opportunity_id") == opportunity_id or item.get("summary_id") == opportunity_id:
                return str(item["summary_id"])
        self.fail(f"fixture opportunity {opportunity_id} missing from ranked book")

    def _assert_no_watch_mutation(self, opportunity_id: str) -> None:
        self.assertFalse(
            any(row.get("opportunity_id") == opportunity_id for row in list_operator_acks())
        )
        self.assertEqual(
            execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                opportunity_id
            ),
            (),
        )
        self.assertEqual(open_trade_review_repository().list_trade_reviews_by_opportunity(opportunity_id), ())

    def test_evidence_class_remains_fixture_software(self) -> None:
        self.assertEqual(_EVIDENCE_CLASS, "FIXTURE_SOFTWARE_PLUMBING")

    def test_stale_opportunity_is_not_ranked_and_ack_fails_closed(self) -> None:
        self.repo.put_opportunity(
            _fixture_opportunity(
                opportunity_id=_STALE_OPP,
                instrument_id="AAPL",
                headline="stale observational candidate",
            )
        )
        self.store.opportunity_source = "OBSERVATIONAL"
        self.store.last_source_time_ns = _FIXTURE_AS_OF_NS
        self.store.as_of_time_ns = _FIXTURE_AS_OF_NS + DEFAULT_STALE_AFTER_NS + 1
        payload = build_opportunities_summary_payload(self.store)
        self.assertNotIn(_STALE_OPP, self._summary_ids())
        for item in payload.get("items") or []:
            quality = item.get("data_quality") or {}
            evaluation = quality.get("freshness_evaluation") or {}
            if evaluation.get("status") == FRESHNESS_STALE:
                self.assertNotEqual(item.get("opportunity_id"), _STALE_OPP)
        with self.assertRaises(KeyError):
            apply_opportunity_ack(self.store, row_id=_STALE_OPP, action="WATCHED")
        self._assert_no_watch_mutation(_STALE_OPP)

    def test_missing_evidence_does_not_fabricate_and_unknown_row_fails(self) -> None:
        bare = OpportunityV1(
            opportunity_id=_NO_EVIDENCE_OPP,
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
            created_at_ns=_FIXTURE_AS_OF_NS,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            reason_summary="fixture candidate without lineage",
        )
        self.repo.put_opportunity(bare)
        row_id = self._row_id(_NO_EVIDENCE_OPP)
        evidence = build_opportunity_evidence_payload(self.store, row_id)
        self.assertEqual(evidence.get("identity_kind"), "OPPORTUNITY_V1")
        self.assertEqual(evidence.get("lineage_refs") or [], [])
        self.assertEqual(evidence.get("items") or [], [])
        self.assertNotIn("last_price", evidence)
        self.assertNotIn("quote", evidence)
        ack = apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        review = open_trade_review_repository().get_trade_review(str(ack["trade_review_id"]))
        assert review is not None
        self.assertEqual(review.evidence_snapshot_refs, ())
        self.assertEqual(review.opportunity_id, _NO_EVIDENCE_OPP)
        with self.assertRaises(KeyError):
            apply_opportunity_ack(self.store, row_id="opp-wd-missing-row", action="WATCHED")
        self._assert_no_watch_mutation("opp-wd-missing-row")

    def test_duplicate_watch_ack_is_idempotent(self) -> None:
        row_id = self._row_id(_WATCH_OPP)
        first = apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        second = apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        self.assertEqual(first["action"], OperatorLifecycleState.WATCHED.value)
        self.assertEqual(second["action"], OperatorLifecycleState.WATCHED.value)
        self.assertEqual(first["trade_review_id"], second["trade_review_id"])
        watched = [row for row in list_operator_acks() if row["opportunity_id"] == _WATCH_OPP]
        self.assertEqual(len(watched), 1)
        self.assertEqual(watched[0]["action"], "WATCHED")
        reviews = open_trade_review_repository().list_trade_reviews_by_opportunity(_WATCH_OPP)
        self.assertEqual(len(reviews), 1)
        traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            _WATCH_OPP
        )
        watch_traces = [row for row in traces if row.decision_kind == ExecutionDecisionKind.WATCH]
        self.assertEqual(len(watch_traces), 1)

    def test_invalid_opportunity_and_invalid_action_fail_closed(self) -> None:
        self.repo.put_opportunity(
            _fixture_opportunity(
                opportunity_id=_INVALID_INSTRUMENT_OPP,
                instrument_id="UNKNOWN",
                headline="invalid unknown instrument",
            )
        )
        self.assertNotIn(_INVALID_INSTRUMENT_OPP, self._summary_ids())
        with self.assertRaises(KeyError):
            apply_opportunity_ack(self.store, row_id=_INVALID_INSTRUMENT_OPP, action="WATCHED")
        self._assert_no_watch_mutation(_INVALID_INSTRUMENT_OPP)
        row_id = self._row_id(_WATCH_OPP)
        with self.assertRaises(ValueError) as ctx:
            apply_opportunity_ack(self.store, row_id=row_id, action="WATCH")
        self.assertIn("WATCH", str(ctx.exception))
        self._assert_no_watch_mutation(_WATCH_OPP)

    def test_live_observational_unauthorized_mode_still_fail_closed(self) -> None:
        self.assertIsNone(os.environ.get("IMP_LIVE_OBSERVATIONAL"))
        self.assertIsNone(os.environ.get("IMP_LIVE_EXECUTION"))
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        summary = build_opportunities_summary_payload(self.store)
        self.assertEqual(summary["feed_status"], "UNAVAILABLE")
        self.assertEqual(summary["reason"], "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        self.assertEqual(summary["items"], [])
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
        live_reviews = build_trade_reviews_for_opportunity_payload(self.store, _WATCH_OPP)
        self.assertEqual(live_reviews["items"], [])
        self.assertEqual(live_reviews["reason"], "LIVE_OBSERVATIONAL_NO_TRADE_REVIEW")
        self._assert_no_watch_mutation(_WATCH_OPP)


if __name__ == "__main__":
    unittest.main()
