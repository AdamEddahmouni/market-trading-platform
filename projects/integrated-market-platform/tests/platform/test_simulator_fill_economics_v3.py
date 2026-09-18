"""IMP-SIMULATOR-FILL-ECONOMICS-V3 unit and integration tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import SIMULATOR_VERSION  # noqa: E402
from market_platform_foundation.intelligence.historical_research_harness.fill_economics import (  # noqa: E402
    ACCOUNTING_VERSION,
    COST_MODEL_VERSION,
    NET_PNL_TOLERANCE,
    aggregate_fill_economics,
    assert_fill_economics_invariants,
)
from market_platform_foundation.intelligence.historical_research_harness.simulator import (  # noqa: E402
    run_historical_development_simulator_research,
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
    price_minor = int(round(price_dollars * 100))
    return {
        "direction": direction,
        "fill_id": fill_id,
        "fill_price_minor": price_minor,
        "fill_quantity": quantity,
        "fill_time": fill_time,
        "instrument_id": "canonical:EQUITY:XNAS:TEST",
    }


def _bar(close: float, time_ns: int = 9_000_000_000) -> dict:
    return {
        "available_time": time_ns,
        "event_type": "BAR_OHLCV_1M",
        "instrument_id": "canonical:EQUITY:XNAS:TEST",
        "bar_payload": {"close": str(close), "volume": 1000},
    }


def _economics(*fills: dict, cost_bps: float = 10.0, events: list | None = None) -> dict:
    return aggregate_fill_economics(
        list(fills),
        events=events or [_bar(11.0)],
        policy=POLICY,
        cost_slippage_bps=cost_bps,
        instrument_id="canonical:EQUITY:XNAS:TEST",
    )


class SimulatorFillEconomicsV3UnitTests(unittest.TestCase):
    def test_long_win_round_trip(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0, fill_time=1),
            _fill("s", direction="short", quantity=100, price_dollars=11.0, fill_time=2),
            cost_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_realized_pnl"], 100.0)
        self.assertAlmostEqual(summary["gross_unrealized_pnl"], 0.0)
        self.assertAlmostEqual(summary["gross_pnl"], 100.0)

    def test_long_loss_round_trip(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            _fill("s", direction="short", quantity=100, price_dollars=9.0),
            cost_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_realized_pnl"], -100.0)

    def test_short_round_trip_profit(self) -> None:
        summary = _economics(
            _fill("s", direction="short", quantity=100, price_dollars=10.0),
            _fill("b", direction="long", quantity=100, price_dollars=9.0),
            cost_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_realized_pnl"], 100.0)

    def test_partial_close(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            _fill("s1", direction="short", quantity=40, price_dollars=11.0),
            _fill("s2", direction="short", quantity=60, price_dollars=12.0),
            cost_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_realized_pnl"], 40.0 + 120.0)

    def test_position_increase_weighted_average(self) -> None:
        summary = _economics(
            _fill("b1", direction="long", quantity=100, price_dollars=10.0),
            _fill("b2", direction="long", quantity=100, price_dollars=12.0),
            events=[_bar(12.0)],
            cost_bps=0.0,
        )
        self.assertEqual(summary["position_shares"], 200)
        last = summary["fill_economics"][-1]
        self.assertAlmostEqual(last["average_entry_price_after"], 11.0)

    def test_reversal_long_to_short(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            _fill("r", direction="short", quantity=150, price_dollars=12.0),
            events=[_bar(12.0)],
            cost_bps=0.0,
        )
        self.assertEqual(summary["position_shares"], -50)
        self.assertAlmostEqual(summary["gross_realized_pnl"], 200.0)

    def test_reversal_short_to_long(self) -> None:
        summary = _economics(
            _fill("s", direction="short", quantity=100, price_dollars=10.0),
            _fill("r", direction="long", quantity=150, price_dollars=8.0),
            events=[_bar(8.0)],
            cost_bps=0.0,
        )
        self.assertEqual(summary["position_shares"], 50)
        self.assertAlmostEqual(summary["gross_realized_pnl"], 200.0)

    def test_policy_fees_charged_once_not_doubled(self) -> None:
        fee_policy = {
            **POLICY,
            "fee_minor_per_order": 100,
            "commission_minor_per_share": 2,
        }
        fills = [
            _fill("b", direction="long", quantity=10, price_dollars=10.0),
            _fill("s", direction="short", quantity=10, price_dollars=11.0),
        ]
        summary = aggregate_fill_economics(
            fills,
            events=[_bar(11.0)],
            policy=fee_policy,
            cost_slippage_bps=0.0,
        )
        market_realized = 10.0
        per_fill_fees = 100 + 2 * 10
        expected_policy_fees = 2 * per_fill_fees / 100.0
        self.assertAlmostEqual(summary["gross_realized_pnl"], market_realized)
        self.assertAlmostEqual(summary["transaction_costs"], expected_policy_fees)
        self.assertAlmostEqual(summary["net_pnl"], market_realized - expected_policy_fees)
        self.assertAlmostEqual(
            summary["ledger_post_fee_realized_pnl_minor"],
            int(round((market_realized - expected_policy_fees) * 100)),
        )
        assert_fill_economics_invariants(summary, trade_intent_count=2)

    def test_commission_only_policy_net_identity(self) -> None:
        policy = {**POLICY, "commission_minor_per_share": 5, "fee_minor_per_order": 0}
        summary = aggregate_fill_economics(
            [
                _fill("b", direction="long", quantity=20, price_dollars=10.0),
                _fill("s", direction="short", quantity=20, price_dollars=10.5),
            ],
            events=[_bar(10.5)],
            policy=policy,
            cost_slippage_bps=10.0,
        )
        notional = 20 * 10.0 + 20 * 10.5
        slippage = notional * (10.0 / 10_000.0)
        policy_fees = (5 * 20 + 5 * 20) / 100.0
        self.assertAlmostEqual(summary["gross_realized_pnl"], 10.0)
        self.assertAlmostEqual(summary["transaction_costs"], slippage + policy_fees)
        self.assertAlmostEqual(summary["net_pnl"], summary["gross_pnl"] - summary["transaction_costs"])

    def test_costs_from_notional_independent_of_pnl_sign(self) -> None:
        win = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            _fill("s", direction="short", quantity=100, price_dollars=11.0),
            cost_bps=25.0,
        )
        loss = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            _fill("s", direction="short", quantity=100, price_dollars=9.0),
            cost_bps=25.0,
        )
        win_notional = 100 * 10.0 + 100 * 11.0
        loss_notional = 100 * 10.0 + 100 * 9.0
        rate = 25.0 / 10_000.0
        self.assertAlmostEqual(win["transaction_costs"], win_notional * rate)
        self.assertAlmostEqual(loss["transaction_costs"], loss_notional * rate)
        self.assertGreater(win["gross_pnl"], 0)
        self.assertLess(loss["gross_pnl"], 0)
        self.assertGreater(loss["transaction_costs"], 0)

    def test_no_trade_exact_zeros(self) -> None:
        summary = _economics(cost_bps=5.0)
        self.assertEqual(summary["fill_count"], 0)
        self.assertEqual(summary["turnover"], 0.0)
        self.assertEqual(summary["transaction_costs"], 0.0)
        self.assertEqual(summary["gross_pnl"], 0.0)
        self.assertEqual(summary["net_pnl"], 0.0)
        assert_fill_economics_invariants(summary, trade_intent_count=0)

    def test_determinism(self) -> None:
        fills = [
            _fill("b", direction="long", quantity=10, price_dollars=10.0),
            _fill("s", direction="short", quantity=10, price_dollars=10.5),
        ]
        first = aggregate_fill_economics(fills, events=[_bar(10.5)], policy=POLICY, cost_slippage_bps=5.0)
        second = aggregate_fill_economics(fills, events=[_bar(10.5)], policy=POLICY, cost_slippage_bps=5.0)
        self.assertEqual(first, second)

    def test_net_pnl_identity(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=50, price_dollars=20.0),
            _fill("s", direction="short", quantity=50, price_dollars=21.0),
            cost_bps=12.0,
        )
        self.assertLessEqual(
            abs(summary["net_pnl"] - (summary["gross_pnl"] - summary["transaction_costs"])),
            NET_PNL_TOLERANCE,
        )

    def test_unrealized_from_last_bar_mark(self) -> None:
        summary = _economics(
            _fill("b", direction="long", quantity=100, price_dollars=10.0),
            events=[_bar(10.5)],
            cost_bps=0.0,
        )
        self.assertAlmostEqual(summary["gross_realized_pnl"], 0.0)
        self.assertAlmostEqual(summary["gross_unrealized_pnl"], 50.0)
        self.assertAlmostEqual(summary["gross_pnl"], 50.0)

    def test_version_strings_frozen(self) -> None:
        self.assertEqual(ACCOUNTING_VERSION, "simulator-research-fill-economics/3.0.1")
        self.assertEqual(COST_MODEL_VERSION, "simulator-research/notional-linear-bps/1.0.0")
        self.assertEqual(SIMULATOR_VERSION, "phase7.bar-conservative/1.1.0")


class SimulatorFillEconomicsV3IntegrationTests(unittest.TestCase):
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

    def test_integration_no_trade_zero_economics(self) -> None:
        result = run_historical_development_simulator_research(
            [self._bar_event(1_000_000)],
            predictions=[{"decision_time_ns": 1_000_000, "predicted_direction": 0}],
            simulator_version=SIMULATOR_VERSION,
            cost_slippage_bps=10.0,
        )
        self.assertEqual(result["trade_intents"], 0)
        self.assertEqual(result["fills"], 0)
        self.assertEqual(result["transaction_costs"], 0.0)
        self.assertEqual(result["gross_pnl"], 0.0)
        self.assertEqual(result["net_pnl"], 0.0)

    def test_integration_active_baseline_has_costs(self) -> None:
        decision_time_ns = 1_000_000
        events = [
            self._bar_event(decision_time_ns + index * 60_000_000_000, close=100.0 + index * 0.1)
            for index in range(3)
        ]
        result = run_historical_development_simulator_research(
            events,
            predictions=[{"decision_time_ns": decision_time_ns, "predicted_direction": 1}],
            simulator_version=SIMULATOR_VERSION,
            cost_slippage_bps=10.0,
        )
        self.assertGreater(result["signal_count"], 0)
        self.assertGreater(result["trade_intents"], 0)
        self.assertGreater(result["fills"], 0)
        self.assertGreater(result["traded_notional"], 0.0)
        self.assertGreater(result["transaction_costs"], 0.0)
        self.assertIsInstance(result["fill_economics"], list)
        self.assertEqual(len(result["fill_economics"]), result["fills"])
        self.assertEqual(len(result["fill_economics"]), result["fill_count"])
        self.assertEqual(result["accounting_version"], ACCOUNTING_VERSION)
        self.assertEqual(result["cost_model_version"], COST_MODEL_VERSION)


if __name__ == "__main__":
    unittest.main()
