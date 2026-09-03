"""Offline unit tests for scheduler market-hours logic."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scheduler

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

SETTINGS = {
    "scheduler": {
        "timezone": "America/New_York",
        "market_holidays": ["2026-06-19", "2026-12-25"],
    }
}


def _open_at(y, m, d, hh, mm) -> bool:
    return scheduler.is_market_open(SETTINGS, datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(UTC))


class SchedulerTests(unittest.TestCase):
    def test_open_during_regular_hours(self) -> None:
        self.assertTrue(_open_at(2026, 6, 17, 11, 0))  # Wednesday

    def test_closed_before_open_and_after_close(self) -> None:
        self.assertFalse(_open_at(2026, 6, 17, 9, 0))   # pre-market
        self.assertFalse(_open_at(2026, 6, 17, 16, 30))  # after close

    def test_closed_on_weekend(self) -> None:
        self.assertFalse(_open_at(2026, 6, 20, 11, 0))  # Saturday

    def test_closed_on_holiday(self) -> None:
        self.assertFalse(_open_at(2026, 6, 19, 11, 0))   # Juneteenth
        self.assertFalse(_open_at(2026, 12, 25, 11, 0))  # Christmas


if __name__ == "__main__":
    unittest.main()
