"""RT-01 Paper trace contract tests."""

from __future__ import annotations

import unittest

from types import SimpleNamespace

from market_platform_foundation.intelligence.contracts.common import QualityState
from market_platform_foundation.intelligence.signals.engine import compute_fast_signals
from market_platform_foundation.intelligence.signals.models import SignalComputationRequest
from market_platform_foundation.market_data.bounded_queue import BoundedIngestQueue
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.rt01.collector import InMemoryTraceCollector
from market_platform_foundation.rt01.baseline import run_baseline
from market_platform_foundation.rt01.context import bind_context, reset_context
from market_platform_foundation.rt01.enums import SamplingMode, TraceStage, TraceStatus
from market_platform_foundation.rt01.instrumentation.paper import (
    PaperTrace,
    start_paper_trace,
    trace_refs,
)
from market_platform_foundation.rt01.profiles import profile_by_id
from market_platform_foundation.rt01.tracer import Tracer, configure_tracer
from market_platform_foundation.rt01.workloads import run_paper_trace_workload


class PaperTraceTests(unittest.TestCase):
    def test_queue_wait_creates_trace_span(self) -> None:
        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        configure_tracer(tracer)
        trace = start_paper_trace("paper_queue", correlation_id="corr-queue", tracer=tracer)
        token = bind_context(trace.context)
        try:
            queue: BoundedIngestQueue[dict[str, str]] = BoundedIngestQueue(max_size=2)
            self.assertTrue(queue.enqueue({"instrument_id": "AAPL"}))
            self.assertEqual(queue.dequeue_batch(limit=1), [{"instrument_id": "AAPL"}])
        finally:
            reset_context(token)
            trace.finish()
        queue_spans = [span for span in collector.spans if span.stage == TraceStage.QUEUE]
        self.assertEqual(len(queue_spans), 1)
        self.assertGreaterEqual(queue_spans[0].clocks.duration_ns, 0)
        self.assertIsNotNone(queue_spans[0].queue_enqueue_mono_ns)
        self.assertIsNotNone(queue_spans[0].queue_dequeue_mono_ns)

    def test_signal_computation_creates_trace_span(self) -> None:
        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        configure_tracer(tracer)
        trace = start_paper_trace("paper_signal", correlation_id="corr-signal", tracer=tracer)
        token = bind_context(trace.context)
        try:
            resolved = SimpleNamespace(
                snapshot=SimpleNamespace(quality=SimpleNamespace(state=QualityState.INVALID))
            )
            request = SignalComputationRequest(
                window_ns=60,
                signal_types=frozenset(),
                depth_levels=1,
                require_all=False,
                persist=False,
                parameters={},
            )
            compute_fast_signals(resolved, request)
        finally:
            reset_context(token)
            trace.finish()
        signal_spans = [span for span in collector.spans if span.stage == TraceStage.SIGNAL]
        self.assertEqual(len(signal_spans), 1)

    def test_internal_paper_submission_creates_order_ready_span(self) -> None:
        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        configure_tracer(tracer)
        trace = start_paper_trace("paper_submit", correlation_id="corr-submit", tracer=tracer)
        token = bind_context(trace.context)
        try:
            ledger = PaperExecutionLedger.open_session(
                replay_session_id="rt01-paper-submit",
                instrument_id="AAPL",
                symbol="AAPL",
                execution_mode="INTERNAL_SIMULATION",
                execution_authority="PAPER_ONLY",
            )
            result = submit_interactive_order(
                ledger=ledger,
                bars=[
                    {
                        "available_time": 2,
                        "bar_payload": {"high": "101", "low": "99", "volume": 1000},
                        "normalized_event_id": "bar-2",
                    }
                ],
                symbol="AAPL",
                instrument_id="AAPL",
                side="BUY",
                quantity=1,
                observation_time=1,
                client_order_id="client-submit",
                idempotency_key="key-submit",
            )
        finally:
            reset_context(token)
            trace.finish(output_ref="submission")
        self.assertFalse(result["duplicate"])
        self.assertTrue(
            any(
                span.stage == TraceStage.ORDER_READY
                and span.correlation_id == "corr-submit"
                for span in collector.spans
            )
        )

    def test_trace_links_root_and_children_with_bounded_refs(self) -> None:
        collector = InMemoryTraceCollector()
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        trace = start_paper_trace(
            "paper_order",
            correlation_id="corr-123",
            tracer=tracer,
        )

        signal = trace.child(
            TraceStage.SIGNAL,
            "compute_signal",
            signal_id="signal-1",
            very_long_reference="x" * 200,
        )
        if signal:
            signal.end(output_ref="signal-1")
        decision = trace.child(
            TraceStage.RISK,
            "assess_risk",
            risk_decision_id="risk-1",
        )
        if decision:
            decision.end(output_ref="risk-1")
        trace.finish(output_ref="order-1")

        spans = collector.spans
        self.assertEqual(len(spans), 3)
        root = next(span for span in spans if span.stage == TraceStage.TRACE_ROOT)
        child = next(span for span in spans if span.stage == TraceStage.SIGNAL)
        self.assertEqual(root.correlation_id, "corr-123")
        self.assertEqual(child.parent_span_id, root.span_id)
        self.assertEqual(child.attributes["signal_id"], "signal-1")
        self.assertLessEqual(len(child.attributes["very_long_reference"]), 64)

    def test_trace_is_safe_when_disabled(self) -> None:
        trace = start_paper_trace(
            "disabled_paper_order",
            correlation_id="corr-off",
            tracer=Tracer(mode=SamplingMode.OFF),
        )
        self.assertIsInstance(trace, PaperTrace)
        self.assertIsNone(
            trace.child(TraceStage.ORDER_READY, "order_ready", order_id="order-off")
        )
        self.assertIsNone(trace.finish(output_ref="order-off"))

    def test_error_and_termination_are_recorded(self) -> None:
        collector = InMemoryTraceCollector()
        trace = start_paper_trace(
            "paper_failure",
            correlation_id="corr-failure",
            tracer=Tracer(mode=SamplingMode.FULL, collector=collector),
        )
        trace.finish(
            status=TraceStatus.ERROR,
            error_code="PAPER_ORDER_FAILED",
            terminated=True,
        )
        root = collector.spans[0]
        self.assertEqual(root.status, TraceStatus.TERMINATED)
        self.assertEqual(root.error_code, "PAPER_ORDER_FAILED")
        self.assertGreaterEqual(root.clocks.duration_ns, 0)

    def test_trace_refs_only_emits_bounded_non_empty_values(self) -> None:
        refs = trace_refs(
            signal_id="signal-1",
            order_id="order-1",
            empty="",
            none_value=None,
            secret_token="token-value",
        )
        self.assertEqual(refs["signal_id"], "signal-1")
        self.assertEqual(refs["order_id"], "order-1")
        self.assertNotIn("empty", refs)
        self.assertNotIn("none_value", refs)
        self.assertNotIn("secret_token", refs)

    def test_paper_latency_profiles_are_registered(self) -> None:
        for profile_id in (
            "queue_wait",
            "queue_to_signal",
            "signal_to_decision",
            "decision_to_submission",
            "submission_to_broker",
            "broker_to_reconciliation",
            "paper_end_to_end",
        ):
            profile = profile_by_id(profile_id)
            self.assertIsNotNone(profile, profile_id)
            self.assertEqual(profile.clock_basis, "process_monotonic_ns")
            self.assertTrue(profile.terminal_stages)

    def test_paper_workload_produces_end_to_end_samples(self) -> None:
        report = run_baseline(
            profile_id="paper_end_to_end",
            workload_fn=run_paper_trace_workload,
            iterations=2,
            warmup_iterations=1,
        )
        self.assertEqual(report["measurement_class"], "MEASURED_BASELINE")
        self.assertGreater(report["statistics"]["count"], 0)
        self.assertEqual(report["sample_count"], report["raw_sample_count"])
        self.assertEqual(report["terminal_stages"], ["reconciliation"])


if __name__ == "__main__":
    unittest.main()
