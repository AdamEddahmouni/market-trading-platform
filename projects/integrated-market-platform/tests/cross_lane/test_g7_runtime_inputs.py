"""G7 cross-lane runtime input bridge tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.runtime_inputs import (  # noqa: E402
    build_order_flow_lane_snapshot,
)
from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)


class CrossLaneRuntimeInputTests(unittest.TestCase):
    def test_canonical_store_feeds_order_flow_snapshot(self) -> None:
        store = ObservationalStateStore()
        store.apply_quote_update(
            instrument_id="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            provider="ibkr.observational",
        )
        snapshot = build_order_flow_lane_snapshot(store, "AAPL")
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["producer"], "observational_lane_runtime/g7")
        self.assertIsNotNone(snapshot["l1"])

    def test_lane_snapshot_preserves_provenance_for_fusion(self) -> None:
        store = ObservationalStateStore()
        store.apply_quote_update(
            instrument_id="NVDA",
            bid_price=100.0,
            ask_price=101.0,
            provider="replay",
            event_time_ns=1000,
            received_ns=1100,
        )
        order_flow = build_order_flow_lane_snapshot(store, "NVDA")
        l1 = order_flow["l1"]
        assert l1 is not None
        self.assertEqual(l1["provenance"]["provider"], "replay")
        self.assertEqual(l1["provenance"]["source_time_ns"], 1000)


if __name__ == "__main__":
    unittest.main()
