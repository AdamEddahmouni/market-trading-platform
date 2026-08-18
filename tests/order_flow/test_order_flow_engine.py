"""Order Flow / microstructure engine tests (OF1–OF3)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.cross_lane_adapter import (
    build_cross_lane_snapshot_from_order_book,
    build_cross_lane_snapshot_from_order_flow,
)
from market_platform_foundation.order_flow import (
    AggressorSide,
    AggressorSource,
    build_order_flow_evidence,
    classify_trade,
    compute_cvd_state,
    compute_l1_state,
    cvd_slope,
    queue_imbalance,
)
from market_platform_foundation.order_flow.aggressor import classify_bar_delta, provenance_from_quality_label


class AggressorClassificationTests(unittest.TestCase):
    def test_lee_ready_buy_at_ask(self) -> None:
        trade = classify_trade(
            trade_id="t1",
            price=10.5,
            quantity=100,
            bid=10.0,
            ask=10.5,
            prev_price=10.4,
            trade_timestamp="2026-07-21T20:30:00Z",
        )
        self.assertEqual(trade.aggressor_side, AggressorSide.BUY)
        self.assertEqual(trade.signed_volume, 100.0)
        self.assertEqual(trade.aggressor_source, AggressorSource.LEE_READY)

    def test_lee_ready_sell_at_bid(self) -> None:
        trade = classify_trade(
            trade_id="t2",
            price=10.0,
            quantity=50,
            bid=10.0,
            ask=10.5,
            prev_price=10.4,
            trade_timestamp="2026-07-21T20:30:01Z",
        )
        self.assertEqual(trade.aggressor_side, AggressorSide.SELL)
        self.assertEqual(trade.signed_volume, -50.0)

    def test_native_quality_not_upgraded(self) -> None:
        self.assertEqual(provenance_from_quality_label("tick"), AggressorSource.EXCHANGE_NATIVE)
        self.assertEqual(provenance_from_quality_label("bvc"), AggressorSource.BVC)
        self.assertEqual(provenance_from_quality_label("neutral"), AggressorSource.UNKNOWN)

    def test_unknown_bar_delta(self) -> None:
        trade = classify_bar_delta(
            bar_time="2026-07-21T20:30:02Z",
            delta=0.0,
            volume=1000.0,
            quality="neutral",
        )
        self.assertEqual(trade.aggressor_side, AggressorSide.UNKNOWN)
        self.assertEqual(trade.classification_confidence, 0.0)


class L1MicrostructureTests(unittest.TestCase):
    def test_microprice_and_queue_imbalance(self) -> None:
        state = compute_l1_state(best_bid=100.0, best_ask=100.1, bid_size=200.0, ask_size=100.0)
        assert state is not None
        self.assertAlmostEqual(state.mid, 100.05)
        self.assertGreater(state.microprice, state.mid)
        self.assertAlmostEqual(queue_imbalance(200.0, 100.0), 1.0 / 3.0, places=4)

    def test_crossed_book_returns_none(self) -> None:
        self.assertIsNone(compute_l1_state(best_bid=100.2, best_ask=100.1, bid_size=10, ask_size=10))


class CVDTests(unittest.TestCase):
    def test_pure_buy_aggression(self) -> None:
        bars = [
            {"date": "t1", "delta": 100.0, "volume": 100.0, "quality": "tick"},
            {"date": "t2", "delta": 50.0, "volume": 50.0, "quality": "tick"},
        ]
        state = compute_cvd_state(bars)
        assert state is not None
        self.assertEqual(state.session_cvd, 150.0)
        self.assertEqual(state.native_classification_fraction, 1.0)
        self.assertEqual(state.cvd_confidence, 1.0)

    def test_mixed_with_unknown(self) -> None:
        bars = [
            {"date": "t1", "delta": 100.0, "volume": 100.0, "quality": "tick"},
            {"date": "t2", "delta": 0.0, "volume": 1000.0, "quality": "neutral"},
            {"date": "t3", "delta": -25.0, "volume": 25.0, "quality": "bvc"},
        ]
        state = compute_cvd_state(bars)
        assert state is not None
        self.assertEqual(state.session_cvd, 75.0)
        self.assertGreater(state.unknown_fraction, 0.0)
        self.assertLess(state.cvd_confidence, 1.0)

    def test_cvd_slope(self) -> None:
        series = [100.0, 150.0, 175.0]
        self.assertEqual(cvd_slope(series), 25.0)


class CrossLaneEvidenceTests(unittest.TestCase):
    def test_aggressive_sell_pressure(self) -> None:
        payload = {
            "available": True,
            "bars": [
                {"delta": -100, "cumulative_delta": -100},
                {"delta": -80, "cumulative_delta": -180},
                {"delta": -50, "cumulative_delta": -230},
            ],
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_flow(payload)
        assert snapshot is not None
        self.assertTrue(snapshot["order_flow_aggressive_sell"])
        signals = {row["signal"] for row in evidence}
        self.assertIn("AGGRESSIVE_SELL_PRESSURE", signals)

    def test_book_imbalance_bid_heavy(self) -> None:
        payload = {
            "available": True,
            "latest_l1": {"queue_imbalance": 0.25},
            "latest_imbalance_ratio": 1.5,
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_book(payload)
        assert snapshot is not None
        signals = {row["signal"] for row in evidence}
        self.assertIn("BOOK_IMBALANCE_BID", signals)


class OrderFlowEvidenceContractTests(unittest.TestCase):
    def test_build_evidence_from_bars_and_snapshot(self) -> None:
        snapshot = {
            "bids": [{"price": 10.0, "size": 100}, {"price": 9.9, "size": 50}],
            "asks": [{"price": 10.1, "size": 80}, {"price": 10.2, "size": 40}],
        }
        bars = [{"date": "t1", "delta": 50.0, "volume": 50.0, "quality": "tick"}]
        evidence = build_order_flow_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:00Z",
            available_time="2026-07-21T20:30:00Z",
            bars=bars,
            snapshot=snapshot,
            ofi_value=12.5,
        )
        assert evidence is not None
        self.assertEqual(evidence.instrument, "NVDA")
        assert evidence.cvd is not None
        assert evidence.l1 is not None
        assert evidence.book_pressure is not None
        self.assertEqual(evidence.ofi_method, "ofi_bbo_delta_v1")


if __name__ == "__main__":
    unittest.main()
