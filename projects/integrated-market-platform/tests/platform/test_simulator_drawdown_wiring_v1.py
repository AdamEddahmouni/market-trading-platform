"""LANE-E-HYP-SIMULATOR-DRAWDOWN-WIRING-V1 harness tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import SIMULATOR_VERSION  # noqa: E402
from market_platform_foundation.intelligence.historical_research_harness.fill_economics import (  # noqa: E402
    aggregate_fill_economics,
)
from market_platform_foundation.intelligence.historical_research_harness.simulator import (  # noqa: E402
    run_historical_development_simulator_research,
)
from market_platform_foundation.intelligence.historical_research_harness.simulator_drawdown import (  # noqa: E402
    DRAWDOWN_METRICS_VERSION,
    MAX_DRAWDOWN_SOURCE_EQUITY_CURVE,
    max_peak_to_trough_drawdown,
)

POLICY = {
    "commission_minor_per_share": 0,
    "fee_minor_per_order": 0,
    "initial_cash_minor": 1_000_000_00,
    "price_scale": 100,
}


def _fill(
    fill_id: str,
    *,
    direction: str,
    quantity: int,
    price_dollars: float,
    fill_time: int = 1,
) -> dict:
    return {
        "direction": direction,
        "fill_id": fill_id,
        "fill_price_minor": int(round(price_dollars * 100)),
        "fill_quantity": quantity,
        "fill_time": fill_time,
        "instrument_id": "canonical:EQUITY:XNAS:TEST",
    }


def _bar(close: float, time_ns: int) -> dict:
    return {
        "available_time": time_ns,
        "event_type": "BAR_OHLCV_1M",
        "instrument_id": "canonical:EQUITY:XNAS:TEST",
        "bar_payload": {"close": str(close), "volume": 1000},
    }


class SimulatorDrawdownWiringUnitTests(unittest.TestCase):
    def test_peak_to_trough_basic(self) -> None:
        self.assertAlmostEqual(max_peak_to_trough_drawdown([0.0, 10.0, 4.0, 8.0]), 6.0)
        self.assertAlmostEqual(max_peak_to_trough_drawdown([]), 0.0)
        self.assertAlmostEqual(max_peak_to_trough_drawdown([0.0]), 0.0)

    def test_monotonic_gains_zero_drawdown(self) -> None:
        self.assertAlmostEqual(max_peak_to_trough_drawdown([0.0, 5.0, 12.0, 20.0]), 0.0)
        summary = aggregate_fill_economics(
            [
                _fill("b", direction="long", quantity=100, price_dollars=10.0, fill_time=1),
                _fill("s", direction="short", quantity=100, price_dollars=11.0, fill_time=2),
            ],
            events=[_bar(10.0, 1), _bar(11.0, 2), _bar(12.0, 3)],
            policy=POLICY,
            cost_slippage_bps=0.0,
        )
        self.assertGreater(summary["net_pnl"], 0.0)
        self.assertAlmostEqual(summary["max_drawdown"], 0.0)

    def test_full_recovery_preserves_prior_max_drawdown(self) -> None:
        self.assertAlmostEqual(max_peak_to_trough_drawdown([0.0, 10.0, 2.0, 9.0]), 8.0)

    def test_all_losses_peak_at_start(self) -> None:
        curve = [0.0, -50.0, -120.0, -90.0]
        self.assertAlmostEqual(max_peak_to_trough_drawdown(curve), 120.0)
        summary = aggregate_fill_economics(
            [
                _fill("b", direction="long", quantity=100, price_dollars=10.0, fill_time=1),
                _fill("s", direction="short", quantity=100, price_dollars=8.0, fill_time=2),
            ],
            events=[_bar(10.0, 1), _bar(8.0, 2)],
            policy=POLICY,
            cost_slippage_bps=0.0,
        )
        self.assertLess(summary["net_pnl"], 0.0)
        self.assertAlmostEqual(summary["max_drawdown"], 200.0)

    def test_deterministic_rerun(self) -> None:
        fills = [
            _fill("b", direction="long", quantity=50, price_dollars=20.0, fill_time=1),
            _fill("s", direction="short", quantity=50, price_dollars=18.0, fill_time=2),
        ]
        events = [_bar(20.0, 1), _bar(17.0, 2)]
        kwargs = {"events": events, "policy": POLICY, "cost_slippage_bps": 5.0}
        first = aggregate_fill_economics(fills, **kwargs)
        second = aggregate_fill_economics(fills, **kwargs)
        self.assertEqual(first["max_drawdown"], second["max_drawdown"])
        self.assertEqual(first["equity_curve_point_count"], second["equity_curve_point_count"])

    def test_no_fills_zero_drawdown(self) -> None:
        summary = aggregate_fill_economics(
            [],
            events=[_bar(10.0, 1)],
            policy=POLICY,
            cost_slippage_bps=0.0,
        )
        self.assertEqual(summary["max_drawdown"], 0.0)
        self.assertEqual(summary["max_drawdown_source"], MAX_DRAWDOWN_SOURCE_EQUITY_CURVE)
        self.assertEqual(summary["drawdown_metrics_version"], DRAWDOWN_METRICS_VERSION)

    def test_open_loss_mark_increases_drawdown(self) -> None:
        summary = aggregate_fill_economics(
            [_fill("b", direction="long", quantity=100, price_dollars=10.0, fill_time=1)],
            events=[_bar(10.0, 1), _bar(8.0, 2)],
            policy=POLICY,
            cost_slippage_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_unrealized_pnl"], -200.0)
        self.assertGreater(summary["max_drawdown"], 0.0)
        self.assertAlmostEqual(summary["max_drawdown"], 200.0)

    def test_closed_losing_round_trip_drawdown(self) -> None:
        summary = aggregate_fill_economics(
            [
                _fill("b", direction="long", quantity=100, price_dollars=10.0, fill_time=1),
                _fill("s", direction="short", quantity=100, price_dollars=9.0, fill_time=2),
            ],
            events=[_bar(10.0, 1), _bar(9.0, 2)],
            policy=POLICY,
            cost_slippage_bps=0.0,
        )
        self.assertLess(summary["net_pnl"], 0.0)
        self.assertGreater(summary["max_drawdown"], 0.0)


class SimulatorDrawdownWiringIntegrationTests(unittest.TestCase):
    def _bar_event(self, time_ns: int, *, close: float = 100.0) -> dict:
        return {
            "available_time": time_ns,
            "event_time": time_ns,
            "event_type": "BAR_OHLCV_1M",
            "instrument_id": "canonical:EQUITY:XNAS:AAPL",
            "normalized_event_id": f"evt-{time_ns}",
            "bar_payload": {
                "open": str(close - 0.1),
                "high": str(close + 0.2),
                "low": str(close - 0.2),
                "close": str(close),
                "volume": 5000,
            },
        }

    def test_simulator_surfaces_equity_curve_drawdown(self) -> None:
        decision_time_ns = 1_000_000
        events = [
            self._bar_event(decision_time_ns, close=100.0),
            self._bar_event(decision_time_ns + 60_000_000_000, close=99.0),
        ]
        result = run_historical_development_simulator_research(
            events,
            predictions=[{"decision_time_ns": decision_time_ns, "predicted_direction": 1}],
            simulator_version=SIMULATOR_VERSION,
            cost_slippage_bps=10.0,
        )
        self.assertEqual(result["max_drawdown_source"], MAX_DRAWDOWN_SOURCE_EQUITY_CURVE)
        self.assertIsNotNone(result["max_drawdown"])
        self.assertGreaterEqual(result["max_drawdown"], 0.0)
        self.assertGreater(result["equity_curve_point_count"], 1)


if __name__ == "__main__":
    unittest.main()
