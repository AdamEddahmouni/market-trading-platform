import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.session import (
    build_session_list,
    decision_bucket,
    grid_targets_ns,
    outside_session_window,
    session_bounds_ns,
)

NS = 1_000_000_000


class BucketTests(unittest.TestCase):
    def test_floor_semantics(self):
        self.assertEqual(decision_bucket(0), 0)
        self.assertEqual(decision_bucket(59 * NS), 0)
        self.assertEqual(decision_bucket(60 * NS), 1)


class SessionBoundsTests(unittest.TestCase):
    def test_bounds_are_rth_et(self):
        et = ZoneInfo("America/New_York")
        start_ns, end_ns = session_bounds_ns("2026-08-24")  # Monday, EDT
        s = datetime.fromtimestamp(start_ns / 1e9, tz=et)
        e = datetime.fromtimestamp(end_ns / 1e9, tz=et)
        self.assertEqual((s.hour, s.minute), (9, 30))
        self.assertEqual((e.hour, e.minute), (16, 0))
        self.assertEqual(s.date().isoformat(), "2026-08-24")


class SessionListTests(unittest.TestCase):
    def test_skips_weekends_holidays_early_closes(self):
        days = build_session_list(
            "2026-09-04", 3,
            holidays=frozenset({"2026-09-07"}),      # Labor Day Monday
            early_closes=frozenset({"2026-09-04"}),  # excluded entirely
        )
        self.assertEqual(days, ["2026-09-08", "2026-09-09", "2026-09-10"])


class GridTests(unittest.TestCase):
    def test_targets_step_and_respect_tolerance(self):
        targets = grid_targets_ns("2026-08-24", horizon_seconds=1800, tolerance_seconds=300)
        _, end_ns = session_bounds_ns("2026-08-24")
        self.assertGreater(len(targets), 10)
        self.assertEqual(targets[1] - targets[0], 1800 * NS)
        for t in targets:
            self.assertLessEqual(t + 1800 * NS + 300 * NS, end_ns)

    def test_outside_session_window_guard(self):
        _, end_ns = session_bounds_ns("2026-08-24")
        self.assertFalse(outside_session_window(end_ns - 3600 * NS, 1800 * NS, end_ns))
        self.assertTrue(outside_session_window(end_ns - 1200 * NS, 1800 * NS, end_ns))


if __name__ == "__main__":
    unittest.main()
