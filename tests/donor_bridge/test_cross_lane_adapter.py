"""Tests for IMP cross-lane order-flow adapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.cross_lane_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_futures,
    build_cross_lane_snapshot_from_options,
    build_cross_lane_snapshot_from_order_flow,
    merge_cross_lane_evidence,
    merge_cross_lane_snapshots,
)


class CrossLaneAdapterTests(unittest.TestCase):
    def test_builds_aggressive_buy_snapshot(self) -> None:
        payload = {
            "available": True,
            "bars": [
                {"delta": 200, "cumulative_delta": 200},
                {"delta": 150, "cumulative_delta": 350},
                {"delta": 180, "cumulative_delta": 530},
            ],
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_flow(payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["order_flow_available"])
        self.assertTrue(snapshot["order_flow_aggressive_buy"])
        self.assertGreater(len(evidence), 0)

    def test_builds_options_call_demand_snapshot(self) -> None:
        payload = {
            "available": True,
            "activities": [
                {
                    "option_type": "call",
                    "volume_oi_ratio": 3.0,
                    "volume_ratio": 2.0,
                    "direction_label": "ambiguous",
                    "confirmation_score": 80,
                },
                {
                    "option_type": "call",
                    "volume_oi_ratio": 2.5,
                    "volume_ratio": 1.8,
                    "direction_label": "ambiguous",
                    "confirmation_score": 75,
                },
            ],
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["options_available"])
        self.assertFalse(snapshot["options_signed_flow_available"])
        signals = {item["signal"] for item in evidence}
        self.assertIn("CALL_DEMAND_ANOMALY", signals)

    def test_builds_options_signed_flow_snapshot(self) -> None:
        payload = {
            "available": True,
            "activities": [
                {
                    "option_type": "call",
                    "flow_side": "buy",
                    "open_close": "open",
                    "size": 500,
                    "strike": 130.0,
                    "volume": 1000,
                    "volume_oi_ratio": 2.0,
                    "volume_ratio": 1.5,
                    "confirmation_score": 80,
                },
                {
                    "option_type": "call",
                    "flow_side": "buy",
                    "open_close": "open",
                    "size": 800,
                    "strike": 135.0,
                    "volume": 1200,
                    "volume_oi_ratio": 2.5,
                    "volume_ratio": 1.8,
                    "confirmation_score": 75,
                },
            ],
            "signed_flow_snapshot": {
                "available": True,
                "signed_flow_available": True,
                "dominant_direction": "buy_initiated",
                "aggregate": {"net_delta_flow": 6000},
            },
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        assert snapshot is not None
        self.assertTrue(snapshot["options_signed_flow_available"])
        signals = {item["signal"] for item in evidence}
        self.assertIn("OPTION_FLOW_DIRECTION", signals)

    def test_builds_futures_depth_snapshot_fail_closed_on_curve(self) -> None:
        payload = {
            "available": True,
            "contract_month": "202506",
            "book_pressure_side": "bid_heavy",
            "imbalance_signal": "supports_long",
            "imbalance_ratio": 2.1,
            "snapshot_count": 5,
        }
        snapshot, evidence = build_cross_lane_snapshot_from_futures(payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["futures_available"])
        self.assertFalse(snapshot["futures_curve_available"])
        self.assertFalse(snapshot["futures_positioning_available"])
        self.assertEqual(snapshot.get("futures_data_kind"), "depth_derived")
        signals = {item["signal"] for item in evidence}
        self.assertIn("BOOK_IMBALANCE_BID", signals)
        self.assertIn("FUTURES_DATA_CONFIDENCE", signals)
        self.assertNotIn("FUTURES_ORDER_FLOW_CONFIRMING", signals)

    def test_futures_unavailable_returns_empty(self) -> None:
        snapshot, evidence = build_cross_lane_snapshot_from_futures(None)
        self.assertIsNone(snapshot)
        self.assertEqual(evidence, [])

    def test_merge_cross_lane_snapshots(self) -> None:
        order_snapshot = {"order_flow_available": True, "options_available": False}
        options_snapshot = {"options_available": True, "options_activity_count": 2}
        merged = merge_cross_lane_snapshots(order_snapshot, options_snapshot)
        self.assertTrue(merged["order_flow_available"])
        self.assertTrue(merged["options_available"])
        self.assertEqual(merged["options_activity_count"], 2)

    def test_merge_cross_lane_evidence(self) -> None:
        first = [{"signal": "CVD_POSITIVE_SLOPE"}]
        second = [{"signal": "CALL_DEMAND_ANOMALY"}]
        merged = merge_cross_lane_evidence(first, second)
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
