"""Runtime wiring tests for execution decision trace producers and durability."""

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
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.paper.eligibility import ensure_operator_fixture_registered  # noqa: E402
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    EXECUTION_DECISION_TRACE_RUNTIME_READY,
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
    verify_execution_decision_trace_replay,
)
from market_platform_foundation.rt01.execution_decision_trace.runtime import (  # noqa: E402
    record_preview_gate_block_trace,
)
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    apply_opportunity_ack,
    build_opportunities_summary_payload,
    build_opportunity_detail_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks  # noqa: E402
from market_platform_foundation.ui_api.paper_projections import (  # noqa: E402
    open_paper_session,
    preview_paper_order,
    submit_paper_order,
)
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402

from tests.ui1.test_ui_api import COLLECTION_ROOT  # noqa: E402

_STATUS_FLAG = EXECUTION_DECISION_TRACE_RUNTIME_READY


class ExecutionDecisionTraceRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        reset_execution_decision_trace_runtime_for_tests()
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["IMP_STATE_DIR"] = self._tmpdir.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.execution_mode = "INTERNAL_SIMULATION"
        self._seed_opportunity()

    def tearDown(self) -> None:
        reset_execution_decision_trace_runtime_for_tests()
        reset_operator_acks()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        self._tmpdir.cleanup()

    def _seed_opportunity(self, *, opportunity_id: str = "opp-trace-runtime-1") -> None:
        opportunity = OpportunityV1(
            opportunity_id=opportunity_id,
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
            created_at_ns=1_700_000_000_000_000_000,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.12,
            expected_net_edge=0.08,
            reason_summary="AAPL candidate",
            lineage_refs=(ContractReference(kind="forecast", id="fc-trace-1"),),
        )
        repo = InMemoryIntelligenceRepository()
        repo.put_opportunity(opportunity)
        self.store.strategy_repository = repo

    def _first_row_id(self) -> str:
        summary = build_opportunities_summary_payload(self.store)
        items = summary.get("items") or []
        if not items:
            self.skipTest("no opportunity rows in fixture")
        item = next((row for row in items if row.get("opportunity_id") == "opp-trace-runtime-1"), items[0])
        return str(item["summary_id"])

    def test_EXECUTION_DECISION_TRACE_RUNTIME_READY(self) -> None:
        self.assertEqual(_STATUS_FLAG, "EXECUTION_DECISION_TRACE_RUNTIME_READY")

    def test_operator_watch_and_dismiss_producers(self) -> None:
        row_id = self._first_row_id()
        build_opportunity_detail_payload(self.store, row_id)
        apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        apply_opportunity_ack(self.store, row_id=row_id, action="DISMISSED")
        repo = execution_decision_trace_repository()
        rows = repo.list_execution_decision_traces_by_opportunity("opp-trace-runtime-1")
        kinds = {row.decision_kind for row in rows}
        self.assertIn(ExecutionDecisionKind.SURFACE, kinds)
        self.assertIn(ExecutionDecisionKind.WATCH, kinds)
        self.assertIn(ExecutionDecisionKind.DISMISS, kinds)
        self.assertNotIn(ExecutionDecisionKind.PAPER_REQUESTED, kinds)

    def test_durable_readback_after_restart(self) -> None:
        row_id = self._first_row_id()
        build_opportunity_detail_payload(self.store, row_id)
        apply_opportunity_ack(self.store, row_id=row_id, action="WATCHED")
        repo = execution_decision_trace_repository()
        rows = repo.list_execution_decision_traces_by_opportunity("opp-trace-runtime-1")
        self.assertGreaterEqual(len(rows), 2)
        trace_id = next(row.decision_trace_id for row in rows if row.decision_kind == ExecutionDecisionKind.WATCH)
        reset_execution_decision_trace_runtime_for_tests()
        os.environ["IMP_STATE_DIR"] = self._tmpdir.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reloaded = execution_decision_trace_repository().get_execution_decision_trace(trace_id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.decision_kind, ExecutionDecisionKind.WATCH)

    def test_preview_blocked_without_placing_order(self) -> None:
        ensure_operator_fixture_registered()
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION", "preferred_instrument": self.store.instrument_id})
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(
                self.store,
                {
                    "client_order_id": "trace-block-1",
                    "idempotency_key": "trace-block-key-1",
                    "instrument_id": self.store.instrument_id,
                    "symbol": self.store.symbol,
                    "quantity": 1,
                    "side": "BUY",
                    "opportunity_id": "opp-trace-runtime-1",
                },
            )
        self.assertIn("PREVIEW_REQUIRED", str(ctx.exception))
        rows = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            "opp-trace-runtime-1"
        )
        blocked = [row for row in rows if row.decision_kind == ExecutionDecisionKind.PAPER_BLOCKED]
        self.assertEqual(len(blocked), 1)
        self.assertIn("PREVIEW_REQUIRED", blocked[0].blocker_codes)
        paper_requested = [row for row in rows if row.decision_kind == ExecutionDecisionKind.PAPER_REQUESTED]
        self.assertEqual(paper_requested, [])

    def test_preview_allowed_and_replay_determinism(self) -> None:
        ensure_operator_fixture_registered()
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION", "preferred_instrument": self.store.instrument_id})
        from market_platform_foundation.paper.execution import preview_interactive_order

        for index in range(len(self.store.bars) - 2, -1, -1):
            self.store.set_cursor_index(index)
            probe = preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="trace-probe",
                idempotency_key="trace-probe",
            )
            if probe.get("fill_preview") is not None and probe.get("risk_status") == "PASS":
                break
        else:
            self.skipTest("no fillable cursor on fixture")
        body = {
            "client_order_id": "trace-preview-1",
            "idempotency_key": "trace-preview-key-1",
            "instrument_id": self.store.instrument_id,
            "symbol": self.store.symbol,
            "quantity": 1,
            "side": "BUY",
            "opportunity_id": "opp-trace-runtime-1",
        }
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        rows = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
            "opp-trace-runtime-1"
        )
        allowed = [row for row in rows if row.decision_kind == ExecutionDecisionKind.PREVIEW_ALLOWED]
        self.assertEqual(len(allowed), 1)
        self.assertEqual(allowed[0].preview.preview_id if allowed[0].preview else None, preview_id)
        verification = verify_execution_decision_trace_replay(
            allowed[0],
            immutable_inputs={
                "decision_kind": ExecutionDecisionKind.PREVIEW_ALLOWED.value,
                "mode": "PAPER",
                "opportunity_id": "opp-trace-runtime-1",
                "preview_id": preview_id,
                "account_id": self.store.paper_ledger.paper_account_id,
            },
        )
        self.assertTrue(verification.identity_match)

    def test_revalidation_required_mapping(self) -> None:
        record = record_preview_gate_block_trace(
            self.store,
            {"opportunity_id": "opp-trace-runtime-1"},
            reason="PREVIEW_PORTFOLIO_STALE",
            decision_time_ns=1_700_000_000_000_000_001,
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.decision_kind, ExecutionDecisionKind.REVALIDATION_REQUIRED)
        loaded = execution_decision_trace_repository().get_execution_decision_trace(record.decision_trace_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.preview.status if loaded.preview else "", "REVALIDATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
