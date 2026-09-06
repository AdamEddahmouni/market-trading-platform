"""Tests for Options O5 signed flow."""

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
from market_platform_foundation.options import (  # noqa: E402
    aggregate_signed_flow,
    build_flow_snapshot,
    classify_signed_flow,
)
from market_platform_foundation.options import flow as options_flow  # noqa: E402

SIGNED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_signed_flow_slice.json"
)


class OptionsO5Tests(unittest.TestCase):
    def test_ambiguous_flow_direction_uncertain(self) -> None:
        result = classify_signed_flow({"direction_label": "ambiguous"})
        self.assertFalse(result["flow_confirmed"])
        self.assertIn(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value, result["quality_flags"])

    def test_signed_flow_snapshot_buy_dominant(self) -> None:
        payload = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
        activities = payload["activities"]
        snapshot = build_flow_snapshot(activities)
        self.assertTrue(snapshot.get("available"))
        self.assertTrue(snapshot.get("signed_flow_available"))
        self.assertEqual(snapshot.get("dominant_direction"), "buy_initiated")
        self.assertTrue(snapshot.get("greeks_flow_available"))
        self.assertTrue(snapshot["aggregate"]["greeks_flow_available"])
        self.assertIsInstance(snapshot["aggregate"]["net_delta_flow"], float)
        self.assertNotIn("universal_score", snapshot)
        self.assertEqual(snapshot.get("flow_version"), "options_signed_flow_v3")

    def test_default_spot_vol_rate_constants_removed(self) -> None:
        self.assertFalse(hasattr(options_flow, "DEFAULT_SPOT"))
        self.assertFalse(hasattr(options_flow, "DEFAULT_VOL"))
        self.assertFalse(hasattr(options_flow, "DEFAULT_RATE"))

    def test_missing_underlying_fails_greeks_closed(self) -> None:
        aggregate = aggregate_signed_flow(
            [
                {
                    "flow_side": "buy",
                    "open_close": "open",
                    "option_type": "call",
                    "strike": 130.0,
                    "size": 100,
                    "bid": 1.80,
                    "ask": 1.85,
                }
            ]
        )
        self.assertFalse(aggregate["greeks_flow_available"])
        self.assertEqual(aggregate["reason"], "UNDERLYING_PRICE_ASSUMPTION_MISSING")
        self.assertIsNone(aggregate["net_delta_flow"])
        self.assertIsNone(aggregate["net_gamma_flow"])
        self.assertIsNone(aggregate["net_vega_flow"])
        self.assertEqual(aggregate["buy_initiated_volume"], 100)
        self.assertEqual(aggregate["confirmed_trade_count"], 1)

    def test_spot_only_fails_greeks_for_missing_vol_or_rate(self) -> None:
        aggregate = aggregate_signed_flow(
            [
                {
                    "flow_side": "buy",
                    "open_close": "open",
                    "option_type": "call",
                    "strike": 130.0,
                    "size": 100,
                    "underlying_price": 128.0,
                }
            ]
        )
        self.assertFalse(aggregate["greeks_flow_available"])
        self.assertEqual(aggregate["reason"], "BSM_VOL_OR_RATE_ASSUMPTION_MISSING")
        self.assertIsNone(aggregate["net_delta_flow"])
        self.assertEqual(aggregate["buy_initiated_volume"], 100)

    def test_inferred_and_explicit_spot_enable_greeks(self) -> None:
        row = {
            "flow_side": "buy",
            "open_close": "open",
            "option_type": "call",
            "strike": 130.0,
            "size": 100,
            "underlying_price": 128.0,
            "provider_iv": 0.42,
            "rate": 0.04,
        }
        inferred = aggregate_signed_flow([row])
        explicit = aggregate_signed_flow(
            [{k: v for k, v in row.items() if k != "underlying_price"}],
            spot=128.0,
        )
        self.assertTrue(inferred["greeks_flow_available"])
        self.assertTrue(explicit["greeks_flow_available"])
        self.assertAlmostEqual(inferred["net_delta_flow"], explicit["net_delta_flow"], places=4)
        self.assertIsInstance(inferred["net_delta_flow"], float)
        self.assertNotAlmostEqual(inferred["net_delta_flow"], 0.0, places=4)

    def test_cross_lane_signed_flow_evidence(self) -> None:
        payload = json.loads(SIGNED_FIXTURE.read_text(encoding="utf-8"))
        options_payload = {
            "available": True,
            "activities": payload["activities"],
            "signed_flow_snapshot": build_flow_snapshot(payload["activities"]),
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(options_payload)
        assert snapshot is not None
        self.assertTrue(snapshot["options_signed_flow_available"])
        signals = {row["signal"] for row in evidence}
        self.assertIn("OPTION_FLOW_DIRECTION", signals)

    def test_cross_lane_no_signed_flow_without_flow_side(self) -> None:
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
            "signed_flow_snapshot": build_flow_snapshot(
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
        snapshot, _ = build_cross_lane_snapshot_from_options(options_payload)
        assert snapshot is not None
        self.assertFalse(snapshot["options_signed_flow_available"])


if __name__ == "__main__":
    unittest.main()
