"""Tests for causal state hysteresis."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from squeeze_core.intelligence.hysteresis import apply_hysteresis


class HysteresisTests(unittest.TestCase):
    def test_blocks_downgrade_during_cooldown(self) -> None:
        now = datetime(2026, 8, 18, 20, 0, 0, tzinfo=UTC)
        since = (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        result = apply_hysteresis(
            {
                "state": "VULNERABLE",
                "explanation": {"summary": "Proposed downgrade."},
                "transition": {"trigger": "evidence_deterioration"},
                "quality_flags": [],
            },
            previous_state="IGNITION_WATCH",
            state_since=since,
            now=now,
            cooldown_seconds=120,
        )
        self.assertEqual(result["state"], "IGNITION_WATCH")
        self.assertIn("HYSTERESIS_HOLD", result["quality_flags"])
        self.assertTrue(result["transition"]["hysteresis_applied"])

    def test_allows_upgrade_immediately(self) -> None:
        now = datetime(2026, 8, 18, 20, 0, 0, tzinfo=UTC)
        since = (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        result = apply_hysteresis(
            {"state": "LIVE_CONFIRMATION", "transition": {}, "quality_flags": []},
            previous_state="IGNITION_WATCH",
            state_since=since,
            now=now,
        )
        self.assertEqual(result["state"], "LIVE_CONFIRMATION")


if __name__ == "__main__":
    unittest.main()
