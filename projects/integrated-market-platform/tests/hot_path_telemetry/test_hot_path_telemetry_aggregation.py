"""Focused hot-path telemetry aggregation tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.hot_path_telemetry.models import HotPathQualityCounters
from market_platform_foundation.hot_path_telemetry.quality_mapping import apply_finding_code
from market_platform_foundation.hot_path_telemetry.rt01_aggregation import aggregate_rt01_spans
from market_platform_foundation.intelligence.quality.models import QualityFindingCode
from market_platform_foundation.rt01.clock import span_clocks
from market_platform_foundation.rt01.enums import TraceStage, TraceStatus
from market_platform_foundation.rt01.span import TraceSpan


class HotPathTelemetryAggregationTests(unittest.TestCase):
    def test_missing_timestamp_counts(self) -> None:
        clocks = span_clocks(1, 10, 2, 20)
        span = TraceSpan(
            trace_id="trace-missing",
            span_id="span-root",
            parent_span_id=None,
            stage=TraceStage.PROVIDER_RECEIVE,
            operation="receive",
            clocks=clocks,
            status=TraceStatus.OK,
        )
        report = aggregate_rt01_spans([span])
        presence = report["timestamp_presence"]
        self.assertEqual(presence["source_event_at"]["missing_count"], 1)
        self.assertEqual(presence["normalized_at"]["missing_count"], 1)
        self.assertEqual(presence["operator_surfaced_at"]["missing_count"], 1)

    def test_duplicate_quality_counter(self) -> None:
        counters = HotPathQualityCounters()
        updated = apply_finding_code(counters, QualityFindingCode.EXACT_DUPLICATE.value)
        self.assertEqual(updated.duplicates, 1)


if __name__ == "__main__":
    unittest.main()
