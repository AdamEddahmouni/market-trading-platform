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
    build_cross_lane_snapshot_from_squeeze,
    merge_cross_lane_evidence,
    merge_cross_lane_snapshots,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.options.features.squeeze_context import (  # noqa: E402
    build_squeeze_context_for_options,
)
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402


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

    def test_options_snapshot_sets_gamma_amplification_flag(self) -> None:
        payload = {
            "available": True,
            "activities": [
                {
                    "option_type": "call",
                    "strike": 4.0,
                    "expiry": "2026-08-15",
                    "event_time": "2026-07-21T20:30:00.000000000Z",
                    "bid": 0.35,
                    "ask": 0.38,
                    "open_interest": 450,
                    "underlying_price": 4.25,
                    "volume_oi_ratio": 3.0,
                    "volume_ratio": 2.0,
                    "direction_label": "ambiguous",
                    "confirmation_score": 80,
                },
                {
                    "option_type": "call",
                    "strike": 4.5,
                    "expiry": "2026-08-15",
                    "event_time": "2026-07-21T20:30:00.000000000Z",
                    "bid": 0.20,
                    "ask": 0.22,
                    "open_interest": 300,
                    "underlying_price": 4.25,
                    "volume_oi_ratio": 2.5,
                    "volume_ratio": 1.8,
                    "direction_label": "ambiguous",
                    "confirmation_score": 75,
                },
            ],
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        assert snapshot is not None
        self.assertTrue(snapshot["options_dealer_position_available"])
        if snapshot.get("options_gamma_amplification"):
            self.assertIn("GAMMA_AMPLIFICATION_POTENTIAL", {row["signal"] for row in evidence})
            self.assertIn("options_hedging_pressure", snapshot)

    def test_chain_only_nvda_options_snapshot(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=cutoff))
        try:
            payload = build_workspace_options_payload(
                "NVDA",
                as_of_context={},
                prediction_cutoff=cutoff,
            )
            snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        finally:
            configure_institutional_ledger(original)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["options_available"])
        self.assertTrue(snapshot["options_dealer_position_available"])

    def test_squeeze_publishes_fuel_and_exhaustion_evidence(self) -> None:
        detail = {
            "causal_intelligence": {
                "state": "ACTIVE_SQUEEZE",
                "ignition_strength": 75,
                "remaining_fuel": 55.0,
                "exhaustion_risk": 60.0,
            }
        }
        snapshot, evidence = build_cross_lane_snapshot_from_squeeze(detail)
        assert snapshot is not None
        self.assertEqual(snapshot["remaining_fuel"], 55.0)
        signals = {row["signal"] for row in evidence}
        self.assertIn("REMAINING_SQUEEZE_FUEL", signals)
        self.assertIn("EXHAUSTION_RISK", signals)

    def test_squeeze_context_reads_remaining_fuel_field(self) -> None:
        context = build_squeeze_context_for_options(
            {"state": "ACTIVE_SQUEEZE", "remaining_fuel": 48.0, "exhaustion_risk": 55.0}
        )
        self.assertTrue(context["available"])
        self.assertEqual(context["remaining_squeeze_fuel"], 48.0)
        self.assertEqual(context["exhaustion_risk"], 55.0)


if __name__ == "__main__":
    unittest.main()
