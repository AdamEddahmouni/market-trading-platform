"""Tests for Options O6 dealer positioning."""

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
from market_platform_foundation.options.dealer import (  # noqa: E402
    DEALER_METHOD,
    aggregate_dealer_exposure,
    build_dealer_snapshot,
    estimate_contract_dealer_greeks,
)

BIYA_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "biya_options_slice.json"


class OptionsO6Tests(unittest.TestCase):
    def test_fail_closed_without_open_interest(self) -> None:
        result = estimate_contract_dealer_greeks(
            {
                "option_type": "call",
                "strike": 4.0,
                "expiry": "2026-08-15",
                "event_time": "2026-07-21T20:30:00.000000000Z",
                "bid": 0.35,
                "ask": 0.38,
                "open_interest": 0,
            }
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "OPEN_INTEREST_MISSING")

    def test_dealer_gamma_sign_convention(self) -> None:
        result = estimate_contract_dealer_greeks(
            {
                "option_type": "call",
                "strike": 4.0,
                "expiry": "2026-08-15",
                "event_time": "2026-07-21T20:30:00.000000000Z",
                "bid": 0.35,
                "ask": 0.38,
                "open_interest": 100,
                "underlying_price": 4.25,
            }
        )
        self.assertTrue(result["available"])
        self.assertLess(result["estimated_dealer_gamma"], 0)
        self.assertEqual(result["method"], DEALER_METHOD)

    def test_biya_fixture_aggregation(self) -> None:
        payload = json.loads(BIYA_FIXTURE.read_text(encoding="utf-8"))
        snapshot = build_dealer_snapshot(
            payload["activities"],
            as_of_time="2026-07-21T20:30:00.000000000Z",
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["method"], DEALER_METHOD)
        self.assertEqual(snapshot["confidence"], "LOW")
        self.assertIn(snapshot["gamma_regime"], {"negative_gamma", "positive_gamma", "neutral"})
        self.assertGreater(snapshot["oi_backed_contract_count"], 0)
        self.assertIn("hedging_pressure_estimate", snapshot)

    def test_aggregate_fail_closed_empty(self) -> None:
        snapshot = aggregate_dealer_exposure([])
        self.assertFalse(snapshot["available"])
        self.assertIn(OptionQualityFlag.DEALER_POSITION_UNKNOWN.value, snapshot["quality_flags"])

    def test_cross_lane_gamma_evidence_for_biya(self) -> None:
        payload = json.loads(BIYA_FIXTURE.read_text(encoding="utf-8"))
        dealer_snapshot = build_dealer_snapshot(payload["activities"])
        options_payload = {
            "available": True,
            "activities": payload["activities"],
            "dealer_snapshot": dealer_snapshot,
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(options_payload)
        assert snapshot is not None
        self.assertTrue(snapshot["options_dealer_position_available"])
        signals = {row["signal"] for row in evidence}
        self.assertIn("OPTIONS_DATA_CONFIDENCE", signals)
        if dealer_snapshot.get("gamma_regime") == "negative_gamma":
            self.assertIn("GAMMA_AMPLIFICATION_POTENTIAL", signals)

    def test_cross_lane_no_dealer_without_oi(self) -> None:
        options_payload = {
            "available": True,
            "activities": [
                {
                    "option_type": "call",
                    "volume_oi_ratio": 3.0,
                    "volume_ratio": 2.0,
                    "direction_label": "ambiguous",
                    "confirmation_score": 80,
                }
            ],
            "dealer_snapshot": build_dealer_snapshot(
                [
                    {
                        "option_type": "call",
                        "volume_oi_ratio": 3.0,
                        "volume_ratio": 2.0,
                        "direction_label": "ambiguous",
                        "confirmation_score": 80,
                    }
                ]
            ),
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(options_payload)
        assert snapshot is not None
        self.assertFalse(snapshot["options_dealer_position_available"])
        signals = {row["signal"] for row in evidence}
        self.assertNotIn("GAMMA_AMPLIFICATION_POTENTIAL", signals)


if __name__ == "__main__":
    unittest.main()
