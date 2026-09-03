"""Tests for Options O7 event volatility."""

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
from market_platform_foundation.options.event_vol import (  # noqa: E402
    EVENT_VOL_METHOD,
    build_event_vol_snapshot,
    classify_event_state,
    estimate_implied_event_move,
    estimate_iv_crush,
    load_earnings_event_fixture,
)
from market_platform_foundation.options.vrp import vrp_research_snapshot  # noqa: E402

EARNINGS_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_earnings_event_slice.json"


class OptionsO7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(EARNINGS_FIXTURE.read_text(encoding="utf-8"))

    def test_fail_closed_without_earnings_date(self) -> None:
        snapshot = build_event_vol_snapshot("NVDA", "2026-08-19T20:30:00.000000000Z")
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "UNAVAILABLE")
        self.assertEqual(snapshot["event_state"], "NO_EVENT")
        self.assertIn(OptionQualityFlag.EARNINGS_DATE_UNKNOWN.value, snapshot["quality_flags"])

    def test_state_machine_transitions(self) -> None:
        event_time = self.fixture["earnings_event_time"]
        scenarios = self.fixture["scenarios"]
        for key, scenario in scenarios.items():
            state = classify_event_state(scenario["as_of_time"], event_time)
            self.assertEqual(
                state,
                scenario["expected_event_state"],
                msg=f"scenario {key}",
            )

    def test_implied_event_move_from_straddle(self) -> None:
        result = estimate_implied_event_move(
            self.fixture["pre_event_chain"],
            event_expiry=self.fixture["event_expiry"],
        )
        self.assertTrue(result["available"])
        self.assertGreaterEqual(
            result["implied_event_move"],
            self.fixture["expected"]["min_implied_event_move_pct"],
        )
        self.assertEqual(result["method"], EVENT_VOL_METHOD)

    def test_iv_crush_empirical_baseline(self) -> None:
        implied = estimate_implied_event_move(
            self.fixture["pre_event_chain"],
            event_expiry=self.fixture["event_expiry"],
        )
        crush = estimate_iv_crush(
            implied.get("pre_iv"),
            self.fixture["empirical_crush_history"],
            event_state="EVENT_IMMINENT",
        )
        self.assertTrue(crush["available"])
        self.assertEqual(crush["status"], self.fixture["expected"]["status_with_history"])
        self.assertGreaterEqual(
            crush["crush_ratio_median"],
            self.fixture["expected"]["min_crush_ratio_median"],
        )

    def test_exhaustion_boosts_crush_jq6(self) -> None:
        implied = estimate_implied_event_move(
            self.fixture["pre_event_chain"],
            event_expiry=self.fixture["event_expiry"],
        )
        baseline = estimate_iv_crush(
            implied.get("pre_iv"),
            self.fixture["empirical_crush_history"],
            squeeze_context={"available": True, "exhaustion_risk": 30},
            event_state="EVENT_RESOLUTION",
        )
        boosted = estimate_iv_crush(
            implied.get("pre_iv"),
            self.fixture["empirical_crush_history"],
            squeeze_context={"available": True, "exhaustion_risk": 75},
            event_state="EVENT_RESOLUTION",
        )
        self.assertTrue(boosted["exhaustion_boost_applied"])
        self.assertGreater(
            boosted["expected_iv_crush"],
            baseline["expected_iv_crush"],
        )

    def test_build_snapshot_pre_event(self) -> None:
        scenario = self.fixture["scenarios"]["pre_event_imminent"]
        snapshot = build_event_vol_snapshot(
            "NVDA",
            scenario["as_of_time"],
            earnings_event=self.fixture,
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["event_state"], "EVENT_IMMINENT")
        self.assertIsNotNone(snapshot["implied_event_move"])
        self.assertIsNotNone(snapshot["expected_iv_crush"])
        self.assertIn(snapshot["vega_risk"], {"LOW", "MODERATE", "HIGH"})

    def test_build_snapshot_post_event_observed_crush(self) -> None:
        scenario = self.fixture["scenarios"]["post_event_resolution"]
        snapshot = build_event_vol_snapshot(
            "NVDA",
            scenario["as_of_time"],
            earnings_event=self.fixture,
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["event_state"], "EVENT_RESOLUTION")
        self.assertIsNotNone(snapshot["expected_iv_crush"])

    def test_load_earnings_fixture_nvda(self) -> None:
        loaded = load_earnings_event_fixture("NVDA")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["symbol"], "NVDA")

    def test_vrp_uses_event_vol_state(self) -> None:
        snapshot = build_event_vol_snapshot(
            "NVDA",
            self.fixture["scenarios"]["pre_event_imminent"]["as_of_time"],
            earnings_event=self.fixture,
        )
        vrp = vrp_research_snapshot(
            {"vol_forecast_annualized": 0.35, "confidence": "LOW"},
            {
                "available": True,
                "vol_implied_annualized": 0.55,
                "confidence": "LOW",
                "horizons": [{"horizon_days": 25}],
            },
            event_vol_snapshot=snapshot,
        )
        self.assertTrue(vrp["available"])
        self.assertEqual(vrp["event_state"], "EVENT_IMMINENT")

    def test_cross_lane_event_vol_evidence(self) -> None:
        snapshot = build_event_vol_snapshot(
            "NVDA",
            self.fixture["scenarios"]["pre_event_imminent"]["as_of_time"],
            earnings_event=self.fixture,
            physical_forecast={"vol_forecast_annualized": 0.35, "confidence": "LOW"},
        )
        options_payload = {
            "available": True,
            "symbol": "NVDA",
            "activities": [],
            "event_vol_snapshot": snapshot,
            "dealer_snapshot": {"available": False},
        }
        _cross_lane, evidence = build_cross_lane_snapshot_from_options(options_payload)
        signals = {row["signal"] for row in evidence}
        self.assertIn("EVENT_VOL_PREMIUM", signals)
        self.assertIn("IV_CRUSH_RISK", signals)


if __name__ == "__main__":
    unittest.main()
