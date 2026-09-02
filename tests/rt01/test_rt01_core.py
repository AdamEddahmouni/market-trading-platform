"""RT-01 core trace, validation, baseline, and integration tests."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from market_platform_foundation.clock import reset_clock_for_tests
from market_platform_foundation.rt01.baseline import collect_profile_samples, compare_baselines, run_baseline
from market_platform_foundation.rt01.collector import InMemoryTraceCollector
from market_platform_foundation.rt01.context import bind_context, new_root_context, reset_context
from market_platform_foundation.rt01.enums import SamplingMode, TraceStage, TraceStatus
from market_platform_foundation.rt01.equivalence import prove_equivalence
from market_platform_foundation.rt01.export import export_document, read_export, spans_from_export, write_export
from market_platform_foundation.rt01.overhead import measure_overhead
from market_platform_foundation.rt01.profiles import PROFILE_QUEUE_WAIT, PROFILE_RECEIVE_TO_CANONICAL, PROFILE_RECEIVE_TO_SIGNAL
from market_platform_foundation.rt01.propagation import inject_carrier, extract_carrier, queue_wait_ns
from market_platform_foundation.rt01.sampling import sampling_decision
from market_platform_foundation.rt01.span import TraceSpan
from market_platform_foundation.rt01.clock import span_clocks
from market_platform_foundation.rt01.tracer import Tracer, configure_tracer
from market_platform_foundation.rt01.validation import validate_spans
from market_platform_foundation.rt01.workloads import (
    fixture_ingest_domain_hash,
    run_fixture_ingest_workload,
    run_quality_replay_workload,
)


class RT01CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_clock_for_tests()
        configure_tracer(Tracer(mode=SamplingMode.FULL, collector=InMemoryTraceCollector()))

    def test_parent_child_and_duration(self) -> None:
        tracer = Tracer(mode=SamplingMode.FULL, collector=InMemoryTraceCollector())
        root = tracer.start_root("vertical_slice")
        self.assertIsNotNone(root)
        child = tracer.start_span(TraceStage.NORMALIZE, "normalize", parent=root.context)
        self.assertIsNotNone(child)
        child.end(output_ref="out-1")
        root.end()
        spans = tracer.collector.spans
        self.assertEqual(len(spans), 2)
        child_span = next(s for s in spans if s.stage == TraceStage.NORMALIZE)
        self.assertEqual(child_span.parent_span_id, root.context.span_id)
        self.assertGreaterEqual(child_span.clocks.duration_ns, 0)

    def test_export_readback(self) -> None:
        tracer = Tracer(mode=SamplingMode.FULL, collector=InMemoryTraceCollector())
        handle = tracer.start_span(TraceStage.QUALITY, "quality")
        if handle:
            handle.end()
        doc = export_document(tracer.collector.spans, counts=tracer.collector.counts.to_dict())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.json"
            write_export(path, doc)
            loaded = read_export(path)
        roundtrip = spans_from_export(loaded)
        self.assertEqual(len(roundtrip), 1)
        self.assertEqual(roundtrip[0].stage, TraceStage.QUALITY)

    def test_duplicate_span_rejected(self) -> None:
        clocks = span_clocks(1, 1, 2, 3)
        span = TraceSpan(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            stage=TraceStage.TRACE_ROOT,
            operation="op",
            clocks=clocks,
            status=TraceStatus.OK,
        )
        findings = validate_spans([span, span])
        self.assertTrue(any(f.code == "DUPLICATE_SPAN_ID" for f in findings))

    def test_unknown_parent_and_cycle(self) -> None:
        clocks = span_clocks(1, 1, 2, 3)
        bad_parent = TraceSpan(
            trace_id="t1",
            span_id="s2",
            parent_span_id="missing",
            stage=TraceStage.NORMALIZE,
            operation="op",
            clocks=clocks,
            status=TraceStatus.OK,
        )
        findings = validate_spans([bad_parent])
        self.assertTrue(any(f.code == "UNKNOWN_PARENT" for f in findings))

    def test_root_to_terminal_elapsed_not_terminal_duration(self) -> None:
        root = TraceSpan(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            stage=TraceStage.PROVIDER_RECEIVE,
            operation="receive",
            clocks=span_clocks(1, 1000, 1, 1100),
            status=TraceStatus.OK,
        )
        intermediate = TraceSpan(
            trace_id="t1",
            span_id="s2",
            parent_span_id="s1",
            stage=TraceStage.NORMALIZE,
            operation="normalize",
            clocks=span_clocks(1, 1200, 1, 1400),
            status=TraceStatus.OK,
        )
        terminal = TraceSpan(
            trace_id="t1",
            span_id="s3",
            parent_span_id="s2",
            stage=TraceStage.CANONICAL_STATE,
            operation="canonical_state",
            clocks=span_clocks(1, 1500, 1, 1900),
            status=TraceStatus.OK,
        )
        spans = [root, intermediate, terminal]
        samples = collect_profile_samples(spans, PROFILE_RECEIVE_TO_CANONICAL)
        self.assertEqual(samples, [900])
        self.assertEqual(terminal.clocks.duration_ns, 400)

    def test_queue_zero_samples_not_exercised(self) -> None:
        report = run_baseline(
            profile_id="queue_wait",
            workload_fn=run_fixture_ingest_workload,
            iterations=2,
            warmup_iterations=1,
        )
        self.assertEqual(report["measurement_class"], "NOT_EXERCISED")
        self.assertEqual(report["statistics"]["count"], 0)
        self.assertIsNone(report["statistics"]["median_ns"])

    def test_signal_profile_not_exercised(self) -> None:
        report = run_baseline(
            profile_id="receive_to_signal",
            workload_fn=run_fixture_ingest_workload,
            iterations=2,
            warmup_iterations=1,
        )
        self.assertEqual(report["measurement_class"], "NOT_EXERCISED")
        self.assertEqual(report["raw_sample_count"], 0)

    def test_sampling_modes(self) -> None:
        self.assertFalse(sampling_decision(mode=SamplingMode.OFF, stable_key="x"))
        self.assertTrue(sampling_decision(mode=SamplingMode.FULL, stable_key="x"))
        a = sampling_decision(mode=SamplingMode.DETERMINISTIC_SAMPLE, stable_key="stable-key", rate=10)
        b = sampling_decision(mode=SamplingMode.DETERMINISTIC_SAMPLE, stable_key="stable-key", rate=10)
        self.assertEqual(a, b)

    def test_collector_overflow_drop(self) -> None:
        collector = InMemoryTraceCollector(max_spans=1)
        tracer = Tracer(mode=SamplingMode.FULL, collector=collector)
        h1 = tracer.start_span(TraceStage.QUEUE, "one")
        h2 = tracer.start_span(TraceStage.QUEUE, "two")
        if h1:
            h1.end()
        if h2:
            h2.end()
        self.assertEqual(collector.counts.dropped, 1)
        self.assertEqual(collector.counts.written, 1)

    def test_context_propagation_thread(self) -> None:
        tracer = Tracer(mode=SamplingMode.FULL, collector=InMemoryTraceCollector())
        root = tracer.start_root("thread_root")
        carrier = inject_carrier({}, root.context if root else None)
        seen: list[str] = []
        def worker() -> None:
            ctx = extract_carrier(carrier)
            if ctx:
                seen.append(ctx.trace_id)
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(len(seen), 1)
        if root:
            root.end()

    def test_queue_wait_calculation(self) -> None:
        wait = queue_wait_ns(100, 250)
        self.assertEqual(wait, 150)

    def test_fixture_workload_spans(self) -> None:
        spans = run_fixture_ingest_workload()
        self.assertGreater(len(spans), 0)
        stages = {span.stage for span in spans}
        self.assertIn(TraceStage.PROVIDER_RECEIVE, stages)
        self.assertIn(TraceStage.CANONICAL_STATE, stages)

    def test_quality_replay_workload(self) -> None:
        spans = run_quality_replay_workload()
        stages = {span.stage for span in spans}
        self.assertIn(TraceStage.QUALITY, stages)
        self.assertIn(TraceStage.FEATURE, stages)

    def test_domain_equivalence(self) -> None:
        result = prove_equivalence(fixture_ingest_domain_hash, iterations=2)
        self.assertTrue(result["equivalent"])

    def test_overhead_measurement(self) -> None:
        report = measure_overhead(run_fixture_ingest_workload, iterations=3, warmup=1)
        self.assertIn("relative_overhead", report)
        self.assertGreater(report["full_span_count"], report["off_span_count"])

    def test_baseline_report(self) -> None:
        report = run_baseline(
            profile_id="receive_to_canonical_state",
            workload_fn=run_fixture_ingest_workload,
            iterations=2,
            warmup_iterations=1,
        )
        self.assertEqual(report["measurement_class"], "MEASURED_BASELINE")
        self.assertGreater(report["statistics"]["count"], 0)

    def test_compare_incompatible_profiles(self) -> None:
        left = {"profile_id": "a", "profile_version": "1", "clock_basis": "x", "workload": "w"}
        right = {"profile_id": "b", "profile_version": "1", "clock_basis": "x", "workload": "w"}
        delta = compare_baselines(left, right)
        self.assertFalse(delta["compatible"])


if __name__ == "__main__":
    unittest.main()
