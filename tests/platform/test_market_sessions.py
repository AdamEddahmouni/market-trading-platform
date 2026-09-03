"""Tests for US equity session labels."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_sessions import us_equity_session_label  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
