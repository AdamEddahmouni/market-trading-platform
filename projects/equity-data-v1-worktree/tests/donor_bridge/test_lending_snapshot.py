"""Tests for IBKR lending snapshot bridge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.lending_adapter import (  # noqa: E402
    build_lending_cross_lane_snapshot,
    build_lending_snapshot_from_donor_detail,
    build_lending_snapshot_from_ibkr,
    reset_lending_snapshot_cache,
)


class LendingSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_lending_snapshot_cache()

    def test_ibkr_snapshot_fail_closed_without_data(self) -> None:
        snapshot = build_lending_snapshot_from_ibkr(
            symbol="GME",
            fee_rate=None,
            shares_available=None,
            observation_time="2026-07-21T20:00:00Z",
            available_time="2026-07-21T20:00:00Z",
        )
        self.assertIsNone(snapshot)

    def test_donor_detail_maps_to_cross_lane(self) -> None:
        detail = {
            "symbol": "GME",
            "fields": {
                "borrow_fee": {"status": "KNOWN", "value": 12.5},
                "borrow_availability": {"status": "KNOWN", "value": 50000},
            },
            "snapshot_at": "2026-07-21T20:00:00Z",
        }
        lending = build_lending_snapshot_from_donor_detail(detail)
        self.assertIsNotNone(lending)
        cross_lane = build_lending_cross_lane_snapshot(detail)
        self.assertTrue(cross_lane.get("lending_available"))
        self.assertEqual(cross_lane.get("lending_fee_rate"), 12.5)
        self.assertEqual(cross_lane.get("lending_shares_available"), 50000)

    def test_velocity_from_prior_snapshot(self) -> None:
        detail_v1 = {
            "symbol": "GME",
            "fields": {"borrow_fee": {"status": "KNOWN", "value": 8.0}},
            "snapshot_at": "2026-07-21T19:00:00Z",
        }
        build_lending_snapshot_from_donor_detail(detail_v1)
        detail_v2 = {
            "symbol": "GME",
            "fields": {"borrow_fee": {"status": "KNOWN", "value": 12.0}},
            "snapshot_at": "2026-07-21T20:00:00Z",
        }
        lending = build_lending_snapshot_from_donor_detail(detail_v2)
        self.assertIsNotNone(lending)
        assert lending is not None
        self.assertEqual(lending.get("borrow_utilization_velocity"), 4.0)


if __name__ == "__main__":
    unittest.main()
