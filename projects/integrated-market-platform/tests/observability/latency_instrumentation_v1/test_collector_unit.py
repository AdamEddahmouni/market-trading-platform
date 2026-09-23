"""Unit tests for latency instrumentation v1 collector semantics.

Evidence class: SOFTWARE_CONTROLLED / FIXTURE — not prospective.
"""

from __future__ import annotations

import unittest

from market_platform_foundation.observability.latency_instrumentation_v1 import (
    EligibilityClockId,
    LatencyInstrumentationCollector,
    LatencyStageId,
    UNAVAILABLE_OPERATOR_STAGES,
    bind_latency_collector,
    current_latency_collector,
)
from market_platform_foundation.observability.latency_instrumentation_v1.clocks import (
    capture_stage_stamp,
)
from market_platform_foundation.observability.latency_instrumentation_v1.types import (
    StageObservationStatus,
)


class LatencyCollectorUnitTests(unittest.TestCase):
    def test_missing_stage_stays_not_observed(self) -> None:
        collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        trace = collector.trace_for("evt-1")
        self.assertEqual(
            trace.stage(LatencyStageId.DETECTOR_STARTED).status,
            StageObservationStatus.NOT_OBSERVED,
        )
        coverage = trace.coverage_note()
        for name in UNAVAILABLE_OPERATOR_STAGES:
            self.assertEqual(coverage["operator_ui_stages"][name], "UNAVAILABLE")

    def test_mark_stage_records_wall_and_mono(self) -> None:
        collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        stamp = capture_stage_stamp()
        collector.mark_stage("evt-1", LatencyStageId.NORMALIZATION_COMPLETED, stamp=stamp)
        again = capture_stage_stamp()
        collector.mark_stage("evt-1", LatencyStageId.NORMALIZATION_COMPLETED, stamp=again)
        observed = collector.get_trace("evt-1")
        assert observed is not None
        stage = observed.stages[str(LatencyStageId.NORMALIZATION_COMPLETED)]
        self.assertEqual(stage.wall_ns, stamp.wall_ns)
        self.assertEqual(stage.mono_ns, stamp.mono_ns)

    def test_eligibility_distinct_from_processing(self) -> None:
        collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        collector.note_eligibility(
            "evt-1",
            source_publication_ns=100,
            provider_retrieved_ns=200,
            imp_server_received_ns=300,
        )
        collector.mark_stage("evt-1", LatencyStageId.PIT_COMPLETED)
        trace = collector.get_trace("evt-1")
        assert trace is not None
        self.assertEqual(trace.eligibility_ns[str(EligibilityClockId.SOURCE_PUBLICATION)], 100)
        self.assertIsNotNone(trace.stages[str(LatencyStageId.PIT_COMPLETED)].wall_ns)
        self.assertNotIn(str(LatencyStageId.PIT_COMPLETED), trace.eligibility_ns)

    def test_mono_delta_requires_both_ends(self) -> None:
        collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        collector.mark_stage("evt-1", LatencyStageId.DETECTOR_STARTED)
        self.assertIsNone(
            collector.mono_delta_ns(
                "evt-1",
                LatencyStageId.DETECTOR_STARTED,
                LatencyStageId.DETECTOR_COMPLETED,
            )
        )
        collector.mark_stage("evt-1", LatencyStageId.DETECTOR_COMPLETED)
        delta = collector.mono_delta_ns(
            "evt-1",
            LatencyStageId.DETECTOR_STARTED,
            LatencyStageId.DETECTOR_COMPLETED,
        )
        self.assertIsNotNone(delta)
        assert delta is not None
        self.assertGreaterEqual(delta, 0)

    def test_context_bind_and_opportunity_index(self) -> None:
        collector = LatencyInstrumentationCollector(evidence_class="FIXTURE")
        self.assertIsNone(current_latency_collector())
        with bind_latency_collector(collector):
            self.assertIs(current_latency_collector(), collector)
            collector.attach_opportunity_id("evt-9", "newsopp-evt-9")
            stamp = capture_stage_stamp()
            correlated = collector.mark_stages_for_opportunity_ids(
                ["newsopp-evt-9", "unknown"],
                LatencyStageId.RANK_GENERATED,
                stamp=stamp,
            )
            self.assertEqual(correlated, ("evt-9",))
        self.assertIsNone(current_latency_collector())

    def test_unbound_collector_skips_stage_recording(self) -> None:
        """Regression: unbound resolve must not create ambient traces or require stamps."""

        from market_platform_foundation.observability.latency_instrumentation_v1.context import (
            resolve_latency_collector,
        )

        self.assertIsNone(current_latency_collector())
        self.assertIsNone(resolve_latency_collector(None))
        self.assertIsNone(resolve_latency_collector(object()))
        with bind_latency_collector(None):
            self.assertIsNone(current_latency_collector())
            self.assertIsNone(resolve_latency_collector(None))

    def test_wall_and_mono_domains_are_separate(self) -> None:
        stamp = capture_stage_stamp()
        self.assertIsNotNone(stamp.wall_ns)
        self.assertIsNotNone(stamp.mono_ns)
        assert stamp.wall_ns is not None and stamp.mono_ns is not None
        # Domains are independently sampled; equality is not required or meaningful.
        self.assertIsInstance(stamp.wall_ns, int)
        self.assertIsInstance(stamp.mono_ns, int)
        self.assertGreater(stamp.wall_ns, 0)
        self.assertGreater(stamp.mono_ns, 0)


if __name__ == "__main__":
    unittest.main()
