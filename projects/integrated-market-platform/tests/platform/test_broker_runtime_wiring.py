"""Canonical Paper runtime wiring for broker-paper execution."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from market_platform_foundation.providers.composition import (
    ProviderComposition,
    configure_provider_composition,
    with_broker_paper_execution,
)
from market_platform_foundation.providers.adapters.tradier_paper import (
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
)
from market_platform_foundation.rt01.collector import InMemoryTraceCollector
from market_platform_foundation.rt01.context import bind_context, reset_context
from market_platform_foundation.rt01.enums import SamplingMode, TraceStage
from market_platform_foundation.rt01.instrumentation.paper import start_paper_trace
from market_platform_foundation.rt01.tracer import Tracer, configure_tracer
from market_platform_foundation.ui_api.paper_projections import (
    cancel_paper_order,
    open_paper_session,
    poll_broker_order,
    preview_paper_order,
    reconcile_broker_paper,
    submit_paper_order,
)
from market_platform_foundation.ui_api.broker_projections import (
    build_broker_reconciliation_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent


def _preview_and_submit(store: ReplayStore, body: dict) -> dict:
    """G3 preview-first submit: issue a server preview, then submit bound to it."""
    preview = preview_paper_order(store, body)
    preview_id = str(preview["preview"]["preview_id"])
    return submit_paper_order(store, {**body, "preview_id": preview_id})


class BrokerRuntimeWiringTests(unittest.TestCase):
    _warm_store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls._warm_store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls._warm_store.load()

    def setUp(self) -> None:
        self._env = {
            "IMP_PAPER_EXECUTION": "1",
            "IMP_BROKER_PAPER_EXECUTION": "1",
            "IMP_TRADIER_PAPER": "1",
            "IMP_TRADIER_TOKEN": "fixture-token",
            "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
            "IMP_TRADIER_ACCOUNT_ID": "acct-runtime",
        }
        self._prior = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.hydrate_replay_bars_from(self.__class__._warm_store)
        self.store.refresh_mutable_runtime()
        composition = with_broker_paper_execution(
            ProviderComposition(),
            env=dict(self._env),
            symbol_map={"BIYA": "BIYA"},
            replay_store=TradierReplayStore.load(),
        )
        configure_provider_composition(composition)

    def tearDown(self) -> None:
        configure_provider_composition(None)
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _open_broker_session(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(self.store, {"execution_mode": "BROKER_PAPER"})
        # G3 BL-0202: broker MARKET buys require a current price reference
        # (live mark). The real UI path applies marks from the live runtime;
        # this fixture environment has no runtime, so supply the mark the
        # runtime would provide (fixture fills execute near $116.20).
        self.store.paper_ledger.apply_live_mark(
            mark_minor=11620,
            mark_provider="TRADIER",
            mark_as_of_ns=1787000000000000000,
            mark_quality="TEST",
        )

    def test_broker_session_binds_composed_provider(self) -> None:
        self._open_broker_session()

        self.assertEqual(self.store.paper_ledger.execution_mode, "BROKER_PAPER")
        self.assertEqual(self.store.paper_ledger.execution_authority, "PAPER_ONLY")
        self.assertEqual(self.store.paper_ledger.execution_provider, "tradier.paper")

    def test_broker_preview_is_dry_run(self) -> None:
        self._open_broker_session()
        before = len(self.store.paper_ledger.events)

        result = preview_paper_order(
            self.store,
            {
                "side": "BUY",
                "quantity": 1,
                "client_order_id": "broker-preview",
                "idempotency_key": "broker-preview-key",
            },
        )

        self.assertEqual(len(self.store.paper_ledger.events), before)
        self.assertEqual(result["preview"]["execution_mode"], "BROKER_PAPER")
        self.assertEqual(result["preview"]["execution_provider"], "tradier.paper")

    def test_broker_submission_dispatches_to_composed_provider(self) -> None:
        self._open_broker_session()

        result = _preview_and_submit(
            self.store,
            {
                "side": "BUY",
                "quantity": 100,
                "client_order_id": "cli-broker-partial-1",
                "idempotency_key": "key-broker-partial-1",
            },
        )

        submission = result["submission"]
        self.assertFalse(submission["duplicate"])
        self.assertEqual(submission["order"]["state"], "PARTIALLY_FILLED")
        self.assertEqual(submission["order"]["broker_order_id"], "TR-PART-0001")

    def test_broker_poll_advances_partial_order_through_runtime(self) -> None:
        self._open_broker_session()
        submitted = _preview_and_submit(
            self.store,
            {
                "side": "BUY",
                "quantity": 100,
                "client_order_id": "cli-broker-partial-1",
                "idempotency_key": "key-broker-partial-1",
            },
        )["submission"]
        order_id = str(submitted["order_id"])
        fills = self.store.paper_ledger.project_fills()
        provider = self.store.paper_ledger
        del provider
        composition = with_broker_paper_execution(
            ProviderComposition(),
            env=dict(self._env),
            symbol_map={"BIYA": "BIYA"},
            replay_store=TradierReplayStore.load(),
        )
        composition.paper_execution._replay.add_record(
            operation="fetch_order",
            match={"broker_order_id": "TR-PART-0001"},
            response={
                "broker_order_id": "TR-PART-0001",
                "status": "filled",
                "status_raw": "filled",
                "event_time_ns": 1787000000900000000,
                "receive_time_ns": 1787000000900500000,
                "filled_quantity": 100,
                "fills": [
                    *[
                        {
                            "broker_fill_id": row["broker_fill_id"],
                            "quantity": row["fill_quantity"],
                            "price_minor": row["fill_price_minor"],
                            "event_time_ns": row["fill_time"],
                            "receive_time_ns": row["fill_time"],
                        }
                        for row in fills
                    ],
                    {
                        "broker_fill_id": "TR-RUNTIME-FINAL",
                        "quantity": 60,
                        "price_minor": 11610,
                        "event_time_ns": 1787000000900000000,
                        "receive_time_ns": 1787000000900100000,
                    },
                ],
            },
        )
        configure_provider_composition(composition)

        result = poll_broker_order(self.store, {"order_id": order_id})

        self.assertEqual(result["poll"]["state"], "FILLED")
        self.assertEqual(len(self.store.paper_ledger.project_fills()), len(fills) + 1)

    def test_broker_reconciliation_records_report(self) -> None:
        self._open_broker_session()
        _preview_and_submit(
            self.store,
            {
                "side": "BUY",
                "quantity": 100,
                "client_order_id": "cli-broker-market-1",
                "idempotency_key": "key-broker-market-1",
            },
        )

        result = reconcile_broker_paper(self.store)

        self.assertIn(result["reconciliation"]["overall_status"], {"MATCHED", "MISMATCH"})
        self.assertTrue(result["reconciliation"]["report_id"])
        self.assertEqual(
            self.store.paper_ledger.events[-1]["event_type"],
            "ReconciliationRecorded",
        )

    def test_broker_lifecycle_and_reconciliation_share_trace(self) -> None:
        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        configure_tracer(tracer)
        self._open_broker_session()
        trace = start_paper_trace(
            "broker_paper_lifecycle",
            correlation_id="broker-trace-1",
            tracer=tracer,
        )
        token = bind_context(trace.context)
        try:
            _preview_and_submit(
                self.store,
                {
                    "side": "BUY",
                    "quantity": 100,
                    "client_order_id": "cli-broker-market-1",
                    "idempotency_key": "key-broker-market-1",
                },
            )
            reconcile_broker_paper(self.store)
            build_broker_reconciliation_payload(self.store)
        finally:
            reset_context(token)
            trace.finish()

        broker_spans = [
            span for span in collector.spans if span.stage == TraceStage.BROKER
        ]
        reconciliation_spans = [
            span
            for span in collector.spans
            if span.stage == TraceStage.RECONCILIATION
        ]
        self.assertTrue(broker_spans)
        self.assertTrue(reconciliation_spans)
        self.assertEqual(
            {span.trace_id for span in broker_spans + reconciliation_spans},
            {trace.root.context.trace_id},
        )
        self.assertEqual(
            {span.correlation_id for span in broker_spans + reconciliation_spans},
            {"broker-trace-1"},
        )
        self.assertIn(
            "TR-FILL-0001",
            {
                span.attributes.get("broker_order_id")
                for span in broker_spans
                if span.attributes.get("broker_order_id")
            },
        )
        self.assertTrue(
            any(span.attributes.get("report_id") for span in reconciliation_spans)
        )
        self.assertTrue(
            any(span.operation == "build_broker_reconciliation_payload" for span in reconciliation_spans)
        )

    def test_fixture_pipeline_shares_one_trace_id(self) -> None:
        """One bound root spans opportunity → risk → order_ready → broker → reconcile."""
        from tests.intelligence.test_equity_paper_runtime import _runtime_fixture

        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        configure_tracer(tracer)
        self._open_broker_session()
        trace = start_paper_trace(
            "rt01_fixture_pipeline",
            correlation_id="rt01-fixture-shared",
            tracer=tracer,
        )
        token = bind_context(trace.context)
        try:
            opportunity = trace.child(
                TraceStage.OPPORTUNITY,
                "strategy_opportunity_pipeline",
                decision_time_ns="fixture",
            )
            runtime, _repository, request, _forecast = _runtime_fixture(
                session_id="rt01-shared-trace-entry",
            )
            result = runtime.run_entry(request)
            if opportunity is not None:
                opportunity.end(output_ref=result.status)
            submitted = _preview_and_submit(
                self.store,
                {
                    "side": "BUY",
                    "quantity": 1,
                    "order_type": "LIMIT",
                    "limit_price_minor": 11600,
                    "client_order_id": "cli-broker-limit-1",
                    "idempotency_key": "key-broker-limit-1",
                },
            )["submission"]
            order_id = str(submitted["order_id"])
            poll_broker_order(self.store, {"order_id": order_id})
            cancel_paper_order(self.store, {"order_id": order_id})
            reconcile_broker_paper(self.store)
        finally:
            reset_context(token)
            trace.finish()

        self.assertEqual(result.status, "FILLED")
        root_id = trace.root.context.trace_id
        required = (
            TraceStage.OPPORTUNITY,
            TraceStage.RISK,
            TraceStage.ORDER_READY,
            TraceStage.BROKER,
            TraceStage.RECONCILIATION,
        )
        by_stage = {stage: [span for span in collector.spans if span.stage == stage] for stage in required}
        for stage, spans in by_stage.items():
            self.assertTrue(spans, msg=f"missing {stage.value} span")
            self.assertEqual({span.trace_id for span in spans}, {root_id})
        self.assertTrue(any(span.operation == "poll_broker_order" for span in by_stage[TraceStage.BROKER]))
        self.assertTrue(
            any(span.operation == "cancel_broker_paper_order" for span in by_stage[TraceStage.BROKER])
        )
        self.assertTrue(
            any(span.operation == "reconcile_broker_paper" for span in by_stage[TraceStage.RECONCILIATION])
        )


if __name__ == "__main__":
    unittest.main()
