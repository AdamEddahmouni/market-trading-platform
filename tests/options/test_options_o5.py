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
    build_flow_snapshot,
    classify_signed_flow,
)

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
        self.assertNotIn("universal_score", snapshot)

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
