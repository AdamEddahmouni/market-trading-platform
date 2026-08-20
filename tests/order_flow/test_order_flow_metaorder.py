"""Tests for OF11 metaorder detection primitives."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.cross_lane.evidence import EvidenceSignal
from market_platform_foundation.order_flow.contracts import AggressorSide, MetaorderFlowState
from market_platform_foundation.order_flow.evidence import metaorder_primitive_cross_lane_evidence
from market_platform_foundation.order_flow.metaorder import (
    classified_trades_from_bars,
    detect_metaorder_primitives,
)

METAORDER_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_metaorder_slice.json"
BASE_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_order_flow_slice.json"


class TestMetaorderDetection(unittest.TestCase):
    def test_persistent_buy_sequence_detected(self) -> None:
        payload = json.loads(METAORDER_FIXTURE.read_text(encoding="utf-8"))
        bars = payload["bars"]
        trades = classified_trades_from_bars(bars, instrument="NVDA")
        primitives = detect_metaorder_primitives(
            trades,
            instrument="NVDA",
            min_signed_volume=500.0,
            min_trade_count=3,
            min_duration_seconds=2.0,
        )
        self.assertEqual(len(primitives), 1)
        primitive = primitives[0]
        self.assertEqual(primitive.aggressor_side, AggressorSide.BUY)
        self.assertGreaterEqual(primitive.signed_volume, 500.0)
        self.assertEqual(primitive.flow_state, MetaorderFlowState.FLOW_WEAKENING)

    def test_alternating_flow_not_detected(self) -> None:
        payload = json.loads(BASE_FIXTURE.read_text(encoding="utf-8"))
        bars = payload["bars"]
        trades = classified_trades_from_bars(bars, instrument="NVDA")
        primitives = detect_metaorder_primitives(trades, instrument="NVDA")
        self.assertEqual(primitives, [])

    def test_single_large_print_not_detected(self) -> None:
        payload = json.loads(BASE_FIXTURE.read_text(encoding="utf-8"))
        bars = [payload["bars"][-1]]
        trades = classified_trades_from_bars(bars, instrument="NVDA")
        primitives = detect_metaorder_primitives(trades, instrument="NVDA", min_signed_volume=100.0)
        self.assertEqual(primitives, [])

    def test_cross_lane_signals_publish_for_active_flow(self) -> None:
        from market_platform_foundation.order_flow.contracts import MetaorderPrimitive, MetaorderFlowState

        primitive = MetaorderPrimitive(
            primitive_id="NVDA:test:active",
            instrument="NVDA",
            venue="NVDA",
            aggressor_side=AggressorSide.BUY,
            signed_volume=1250.0,
            trade_count=4,
            start_time="2026-07-21T20:30:00.000000000Z",
            end_time="2026-07-21T20:30:03.000000000Z",
            available_time="2026-07-21T20:30:03.000000000Z",
            flow_state=MetaorderFlowState.FLOW_ACTIVE,
            detection_method="persistent_aggressive_flow_v1",
            detection_version="1",
        )
        evidence = metaorder_primitive_cross_lane_evidence([primitive])
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.PERSISTENT_AGGRESSIVE_BUY_FLOW.value, signals)


if __name__ == "__main__":
    unittest.main()
