"""Tests for US equity session labels."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_sessions import us_equity_screener_session, us_equity_session_label  # noqa: E402

ET = ZoneInfo("America/New_York")


class MarketSessionTests(unittest.TestCase):
    def test_regular_session_midday(self) -> None:
        at = datetime(2026, 8, 24, 12, 0, tzinfo=ET)
        self.assertEqual(us_equity_session_label(at), "REGULAR")

    def test_premarket_and_after_hours(self) -> None:
        pre = datetime(2026, 8, 24, 8, 0, tzinfo=ET)
        after = datetime(2026, 8, 24, 17, 30, tzinfo=ET)
        self.assertEqual(us_equity_session_label(pre), "PREMARKET")
        self.assertEqual(us_equity_session_label(after), "AFTER_HOURS")

    def test_weekend_is_closed(self) -> None:
        saturday = datetime(2026, 8, 22, 12, 0, tzinfo=ET)
        self.assertEqual(us_equity_session_label(saturday), "CLOSED")

    def test_screener_names_the_overnight_session(self) -> None:
        # 2026-10-01 is a Thursday.
        self.assertEqual(us_equity_screener_session(datetime(2026, 10, 1, 2, 26, tzinfo=ET)), "OVERNIGHT")
        self.assertEqual(us_equity_session_label(datetime(2026, 10, 1, 2, 26, tzinfo=ET)), "CLOSED")
        self.assertEqual(us_equity_screener_session(datetime(2026, 9, 30, 21, 0, tzinfo=ET)), "OVERNIGHT")
        self.assertEqual(us_equity_screener_session(datetime(2026, 10, 4, 20, 30, tzinfo=ET)), "OVERNIGHT")  # Sunday
        self.assertEqual(us_equity_screener_session(datetime(2026, 10, 2, 21, 0, tzinfo=ET)), "CLOSED")  # Friday night
        self.assertEqual(us_equity_screener_session(datetime(2026, 10, 3, 2, 0, tzinfo=ET)), "CLOSED")  # Saturday
        self.assertEqual(us_equity_screener_session(datetime(2026, 10, 1, 12, 0, tzinfo=ET)), "REGULAR")


if __name__ == "__main__":
    unittest.main()
