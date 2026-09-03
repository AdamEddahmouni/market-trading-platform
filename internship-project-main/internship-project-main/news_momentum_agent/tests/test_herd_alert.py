"""Tests for multi-path HIGH_ALERT herd promotion."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.herd_alert import (  # noqa: E402
    apply_multi_path_high_alert,
    news_catalyst_qualifies,
    relative_volume_percentile_by_index,
    volume_spike_qualifies,
)
from agent.path_a_pipeline_health import format_funnel_line  # noqa: E402


SETTINGS = {
    "herd_alert": {
        "enabled": True,
        "news_score_abs_min": 0.5,
        "news_max_age_hours": 4,
        "volume_rvol_percentile_min": 0.9,
        "volume_rvol_floor": 2.0,
        "volume_abs_pct_change_min": 1.0,
    }
}


class HerdAlertPathTests(unittest.TestCase):
    def test_news_catalyst_threshold(self) -> None:
        self.assertTrue(news_catalyst_qualifies(0.55, settings=SETTINGS))
        self.assertTrue(news_catalyst_qualifies(-0.7, settings=SETTINGS))
        self.assertFalse(news_catalyst_qualifies(0.4, settings=SETTINGS))

    def test_volume_top_decile_promotes(self) -> None:
        # 10 names: only the highest RVol in top decile (>=0.9 percentile).
        watchlist = []
        for i in range(10):
            watchlist.append(
                {
                    "ticker": f"T{i}",
                    "relative_volume": 1.5 + i * 0.5,  # T9 = 6.0
                    "percent_change": 4.0 if i == 9 else 0.2,
                    "social_signal_level": "IGNORE",
                }
            )
        ranks = relative_volume_percentile_by_index(watchlist)
        self.assertAlmostEqual(ranks[9], 1.0)
        self.assertTrue(volume_spike_qualifies(watchlist[9], ranks[9], SETTINGS))
        self.assertFalse(volume_spike_qualifies(watchlist[5], ranks[5], SETTINGS))

        stats = apply_multi_path_high_alert(watchlist, SETTINGS)
        self.assertEqual(watchlist[9]["social_signal_level"], "HIGH_ALERT")
        self.assertIn("volume_spike", watchlist[9]["alert_reason"])
        self.assertEqual(stats["by_path"]["volume_spike"], 1)
        self.assertEqual(watchlist[0]["social_signal_level"], "IGNORE")

    def test_volume_fallback_uses_absolute_volume(self) -> None:
        watchlist = []
        for i in range(10):
            watchlist.append(
                {
                    "ticker": f"V{i}",
                    "relative_volume": None,
                    "average_volume": None,
                    "volume": 1000 * (i + 1),
                    "percent_change": 1.5 if i >= 8 else 0.1,
                    "social_signal_level": "IGNORE",
                }
            )
        stats = apply_multi_path_high_alert(watchlist, SETTINGS)
        # Top decile by absolute volume among names with |pct|>=1.0 → V9 only.
        self.assertEqual(watchlist[9]["social_signal_level"], "HIGH_ALERT")
        self.assertIn("volume_spike", watchlist[9]["alert_reason"])
        self.assertGreaterEqual(stats["by_path"]["volume_spike"], 1)

    def test_stocktwits_preserved_and_or_with_news(self) -> None:
        watchlist = [
            {
                "ticker": "AAA",
                "relative_volume": 1.2,
                "percent_change": 0.5,
                "social_signal_level": "HIGH_ALERT",
            },
            {
                "ticker": "BBB",
                "relative_volume": 1.2,
                "percent_change": 0.5,
                "social_signal_level": "IGNORE",
            },
            {
                "ticker": "CCC",
                "relative_volume": 1.2,
                "percent_change": 0.5,
                "social_signal_level": "WATCH",
            },
        ]
        news = {"BBB": {"score": 0.8, "published_at": "2026-07-30T15:00:00+00:00"}}
        stats = apply_multi_path_high_alert(watchlist, SETTINGS, news_by_ticker=news)
        self.assertEqual(watchlist[0]["social_signal_level"], "HIGH_ALERT")
        self.assertEqual(watchlist[0]["alert_reason"], ["stocktwits"])
        self.assertEqual(watchlist[1]["social_signal_level"], "HIGH_ALERT")
        self.assertEqual(watchlist[1]["alert_reason"], ["news_catalyst"])
        self.assertEqual(watchlist[2]["social_signal_level"], "WATCH")
        self.assertEqual(stats["by_path"]["stocktwits"], 1)
        self.assertEqual(stats["by_path"]["news_catalyst"], 1)

    def test_funnel_line_includes_by_path(self) -> None:
        data = {
            "last_screener": {
                "finviz": {"raw": 100, "after_filters": 40},
                "tagging": {"HIGH_ALERT": 5, "WATCH": 2},
                "herd_alert_by_path": {
                    "stocktwits": 0,
                    "news_catalyst": 3,
                    "volume_spike": 2,
                },
            },
            "last_pipeline": {},
        }
        line = format_funnel_line(data)
        self.assertIn("stocktwits=0", line)
        self.assertIn("news_catalyst=3", line)
        self.assertIn("volume_spike=2", line)


if __name__ == "__main__":
    unittest.main()
