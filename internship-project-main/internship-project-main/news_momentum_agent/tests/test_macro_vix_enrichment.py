"""Tests for macro calendar, VIX enrichment, and expectancy reporting."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.macro_calendar import (  # noqa: E402
    catalyst_features_for_day,
    enrich_rows_with_calendar,
)
from evaluation.pattern_miner import annotate_buckets, mine_buckets, row_r_multiple  # noqa: E402
from evaluation.vix_history import enrich_rows_with_vix  # noqa: E402


class MacroCalendarTests(unittest.TestCase):
    def test_fomc_decision_day_flagged(self) -> None:
        feats = catalyst_features_for_day(date(2026, 1, 28))
        self.assertTrue(feats["is_scheduled_catalyst_day"])
        self.assertIn("fomc", feats["catalyst_kinds"])

    def test_ordinary_day_not_flagged(self) -> None:
        feats = catalyst_features_for_day(date(2026, 2, 3))
        self.assertFalse(feats["is_scheduled_catalyst_day"])
        self.assertIsNotNone(feats["hours_until_next_catalyst"])

    def test_enrich_rows(self) -> None:
        rows = enrich_rows_with_calendar(
            [
                {"session_date": "2026-01-28", "outcome": "win"},
                {"session_date": "2026-02-03", "outcome": "loss"},
            ]
        )
        self.assertTrue(rows[0]["is_scheduled_catalyst_day"])
        self.assertFalse(rows[1]["is_scheduled_catalyst_day"])


class VixEnrichTests(unittest.TestCase):
    def test_enrich_from_dict(self) -> None:
        vix = {
            date(2026, 1, 20): {"vix_level": 18.5, "vix_change_intraday": 2.0},
        }
        rows = enrich_rows_with_vix([{"session_date": "2026-01-20"}], vix)
        self.assertEqual(rows[0]["vix_level"], 18.5)
        ann = annotate_buckets(rows[0])
        self.assertEqual(ann["vix_level_band"], "15-20")
        self.assertEqual(ann["vix_change_band"], "flat_pm5")


class ExpectancyTests(unittest.TestCase):
    def test_r_multiple_from_pnl(self) -> None:
        self.assertAlmostEqual(row_r_multiple({"pnl_pct": 0.40}), 0.40 / 0.30, places=4)
        self.assertAlmostEqual(row_r_multiple({"pnl_pct": -0.30}), -1.0, places=4)

    def test_mine_buckets_includes_expectancy(self) -> None:
        rows = []
        for i in range(40):
            rows.append(
                {
                    "session_date": f"2026-01-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-01-{(i % 28) + 1:02d}T20:00:00+00:00",
                    "outcome": "win",
                    "pnl_pct": 0.40,
                    "would_be_side": "call",
                    "confidence_pct": 40,
                    "options_score": 70,
                    "lean_pct": 65,
                    "decision": "BUY",
                    "lean": "BUY",
                    "n_dir": 2,
                    "is_scheduled_catalyst_day": False,
                    "vix_level": 16.0,
                    "vix_change_intraday": 1.0,
                }
            )
        for i in range(40):
            rows.append(
                {
                    "session_date": f"2026-02-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-02-{(i % 28) + 1:02d}T20:00:00+00:00",
                    "outcome": "loss",
                    "pnl_pct": -0.30,
                    "would_be_side": "put",
                    "confidence_pct": 75,
                    "options_score": 30,
                    "lean_pct": 40,
                    "decision": "SELL",
                    "lean": "SELL",
                    "n_dir": 1,
                    "is_scheduled_catalyst_day": True,
                    "vix_level": 28.0,
                    "vix_change_intraday": 6.0,
                }
            )
        patterns = mine_buckets(rows, min_n=30)
        self.assertTrue(patterns)
        for p in patterns:
            self.assertIn("avg_r_multiple", p)
            self.assertIn("expectancy_pnl_pct", p)
            self.assertIsNotNone(p["avg_r_multiple"])


if __name__ == "__main__":
    unittest.main()
