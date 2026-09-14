"""Software-path hot-path telemetry wiring (fixture/replay, not live)."""

from __future__ import annotations

import unittest

from market_platform_foundation.hot_path_telemetry.software_aggregation import aggregate_software_clock_rows
from market_platform_foundation.hot_path_telemetry.software_wired import build_software_wired_document
from market_platform_foundation.hot_path_telemetry.collector import HotPathClockCollector
from market_platform_foundation.hot_path_telemetry.clock_row import HotPathClockRow


class HotPathSoftwareWiredTests(unittest.TestCase):
    def test_software_wired_document_emits_core_clocks(self) -> None:
        document = build_software_wired_document()
        body = document.to_dict()
        self.assertEqual(body["metadata"]["acceptance"], "HOT_PATH_TELEMETRY_SOFTWARE_WIRED")
        presence = body["timestamp_presence"]
        self.assertGreater(presence["imp_received_at"]["present_count"], 0)
        self.assertGreater(presence["normalized_at"]["present_count"], 0)
        self.assertGreater(presence["router_dispatched_at"]["present_count"], 0)
        self.assertGreater(presence["detected_at"]["present_count"], 0)
        segments = body["latency_segments_ns"]
        self.assertIn("imp_receive_to_normalized", segments)
        self.assertIn("normalized_to_router_dispatched", segments)
        self.assertIn("router_dispatched_to_detected", segments)
        for segment in segments.values():
            self.assertIn("missing_pair_count", segment)
            self.assertIn("p50_ns", segment)
            self.assertIn("p95_ns", segment)
            self.assertIn("p99_ns", segment)

    def test_missing_clocks_do_not_zero_fill_segments(self) -> None:
        row = HotPathClockRow(correlation_id="partial", imp_received_at=10)
        report = aggregate_software_clock_rows([row])
        segment = report["latency_segments_ns"]["imp_receive_to_normalized"]
        self.assertEqual(segment["count"], 0)
        self.assertEqual(segment["missing_pair_count"], 1)
        self.assertIsNone(segment.get("min_ns"))


if __name__ == "__main__":
    unittest.main()
