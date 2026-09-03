"""Order Flow / microstructure engine tests (OF1–OF9)."""

from __future__ import annotations

import json
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
    CONTINUATION_THRESHOLD,
    FORECAST_METHOD,
    IMPACT_METHOD,
    LIQUIDITY_METHOD_DEPTH_DELTA,
    OFI_METHOD_BBO_DELTA,
    OFI_METHOD_MULTILEVEL_CS,
    REVERSAL_THRESHOLD,
    build_execution_forecast_evidence,
    build_impact_evidence,
    build_liquidity_evidence,
    build_microstructure_forecast_evidence,
    build_order_flow_evidence,
    classify_trade,
    compute_bbo_ofi,
    compute_cvd_state,
    EXECUTION_METHOD,
    compute_execution_forecast,
    compute_impact_dynamics,
    compute_l1_state,
    compute_liquidity_dynamics,
    compute_microstructure_forecast,
    compute_multilevel_ofi,
    compute_ofi,
    compute_trajectory_resiliency,
    cvd_slope,
    queue_imbalance,
    snapshot_book_state_valid,
    snapshot_pair_book_state_valid,
    snapshot_pair_sequence_valid,
)
from market_platform_foundation.order_flow.contracts import ForecastDirection, ImpactRegime
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

    def test_build_evidence_multilevel_ofi_from_snapshots(self) -> None:
        prev_snapshot = {
            "bids": [{"price": 10.0, "size": 100}, {"price": 9.9, "size": 50}],
            "asks": [{"price": 10.1, "size": 80}, {"price": 10.2, "size": 40}],
        }
        curr_snapshot = {
            "bids": [{"price": 10.05, "size": 90}, {"price": 10.0, "size": 45}],
            "asks": [{"price": 10.15, "size": 70}, {"price": 10.25, "size": 35}],
        }
        evidence = build_order_flow_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:01Z",
            available_time="2026-07-21T20:30:01Z",
            snapshot=curr_snapshot,
            prev_snapshot=prev_snapshot,
        )
        assert evidence is not None
        self.assertEqual(evidence.ofi_method, OFI_METHOD_MULTILEVEL_CS)
        self.assertEqual(evidence.ofi_version, "1")
        assert evidence.ofi_value is not None


class OFIBookFlowTests(unittest.TestCase):
    def test_bbo_vs_multilevel_diverge_on_three_levels(self) -> None:
        prev_snapshot = {
            "bids": [
                {"price": 170.54, "size": 500},
                {"price": 170.53, "size": 400},
                {"price": 170.52, "size": 350},
            ],
            "asks": [
                {"price": 170.56, "size": 300},
                {"price": 170.57, "size": 250},
                {"price": 170.58, "size": 200},
            ],
        }
        curr_snapshot = {
            "bids": [
                {"price": 170.56, "size": 420},
                {"price": 170.55, "size": 360},
                {"price": 170.54, "size": 300},
            ],
            "asks": [
                {"price": 170.58, "size": 280},
                {"price": 170.59, "size": 220},
                {"price": 170.6, "size": 180},
            ],
        }
        bbo = compute_bbo_ofi(prev_snapshot, curr_snapshot)
        multilevel = compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=10)
        self.assertEqual(bbo.ofi_method, OFI_METHOD_BBO_DELTA)
        self.assertEqual(multilevel.ofi_method, OFI_METHOD_MULTILEVEL_CS)
        self.assertNotEqual(bbo.value, multilevel.value)
        self.assertEqual(bbo.value, 720.0)
        self.assertEqual(multilevel.value, 1830.0)

    def test_invalid_book_state_fail_closed(self) -> None:
        valid = {"bids": [{"price": 10.0, "size": 100}], "asks": [{"price": 10.1, "size": 80}]}
        invalid = {"bids": [], "asks": [{"price": 10.1, "size": 80}]}
        self.assertFalse(snapshot_book_state_valid(invalid))
        result = compute_multilevel_ofi(valid, invalid)
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.value, 0.0)

    def test_nvda_golden_fixture_regression(self) -> None:
        depth_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_book" / "nvda_depth_slice.json"
        expected_fixture = ROOT / "tests" / "fixtures" / "order_flow" / "nvda_ofi_expected.json"
        depth = json.loads(depth_fixture.read_text(encoding="utf-8"))
        expected = json.loads(expected_fixture.read_text(encoding="utf-8"))
        snapshots = depth["snapshots"]
        level_count = depth["level_count"]
        for row in expected["transitions"]:
            index = row["index"]
            prev_snapshot = snapshots[index - 1]
            curr_snapshot = snapshots[index]
            bbo = compute_bbo_ofi(prev_snapshot, curr_snapshot)
            multilevel = compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=level_count)
            self.assertEqual(bbo.value, row["bbo_ofi"])
            self.assertEqual(multilevel.value, row["multilevel_ofi"])
            self.assertEqual(multilevel.ofi_method, row["ofi_method"])
            self.assertEqual(multilevel.ofi_version, row["ofi_version"])
            self.assertEqual(multilevel.book_state_valid, row["book_state_valid"])


