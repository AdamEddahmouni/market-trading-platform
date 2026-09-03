"""Tests for Options O9 execution / simulation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.options_quality import OptionQualityFlag  # noqa: E402
from market_platform_foundation.donor_bridge.cross_lane_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_options,
)
from market_platform_foundation.execution.options_conservative import (  # noqa: E402
    OptionsConservativeSimulator,
    simulate_from_candidate,
)
from market_platform_foundation.options.execution import (  # noqa: E402
    EXECUTION_METHOD,
    SIMULATOR_REGISTRY_ID,
    build_execution_snapshot,
    build_options_order_intent,
    conservative_fill_price,
    evaluate_early_exercise,
    load_execution_fixture,
    process_assignment_event,
    run_options_lifecycle,
    settle_at_expiry,
    simulate_multi_leg_entry,
)
from market_platform_foundation.options.payoff import OptionLeg  # noqa: E402
from market_platform_foundation.options.strategy import (  # noqa: E402
    build_candidate_legs,
    build_strategy_snapshot,
)
from market_platform_foundation.portfolio.options_ledger import (  # noqa: E402
    apply_option_fill,
    build_options_ledger_state,
)

EXECUTION_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_options_execution_slice.json"
STRATEGY_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_strategy_optimizer_slice.json"


class OptionsO9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.execution_fixture = json.loads(EXECUTION_FIXTURE.read_text(encoding="utf-8"))
        cls.strategy_fixture = json.loads(STRATEGY_FIXTURE.read_text(encoding="utf-8"))

    def test_conservative_fill_price_long_pays_ask(self) -> None:
        row = self.execution_fixture["chain_rows"][0]
        priced = conservative_fill_price(row, "long")
        self.assertTrue(priced["available"])
        self.assertEqual(priced["fill_price"], row["ask"])

    def test_conservative_fill_price_short_receives_bid(self) -> None:
        row = self.execution_fixture["chain_rows"][0]
        priced = conservative_fill_price(row, "short")
        self.assertTrue(priced["available"])
        self.assertEqual(priced["fill_price"], row["bid"])

    def test_multi_leg_entry_fails_closed_on_missing_row(self) -> None:
        leg = OptionLeg(
            call_put="call",
            strike=999.0,
            expiry="2026-08-15",
            side="long",
            entry_premium=1.0,
        )
        result = simulate_multi_leg_entry([leg], self.execution_fixture["chain_rows"])
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "CHAIN_ROW_MISSING")

    def test_multi_leg_spread_both_legs_fill(self) -> None:
        built = build_candidate_legs(
            "bull_call_spread",
            self.execution_fixture["chain_rows"],
            spot=128.0,
        )
        self.assertTrue(built["available"])
        result = simulate_multi_leg_entry(built["legs"], self.execution_fixture["chain_rows"])
        self.assertTrue(result["available"])
        self.assertEqual(len(result["entry_fills"]), 2)

    def test_settle_at_expiry_itm_long_call(self) -> None:
        position = {
            "call_put": "call",
            "strike": 130.0,
            "expiry": "2026-08-15",
            "side": "long",
            "quantity": 1,
            "multiplier": 100.0,
            "entry_premium": 1.85,
        }
        events = settle_at_expiry([position], 135.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "EXPIRATION")
        self.assertGreater(events[0]["realized_pnl_delta"], 0)

    def test_settle_at_expiry_otm_long_call(self) -> None:
        position = {
            "call_put": "call",
            "strike": 130.0,
            "expiry": "2026-08-15",
            "side": "long",
            "quantity": 1,
            "multiplier": 100.0,
            "entry_premium": 1.85,
        }
        events = settle_at_expiry([position], 120.0)
        self.assertEqual(events[0]["event_type"], "EXPIRATION")
        self.assertLess(events[0]["realized_pnl_delta"], 0)

    def test_early_exercise_deep_itm(self) -> None:
        position = {
            "call_put": "call",
            "strike": 100.0,
            "expiry": "2026-08-15",
            "side": "long",
            "quantity": 1,
            "multiplier": 100.0,
            "entry_premium": 30.5,
        }
        result = evaluate_early_exercise(position, 135.0)
        self.assertTrue(result["should_exercise"])

    def test_assignment_on_short_put(self) -> None:
        position = {
            "call_put": "put",
            "strike": 125.0,
            "expiry": "2026-08-15",
            "side": "short",
            "quantity": 1,
            "multiplier": 100.0,
            "entry_premium": 1.45,
        }
        result = process_assignment_event(position, 118.0)
        self.assertTrue(result["available"])
        self.assertEqual(result["event_type"], "ASSIGNMENT")
        self.assertLess(result["stock_delta"], 0)

    def test_options_conservative_simulator_fills(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = build_strategy_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        self.assertEqual(strategy["status"], "RANKED")
        best = strategy["best_candidate"]
        assert isinstance(best, dict)
        order, fills = simulate_from_candidate(
            best,
            symbol="NVDA",
            as_of_time=self.strategy_fixture["as_of_time"],
            chain_rows=self.execution_fixture["chain_rows"],
            scenario=self.execution_fixture["scenarios"]["single_leg_fill"],
        )
        self.assertEqual(order["state"], "FILLED")
        self.assertEqual(len(fills), len(best["legs"]))

    def test_build_execution_snapshot_simulated(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = build_strategy_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        snapshot = build_execution_snapshot(
            "NVDA",
            self.execution_fixture["as_of_time"],
            strategy_snapshot=strategy,
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
            scenario=self.execution_fixture["scenarios"]["single_leg_fill"],
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["status"], "SIMULATED")
        self.assertEqual(snapshot["outcome"], "FILLED")
        self.assertEqual(snapshot["method"], EXECUTION_METHOD)
        self.assertEqual(snapshot["simulator_registry_id"], SIMULATOR_REGISTRY_ID)
        self.assertGreater(len(snapshot["entry_fills"]), 0)
        self.assertGreater(snapshot["realized_pnl"], 0)

    def test_fail_closed_without_ranked_strategy(self) -> None:
        snapshot = build_execution_snapshot(
            "NVDA",
            self.execution_fixture["as_of_time"],
            strategy_snapshot={"available": True, "status": "NO_CLEAR_EDGE", "outcome": "NO_CLEAR_EDGE"},
            chain_rows=self.execution_fixture["chain_rows"],
        )
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["reason"], "STRATEGY_NOT_RANKED")
        self.assertIn(OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value, snapshot["quality_flags"])

    def test_execution_replay_hash_stable(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = build_strategy_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        kwargs = {
            "strategy_snapshot": strategy,
            "chain_rows": self.execution_fixture["chain_rows"],
            "friction": scenario["friction"],
            "scenario": self.execution_fixture["scenarios"]["single_leg_fill"],
        }
        first = build_execution_snapshot("NVDA", self.execution_fixture["as_of_time"], **kwargs)
        second = build_execution_snapshot("NVDA", self.execution_fixture["as_of_time"], **kwargs)
        self.assertEqual(first["execution_replay_hash"], second["execution_replay_hash"])

    def test_options_ledger_entry_and_settlement(self) -> None:
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        fill = {
            "call_put": "call",
            "strike": 130.0,
            "expiry": "2026-08-15",
            "side": "long",
            "fill_price": 1.85,
            "quantity": 1,
            "multiplier": 100.0,
            "fill_id": "fill-1",
        }
        ledger = apply_option_fill(ledger, fill=fill)
        self.assertEqual(len(ledger["option_positions"]), 1)
        self.assertLess(ledger["cash"], 100_000.0)

    def test_cross_lane_execution_evidence(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = build_strategy_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        execution = build_execution_snapshot(
            "NVDA",
            self.execution_fixture["as_of_time"],
            strategy_snapshot=strategy,
            chain_rows=self.execution_fixture["chain_rows"],
            friction=scenario["friction"],
            scenario=self.execution_fixture["scenarios"]["single_leg_fill"],
        )
        payload = {
            "available": False,
            "symbol": "NVDA",
            "strategy_snapshot": strategy,
            "execution_snapshot": execution,
        }
        _, evidence = build_cross_lane_snapshot_from_options(payload)
        signals = {row["signal"] for row in evidence}
        self.assertIn("OPTIONS_EXECUTION_SIMULATED", signals)

    def test_load_execution_fixture(self) -> None:
        loaded = load_execution_fixture("NVDA")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["symbol"], "NVDA")

    def test_build_options_order_intent(self) -> None:
        candidate = {
            "template": "long_call_atm",
            "legs": [
                {
                    "call_put": "call",
                    "strike": 130.0,
                    "expiry": "2026-08-15",
                    "side": "long",
                    "quantity": 1,
                    "entry_premium": 1.825,
                    "multiplier": 100.0,
                }
            ],
        }
        intent = build_options_order_intent(
            candidate,
            self.execution_fixture["as_of_time"],
            symbol="NVDA",
        )
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent["symbol"], "NVDA")
        self.assertEqual(len(intent["legs"]), 1)

    def test_run_options_lifecycle_with_assignment(self) -> None:
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        short_put_fill = {
            "call_put": "put",
            "strike": 125.0,
            "expiry": "2026-08-15",
            "side": "short",
            "fill_price": 1.45,
            "quantity": 1,
            "multiplier": 100.0,
            "fill_id": "fill-short-put",
        }
        ledger = apply_option_fill(ledger, fill=short_put_fill)
        lifecycle = run_options_lifecycle(
            {"ledger": ledger},
            self.execution_fixture["scenarios"]["short_put_assignment"],
        )
        self.assertTrue(lifecycle["available"])
        event_types = {event["event_type"] for event in lifecycle["lifecycle_events"]}
        self.assertIn("ASSIGNMENT", event_types)


if __name__ == "__main__":
    unittest.main()
