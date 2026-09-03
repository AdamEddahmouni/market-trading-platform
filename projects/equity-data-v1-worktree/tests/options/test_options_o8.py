"""Tests for Options O8 strategy optimizer and payoff engine."""

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
from market_platform_foundation.options.payoff import (  # noqa: E402
    OptionLeg,
    PAYOFF_METHOD,
    expected_pnl_under_physical_p,
    payoff_at_spot,
)
from market_platform_foundation.options.strategy import (  # noqa: E402
    STRATEGY_METHOD,
    build_candidate_legs,
    build_strategy_snapshot,
    load_strategy_optimizer_fixture,
    select_atm_contracts,
)

STRATEGY_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_strategy_optimizer_slice.json"


class OptionsO8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(STRATEGY_FIXTURE.read_text(encoding="utf-8"))

    def test_payoff_at_spot_long_call(self) -> None:
        leg = OptionLeg(
            call_put="call",
            strike=130.0,
            expiry="2026-08-15",
            side="long",
            entry_premium=1.825,
            multiplier=100.0,
        )
        itm_pnl = payoff_at_spot(135.0, [leg])
        self.assertGreater(itm_pnl, 0)
        otm_pnl = payoff_at_spot(125.0, [leg])
        self.assertLess(otm_pnl, 0)

    def test_expected_pnl_from_physical_quantiles(self) -> None:
        leg = OptionLeg(
            call_put="call",
            strike=130.0,
            expiry="2026-08-15",
            side="long",
            entry_premium=1.825,
            multiplier=100.0,
        )
        result = expected_pnl_under_physical_p(
            self.fixture["physical_forecast"],
            [leg],
            spot=128.0,
            friction=self.fixture["scenarios"]["bullish_directional"]["friction"],
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["method"], PAYOFF_METHOD)
        self.assertNotIn("universal_score", result)
        self.assertIsNotNone(result["net_expected_pnl"])

    def test_fail_closed_without_executable_edge(self) -> None:
        snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
        )
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["outcome"], "NO_CLEAR_EDGE")
        self.assertIn(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value, snapshot["quality_flags"])

    def test_bullish_directional_ranks_candidates(self) -> None:
        scenario = self.fixture["scenarios"]["bullish_directional"]
        snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
            friction=scenario["friction"],
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["status"], scenario["expected_outcome"])
        self.assertEqual(snapshot["outcome"], "RANKED")
        self.assertIsNotNone(snapshot["best_candidate"])
        self.assertNotIn("universal_score", snapshot)
        templates = {row["template"] for row in snapshot["ranked_candidates"]}
        for expected in scenario["expected_templates"]:
            self.assertIn(expected, templates)

    def test_flat_scenario_no_clear_edge(self) -> None:
        scenario = self.fixture["scenarios"]["flat_no_edge"]
        snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
            friction=scenario["friction"],
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["outcome"], "NO_CLEAR_EDGE")
        self.assertEqual(snapshot["reason"], scenario["expected_reason"])
        self.assertIn(OptionQualityFlag.STRATEGY_NO_EDGE.value, snapshot["quality_flags"])

    def test_atm_selection_deterministic(self) -> None:
        selection = select_atm_contracts(self.fixture["chain_rows"])
        self.assertTrue(selection["available"])
        self.assertEqual(selection["atm_call"]["strike"], self.fixture["expected"]["atm_strike"])
        self.assertEqual(selection["atm_put"]["strike"], self.fixture["expected"]["atm_strike"])

    def test_build_candidate_legs_long_straddle(self) -> None:
        built = build_candidate_legs("long_straddle", self.fixture["chain_rows"])
        self.assertTrue(built["available"])
        self.assertEqual(len(built["legs"]), 2)

    def test_cross_lane_strategy_evidence(self) -> None:
        scenario = self.fixture["scenarios"]["bullish_directional"]
        strategy_snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
            friction=scenario["friction"],
        )
        payload = {
            "symbol": "NVDA",
            "available": True,
            "strategy_snapshot": strategy_snapshot,
            "activities": [],
        }
        _snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        signals = {row["signal"] for row in evidence}
        self.assertIn("STRATEGY_OPPORTUNITY_RANKED", signals)

    def test_cross_lane_no_clear_edge_evidence(self) -> None:
        scenario = self.fixture["scenarios"]["flat_no_edge"]
        strategy_snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
            friction=scenario["friction"],
        )
        payload = {
            "symbol": "NVDA",
            "available": True,
            "strategy_snapshot": strategy_snapshot,
            "activities": [],
        }
        _snapshot, evidence = build_cross_lane_snapshot_from_options(payload)
        signals = {row["signal"] for row in evidence}
        self.assertIn("NO_CLEAR_EDGE", signals)

    def test_fixture_loader(self) -> None:
        loaded = load_strategy_optimizer_fixture("NVDA")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["symbol"], "NVDA")
        self.assertEqual(loaded["expected"]["payoff_method"], PAYOFF_METHOD)

    def test_strategy_method_tag(self) -> None:
        scenario = self.fixture["scenarios"]["vol_rich"]
        snapshot = build_strategy_snapshot(
            "NVDA",
            self.fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.fixture["physical_forecast"],
            chain_rows=self.fixture["chain_rows"],
            friction=scenario["friction"],
        )
        self.assertEqual(snapshot["method"], STRATEGY_METHOD)
        self.assertIn("replay_hash", snapshot)


if __name__ == "__main__":
    unittest.main()