class LiquidityDynamicsTests(unittest.TestCase):
    def test_withdrawal_on_depth_drop(self) -> None:
        prev_snapshot = {
            "bids": [{"price": 10.0, "size": 500}, {"price": 9.9, "size": 400}],
            "asks": [{"price": 10.1, "size": 300}, {"price": 10.2, "size": 250}],
        }
        curr_snapshot = {
            "bids": [{"price": 10.0, "size": 420}, {"price": 9.9, "size": 360}],
            "asks": [{"price": 10.1, "size": 280}, {"price": 10.2, "size": 220}],
        }
        result = compute_liquidity_dynamics(prev_snapshot, curr_snapshot, level_count=10)
        self.assertTrue(result.book_state_valid)
        self.assertEqual(result.liquidity_method, LIQUIDITY_METHOD_DEPTH_DELTA)
        self.assertGreater(result.depth_withdrawal, 0.0)
        self.assertEqual(result.depth_replenishment, 0.0)

    def test_replenishment_on_depth_recovery(self) -> None:
        prev_snapshot = {
            "bids": [{"price": 10.0, "size": 200}, {"price": 9.9, "size": 180}],
            "asks": [{"price": 10.1, "size": 240}, {"price": 10.2, "size": 200}],
        }
        curr_snapshot = {
            "bids": [{"price": 10.0, "size": 300}, {"price": 9.9, "size": 260}],
            "asks": [{"price": 10.1, "size": 320}, {"price": 10.2, "size": 280}],
        }
        result = compute_liquidity_dynamics(prev_snapshot, curr_snapshot, level_count=10)
        self.assertGreater(result.depth_replenishment, 0.0)
        self.assertEqual(result.depth_withdrawal, 0.0)

    def test_build_liquidity_evidence_emits_supporting(self) -> None:
        prev_snapshot = {
            "bids": [{"price": 170.54, "size": 500}, {"price": 170.53, "size": 400}],
            "asks": [{"price": 170.56, "size": 300}, {"price": 170.57, "size": 250}],
        }
        curr_snapshot = {
            "bids": [{"price": 170.56, "size": 420}, {"price": 170.55, "size": 360}],
            "asks": [{"price": 170.58, "size": 280}, {"price": 170.59, "size": 220}],
        }
        evidence = build_liquidity_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:01Z",
            available_time="2026-07-21T20:30:01Z",
            prev_snapshot=prev_snapshot,
            snapshot=curr_snapshot,
        )
        assert evidence is not None
        self.assertEqual(evidence.liquidity_method, LIQUIDITY_METHOD_DEPTH_DELTA)
        self.assertGreater(evidence.depth_withdrawal, 0.0)

    def test_nvda_liquidity_golden_fixture_regression(self) -> None:
        depth_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_book" / "nvda_depth_slice.json"
        expected_fixture = ROOT / "tests" / "fixtures" / "order_flow" / "nvda_liquidity_expected.json"
        depth = json.loads(depth_fixture.read_text(encoding="utf-8"))
        expected = json.loads(expected_fixture.read_text(encoding="utf-8"))
        snapshots = depth["snapshots"]
        level_count = depth["level_count"]
        trajectory = compute_trajectory_resiliency(snapshots, level_count=level_count)
        self.assertEqual(trajectory, expected["trajectory_resiliency"])
        for row in expected["transitions"]:
            index = row["index"]
            result = compute_liquidity_dynamics(
                snapshots[index - 1],
                snapshots[index],
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            self.assertEqual(result.net_depth_delta, row["net_depth_delta"])
            self.assertEqual(result.depth_withdrawal, row["depth_withdrawal"])
            self.assertEqual(result.depth_replenishment, row["depth_replenishment"])
            self.assertEqual(result.fragility_score, row["fragility_score"])
            self.assertEqual(result.resiliency_score, row["resiliency_score"])


class ImpactDynamicsTests(unittest.TestCase):
    def _book(self, bid: float, ask: float, bid_size: float, ask_size: float) -> dict:
        return {
            "bids": [{"price": bid, "size": bid_size}],
            "asks": [{"price": ask, "size": ask_size}],
        }

    def test_buy_absorption_synthetic(self) -> None:
        prev = self._book(100.0, 100.02, 500, 300)
        curr = self._book(100.0, 100.02, 480, 350)
        result = compute_impact_dynamics(
            prev,
            curr,
            bar_delta=200.0,
            prev_bar_delta=50.0,
        )
        self.assertEqual(result.impact_regime, ImpactRegime.BUY_ABSORPTION)
        self.assertTrue(result.opposing_replenishment)
        self.assertIsNotNone(result.absorption_score)

    def test_sell_exhaustion_synthetic(self) -> None:
        prev = self._book(100.0, 100.02, 500, 300)
        curr = self._book(100.005, 100.025, 490, 310)
        result = compute_impact_dynamics(
            prev,
            curr,
            bar_delta=-120.0,
            prev_bar_delta=-200.0,
        )
        self.assertEqual(result.impact_regime, ImpactRegime.SELL_EXHAUSTION)
        self.assertIsNotNone(result.exhaustion_score)

    def test_missing_trade_flow_fail_closed(self) -> None:
        prev = self._book(100.0, 100.02, 500, 300)
        curr = self._book(100.01, 100.03, 480, 320)
        result = compute_impact_dynamics(prev, curr, bar_delta=None)
        self.assertEqual(result.impact_regime, ImpactRegime.NEUTRAL)
        self.assertIn("MISSING_TRADE_FLOW", result.quality_flags)
        self.assertIsNone(result.aggression_signed_volume)

    def test_invalid_book_pair_fail_closed(self) -> None:
        prev = {"bids": [], "asks": []}
        curr = self._book(100.0, 100.02, 500, 300)
        result = compute_impact_dynamics(prev, curr, bar_delta=100.0)
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.impact_regime, ImpactRegime.NEUTRAL)

    def test_build_impact_evidence_supporting_detail(self) -> None:
        prev = self._book(100.0, 100.02, 500, 300)
        curr = self._book(100.0, 100.02, 480, 350)
        evidence = build_impact_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:04Z",
            available_time="2026-07-21T20:30:04Z",
            prev_snapshot=prev,
            snapshot=curr,
            bar_delta=200.0,
        )
        assert evidence is not None
        self.assertEqual(evidence.impact_method, IMPACT_METHOD)

    def test_nvda_impact_golden_fixture_regression(self) -> None:
        depth_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_book" / "nvda_depth_slice.json"
        flow_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_order_flow_slice.json"
        expected_fixture = ROOT / "tests" / "fixtures" / "order_flow" / "nvda_impact_expected.json"
        depth = json.loads(depth_fixture.read_text(encoding="utf-8"))
        flow = json.loads(flow_fixture.read_text(encoding="utf-8"))
        expected = json.loads(expected_fixture.read_text(encoding="utf-8"))
        bars = {str(row["date"]): row for row in flow["bars"]}
        snapshots = depth["snapshots"]
        level_count = depth["level_count"]
        trajectory = compute_trajectory_resiliency(snapshots, level_count=level_count)
        for row in expected["transitions"]:
            index = row["index"]
            prev_snapshot = snapshots[index - 1]
            curr_snapshot = snapshots[index]
            event_time = str(curr_snapshot["event_time"])
            prev_bar = bars.get(str(prev_snapshot["event_time"]))
            curr_bar = bars.get(event_time)
            result = compute_impact_dynamics(
                prev_snapshot,
                curr_snapshot,
                bar_delta=float(curr_bar["delta"]) if curr_bar else None,
                prev_bar_delta=float(prev_bar["delta"]) if prev_bar else None,
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            self.assertEqual(result.impact_regime.value, row["impact_regime"])
            self.assertEqual(result.mid_delta, row["mid_delta"])
            self.assertEqual(result.impact_method, row["impact_method"])
            if row.get("absorption_score") is not None:
                self.assertEqual(result.absorption_score, row["absorption_score"])
            if row.get("exhaustion_score") is not None:
                self.assertEqual(result.exhaustion_score, row["exhaustion_score"])

    def test_cross_lane_emits_absorption_buy(self) -> None:
        payload = {
            "available": True,
            "latest_impact_summary": {
                "impact_regime": "BUY_ABSORPTION",
                "absorption_score": 0.7,
                "impact_method": IMPACT_METHOD,
            },
            "latest_liquidity_summary": {
                "depth_replenishment": 370.0,
            },
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_book(payload)
        assert snapshot is not None
        self.assertEqual(snapshot.get("order_book_impact_regime"), "BUY_ABSORPTION")
        signals = [row["signal"] for row in evidence]
        self.assertIn("ABSORPTION_BUY", signals)


class MicrostructureForecastTests(unittest.TestCase):
    def _book(self, bid: float, ask: float, bid_size: float, ask_size: float) -> dict:
        return {
            "bids": [{"price": bid, "size": bid_size}],
            "asks": [{"price": ask, "size": ask_size}],
        }

    def test_continuation_up_synthetic(self) -> None:
        snapshot = self._book(100.0, 100.04, 800, 200)
        result = compute_microstructure_forecast(
            snapshot,
            ofi_value=250.0,
            book_state_valid=True,
            bar_delta=150.0,
            recent_mid_deltas=[0.01, 0.02, 0.015],
        )
        self.assertEqual(result.direction_bias, ForecastDirection.UP)
        self.assertGreaterEqual(result.continuation_probability, CONTINUATION_THRESHOLD)

    def test_reversal_risk_synthetic(self) -> None:
        snapshot = self._book(100.0, 100.04, 500, 300)
        result = compute_microstructure_forecast(
            snapshot,
            ofi_value=120.0,
            book_state_valid=True,
            fragility_score=0.4,
            impact_regime=ImpactRegime.BUY_EXHAUSTION,
            exhaustion_score=0.6,
            bar_delta=80.0,
            recent_mid_deltas=[0.01, 0.02],
        )
        self.assertGreaterEqual(result.reversal_probability, REVERSAL_THRESHOLD)

    def test_missing_trade_flow_fail_closed(self) -> None:
        snapshot = self._book(100.0, 100.04, 500, 300)
        result = compute_microstructure_forecast(
            snapshot,
            ofi_value=50.0,
            book_state_valid=True,
            bar_delta=None,
        )
        self.assertIn("MISSING_TRADE_FLOW", result.quality_flags)
        self.assertLess(result.model_confidence, 0.75)

    def test_invalid_book_fail_closed(self) -> None:
        snapshot = {"bids": [], "asks": []}
        result = compute_microstructure_forecast(snapshot, book_state_valid=False)
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.direction_bias, ForecastDirection.NEUTRAL)
        self.assertEqual(result.continuation_probability, 0.0)

    def test_build_microstructure_forecast_evidence_detail(self) -> None:
        snapshot = self._book(100.0, 100.04, 700, 250)
        evidence = build_microstructure_forecast_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:02Z",
            available_time="2026-07-21T20:30:02Z",
            snapshot=snapshot,
            ofi_value=200.0,
            bar_delta=120.0,
            recent_mid_deltas=[0.01, 0.02],
        )
        assert evidence is not None
        self.assertEqual(evidence.forecast_method, FORECAST_METHOD)
        self.assertTrue(evidence.supporting_evidence)

    def test_nvda_forecast_golden_fixture_regression(self) -> None:
        depth_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_book" / "nvda_depth_slice.json"
        flow_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_order_flow_slice.json"
        expected_fixture = ROOT / "tests" / "fixtures" / "order_flow" / "nvda_forecast_expected.json"
        depth = json.loads(depth_fixture.read_text(encoding="utf-8"))
        flow = json.loads(flow_fixture.read_text(encoding="utf-8"))
        expected = json.loads(expected_fixture.read_text(encoding="utf-8"))
        bars = {str(row["date"]): row for row in flow["bars"]}
        snapshots = depth["snapshots"]
        level_count = depth["level_count"]
        trajectory = compute_trajectory_resiliency(snapshots, level_count=level_count)
        prev_snapshot = None
        prev_mid = None
        recent_mid_deltas: list[float] = []
        for index, snapshot in enumerate(snapshots):
            if prev_snapshot is None:
                prev_snapshot = snapshot
                bbo = snapshot["bids"][0], snapshot["asks"][0]
                prev_mid = (float(bbo[0]["price"]) + float(bbo[1]["price"])) / 2
                continue
            row = next(r for r in expected["transitions"] if r["index"] == index)
            ofi = compute_ofi(
                prev_snapshot,
                snapshot,
                method=OFI_METHOD_MULTILEVEL_CS,
                level_count=level_count,
            )
            liq = compute_liquidity_dynamics(
                prev_snapshot,
                snapshot,
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            prev_bar = bars.get(str(prev_snapshot["event_time"]))
            curr_bar = bars.get(str(snapshot["event_time"]))
            bar_delta = float(curr_bar["delta"]) if curr_bar else None
            prev_bar_delta = float(prev_bar["delta"]) if prev_bar else None
            impact = compute_impact_dynamics(
                prev_snapshot,
                snapshot,
                bar_delta=bar_delta,
                prev_bar_delta=prev_bar_delta,
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            cvd_slope = (
                bar_delta - prev_bar_delta
                if bar_delta is not None and prev_bar_delta is not None
                else None
            )
            result = compute_microstructure_forecast(
                snapshot,
                ofi_value=ofi.value,
                book_state_valid=ofi.book_state_valid,
                fragility_score=liq.fragility_score,
                resiliency_score=liq.resiliency_score,
                impact_regime=impact.impact_regime,
                absorption_score=impact.absorption_score,
                exhaustion_score=impact.exhaustion_score,
                bar_delta=bar_delta,
                cvd_slope=cvd_slope,
                recent_mid_deltas=recent_mid_deltas,
            )
            self.assertEqual(result.direction_bias.value, row["direction_bias"])
            self.assertEqual(result.continuation_probability, row["continuation_probability"])
            self.assertEqual(result.reversal_probability, row["reversal_probability"])
            self.assertEqual(result.expected_mid_delta, row["expected_mid_delta"])
            self.assertEqual(result.forecast_method, row["forecast_method"])
            bbo_bid = float(snapshot["bids"][0]["price"])
            bbo_ask = float(snapshot["asks"][0]["price"])
            curr_mid = (bbo_bid + bbo_ask) / 2
            if prev_mid is not None and ofi.book_state_valid:
                recent_mid_deltas.append(curr_mid - prev_mid)
                if len(recent_mid_deltas) > 5:
                    recent_mid_deltas = recent_mid_deltas[-5:]
            prev_mid = curr_mid
            prev_snapshot = snapshot

    def test_cross_lane_emits_continuation_up(self) -> None:
        payload = {
            "available": True,
            "latest_microstructure_forecast": {
                "direction_bias": "UP",
                "continuation_probability": 0.62,
                "reversal_probability": 0.2,
                "forecast_method": FORECAST_METHOD,
            },
            "latest_liquidity_summary": {"fragility_score": 0.1},
            "latest_impact_summary": {"impact_regime": "NEUTRAL"},
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_book(payload)
        assert snapshot is not None
        self.assertEqual(snapshot.get("order_book_forecast_direction"), "UP")
        signals = [row["signal"] for row in evidence]
        self.assertIn("MICROSTRUCTURE_CONTINUATION_UP", signals)


class ExecutionForecastTests(unittest.TestCase):
    def _book(self, bid: float, ask: float, bid_size: float, ask_size: float) -> dict:
        return {
            "bids": [{"price": bid, "size": bid_size}],
            "asks": [{"price": ask, "size": ask_size}],
        }

    def test_aggressive_fill_probability_from_touch_depth(self) -> None:
        snapshot = self._book(100.0, 100.04, 800, 40)
        result = compute_execution_forecast(snapshot, order_qty=100.0, order_side="buy")
        self.assertEqual(result.aggressive_fill_probability, 0.4)
        self.assertTrue(result.book_state_valid)

    def test_invalid_book_fail_closed(self) -> None:
        result = compute_execution_forecast({"bids": [], "asks": []}, book_state_valid=False)
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.aggressive_fill_probability, 0.0)
        self.assertIn("BOOK_STATE_INVALID", result.quality_flags)

    def test_build_execution_forecast_evidence(self) -> None:
        snapshot = self._book(100.0, 100.04, 500, 250)
        evidence = build_execution_forecast_evidence(
            instrument="NVDA",
            venue="US_EQUITY",
            event_time="2026-07-21T20:30:02Z",
            available_time="2026-07-21T20:30:02Z",
            snapshot=snapshot,
            continuation_probability=0.6,
            direction_bias="UP",
        )
        assert evidence is not None
        self.assertEqual(evidence.execution_method, EXECUTION_METHOD)
        self.assertTrue(evidence.supporting_evidence)

    def test_nvda_execution_golden_fixture_regression(self) -> None:
        depth_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_book" / "nvda_depth_slice.json"
        flow_fixture = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_order_flow_slice.json"
        expected_fixture = ROOT / "tests" / "fixtures" / "order_flow" / "nvda_execution_forecast_expected.json"
        depth = json.loads(depth_fixture.read_text(encoding="utf-8"))
        flow = json.loads(flow_fixture.read_text(encoding="utf-8"))
        expected = json.loads(expected_fixture.read_text(encoding="utf-8"))
        bars = {str(row["date"]): row for row in flow["bars"]}
        snapshots = depth["snapshots"]
        level_count = depth["level_count"]
        trajectory = compute_trajectory_resiliency(snapshots, level_count=level_count)
        prev_snapshot = None
        prev_mid = None
        recent_mid_deltas: list[float] = []
        for index, snapshot in enumerate(snapshots):
            if prev_snapshot is None:
                forecast = compute_microstructure_forecast(snapshot, ofi_value=0.0, book_state_valid=True)
                result = compute_execution_forecast(
                    snapshot,
                    continuation_probability=forecast.continuation_probability,
                    reversal_probability=forecast.reversal_probability,
                    direction_bias=forecast.direction_bias,
                )
                row = next(r for r in expected["transitions"] if r["index"] == index)
                self.assertEqual(result.aggressive_fill_probability, row["aggressive_fill_probability"])
                self.assertEqual(result.expected_slippage_spread_fraction, row["expected_slippage_spread_fraction"])
                self.assertEqual(result.adverse_selection_risk, row["adverse_selection_risk"])
                prev_snapshot = snapshot
                bbo = snapshot["bids"][0], snapshot["asks"][0]
                prev_mid = (float(bbo[0]["price"]) + float(bbo[1]["price"])) / 2
                continue
            row = next(r for r in expected["transitions"] if r["index"] == index)
            ofi = compute_ofi(
                prev_snapshot,
                snapshot,
                method=OFI_METHOD_MULTILEVEL_CS,
                level_count=level_count,
            )
            liq = compute_liquidity_dynamics(
                prev_snapshot,
                snapshot,
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            prev_bar = bars.get(str(prev_snapshot["event_time"]))
            curr_bar = bars.get(str(snapshot["event_time"]))
            bar_delta = float(curr_bar["delta"]) if curr_bar else None
            prev_bar_delta = float(prev_bar["delta"]) if prev_bar else None
            impact = compute_impact_dynamics(
                prev_snapshot,
                snapshot,
                bar_delta=bar_delta,
                prev_bar_delta=prev_bar_delta,
                level_count=level_count,
                trajectory_resiliency=trajectory,
            )
            cvd_slope = (
                bar_delta - prev_bar_delta
                if bar_delta is not None and prev_bar_delta is not None
                else None
            )
            forecast = compute_microstructure_forecast(
                snapshot,
                ofi_value=ofi.value,
                book_state_valid=ofi.book_state_valid,
                fragility_score=liq.fragility_score,
                resiliency_score=liq.resiliency_score,
                impact_regime=impact.impact_regime,
                absorption_score=impact.absorption_score,
                exhaustion_score=impact.exhaustion_score,
                bar_delta=bar_delta,
                cvd_slope=cvd_slope,
                recent_mid_deltas=recent_mid_deltas,
            )
            result = compute_execution_forecast(
                snapshot,
                book_state_valid=ofi.book_state_valid,
                fragility_score=liq.fragility_score,
                continuation_probability=forecast.continuation_probability,
                reversal_probability=forecast.reversal_probability,
                direction_bias=forecast.direction_bias,
                exhaustion_score=impact.exhaustion_score,
                impact_regime=impact.impact_regime,
                level_count=level_count,
            )
            self.assertEqual(result.aggressive_fill_probability, row["aggressive_fill_probability"])
            self.assertEqual(result.expected_slippage_spread_fraction, row["expected_slippage_spread_fraction"])
            self.assertEqual(result.adverse_selection_risk, row["adverse_selection_risk"])
            bbo_bid = float(snapshot["bids"][0]["price"])
            bbo_ask = float(snapshot["asks"][0]["price"])
            curr_mid = (bbo_bid + bbo_ask) / 2
            if prev_mid is not None and ofi.book_state_valid:
                recent_mid_deltas.append(curr_mid - prev_mid)
                if len(recent_mid_deltas) > 5:
                    recent_mid_deltas = recent_mid_deltas[-5:]
            prev_mid = curr_mid
            prev_snapshot = snapshot

    def test_cross_lane_emits_execution_signals(self) -> None:
        payload = {
            "available": True,
            "latest_execution_forecast": {
                "execution_method": EXECUTION_METHOD,
                "aggressive_fill_probability": 0.2,
                "expected_slippage_spread_fraction": 0.01,
                "adverse_selection_risk": 0.55,
            },
        }
        snapshot, evidence = build_cross_lane_snapshot_from_order_book(payload)
        assert snapshot is not None
        self.assertEqual(snapshot.get("order_book_fill_probability"), 0.2)
        signals = [row["signal"] for row in evidence]
        self.assertIn("EXECUTION_FILL_RISK", signals)
        self.assertIn("EXECUTION_SLIPPAGE_ELEVATED", signals)
        self.assertIn("ADVERSE_SELECTION_RISK_ELEVATED", signals)


class BookSequenceValidationTests(unittest.TestCase):
    def _book(self, seq: int | None = None) -> dict:
        row: dict = {
            "bids": [{"price": 100.0, "size": 50}],
            "asks": [{"price": 100.25, "size": 40}],
        }
        if seq is not None:
            row["book_sequence"] = seq
        return row

    def test_no_sequence_fields_passes(self) -> None:
        prev = self._book()
        curr = self._book()
        valid, flags = snapshot_pair_sequence_valid(prev, curr)
        self.assertTrue(valid)
        self.assertEqual(flags, ())
        result = compute_multilevel_ofi(prev, curr, level_count=1)
        self.assertTrue(result.book_state_valid)

    def test_sequence_gap_invalidates_ofi(self) -> None:
        prev = self._book(1)
        curr = self._book(3)
        valid, flags = snapshot_pair_sequence_valid(prev, curr)
        self.assertFalse(valid)
        self.assertIn("BOOK_SEQUENCE_GAP", flags)
        result = compute_multilevel_ofi(prev, curr, level_count=1)
        self.assertFalse(result.book_state_valid)

    def test_missing_sequence_on_one_side_fail_closed(self) -> None:
        prev = self._book(1)
        curr = self._book()
        valid, flags = snapshot_pair_sequence_valid(prev, curr)
        self.assertFalse(valid)
        self.assertIn("BOOK_SEQUENCE_MISSING", flags)
        self.assertFalse(snapshot_pair_book_state_valid(prev, curr))


if __name__ == "__main__":
    unittest.main()
