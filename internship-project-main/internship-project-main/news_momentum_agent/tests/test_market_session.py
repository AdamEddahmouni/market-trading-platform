"""Tests for equity-options session gating."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from agent.market_session import (
    is_equity_rth,
    is_options_entry_allowed,
    is_options_session_open,
)


ET = ZoneInfo("America/New_York")


class MarketSessionTests(unittest.TestCase):
    def test_rth_open_midday(self) -> None:
        self.assertTrue(is_equity_rth(datetime(2026, 7, 16, 12, 0, tzinfo=ET)))

    def test_rth_closed_after_four(self) -> None:
        self.assertFalse(is_equity_rth(datetime(2026, 7, 16, 16, 5, tzinfo=ET)))

    def test_rth_closed_weekend(self) -> None:
        self.assertFalse(is_equity_rth(datetime(2026, 7, 18, 12, 0, tzinfo=ET)))

    def test_entry_blocked_after_eod_flatten(self) -> None:
        settings = {
            "execution": {"market_hours_only": True},
            "trading": {"options_exits": {"eod_flatten_et": "15:45"}},
        }
        self.assertTrue(
            is_options_session_open(settings, datetime(2026, 7, 16, 15, 50, tzinfo=ET))
        )
        self.assertFalse(
            is_options_entry_allowed(settings, datetime(2026, 7, 16, 15, 50, tzinfo=ET))
        )

    def test_session_closed_blocks_entries(self) -> None:
        settings = {
            "execution": {"market_hours_only": True},
            "trading": {"options_exits": {"eod_flatten_et": "15:45"}},
        }
        closed = datetime(2026, 7, 16, 17, 30, tzinfo=ET)
        self.assertFalse(is_options_session_open(settings, closed))
        self.assertFalse(is_options_entry_allowed(settings, closed))


if __name__ == "__main__":
    unittest.main()
