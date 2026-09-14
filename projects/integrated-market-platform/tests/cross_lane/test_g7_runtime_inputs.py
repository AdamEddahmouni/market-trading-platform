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
from market_platform_foundation.market_data.depth_admission import (  # noqa: E402
    DepthAdmissibilityStatus,
)
from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    DepthOperation,
    DepthSide,
    build_depth_update,
)


NS = 1_000_000_000


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

    def test_ttl_stale_depth_blocks_fusion_ofi(self) -> None:
        store = ObservationalStateStore()
        for event in (
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.RESET,
                received_time_ns=0,
            ),
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="5",
                received_time_ns=0,
            ),
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.ASK,
                price="101",
                size="5",
                received_time_ns=0,
            ),
        ):
            store.apply_depth_update(event)
        snapshot = build_order_flow_lane_snapshot(
            store, "AAPL", as_of_time_ns=(5 * NS) + 1
        )
        ofi = snapshot["ofi"]
        features = snapshot["book_features"]
        self.assertFalse(ofi["available"])
        self.assertEqual(ofi["state"], DepthAdmissibilityStatus.STALE.value)
        self.assertFalse(features["available"])
        self.assertEqual(features["state"], DepthAdmissibilityStatus.STALE.value)


if __name__ == "__main__":
    unittest.main()
