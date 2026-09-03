"""Cboe exchange intraday cumulative statistics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import (  # noqa: E402
    OptionsFeatureLayer,
    OptionsStatisticFamily,
)
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.pit import statistic_as_of  # noqa: E402
from market_platform_foundation.cboe_options.quality import CboeOptionsQualityFlag  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, intraday_html, load_json


class CboeIntradayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = load_json("intraday_exchange_stats.json")
        self.capture = parse_intraday_statistics_html(
            intraday_html(self.payload),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            trade_date=self.payload["tradeDate"],
        )

    def test_timezone_is_america_chicago(self) -> None:
        self.assertEqual(self.capture.timezone, "America/Chicago")
        for obs in self.capture.cumulative:
            self.assertEqual(obs.timezone, "America/Chicago")

    def test_buckets_are_cumulative_not_interval(self) -> None:
        self.assertGreaterEqual(len(self.capture.cumulative), 4)
        for obs in self.capture.cumulative:
            self.assertEqual(obs.statistic_family, OptionsStatisticFamily.INTRADAY_CUMULATIVE)
            self.assertEqual(obs.feature_layer, OptionsFeatureLayer.RAW)

    def test_interval_derivation_is_labeled_deterministic_derived(self) -> None:
        self.assertGreater(len(self.capture.intervals), 0)
        for interval in self.capture.intervals:
            self.assertEqual(interval.feature_layer, OptionsFeatureLayer.DETERMINISTIC_DERIVED)
            self.assertFalse(interval.predictive)

    def test_future_bucket_not_visible_at_earlier_decision(self) -> None:
        bucket_1030 = next(
            obs for obs in self.capture.cumulative if obs.bucket_end.endswith("10:30:00-05:00")
        )
        hidden = statistic_as_of(
            self.capture.cumulative,
            decision_time="2026-08-19T10:29:00-05:00",
            bucket_start=bucket_1030.bucket_start,
        )
        self.assertIsNone(hidden)

    def test_bucket_visible_after_availability(self) -> None:
        bucket_1030 = next(
            obs for obs in self.capture.cumulative if obs.bucket_end.endswith("10:30:00-05:00")
        )
        visible = statistic_as_of(
            self.capture.cumulative,
            decision_time="2026-08-19T10:31:30-05:00",
            bucket_start=bucket_1030.bucket_start,
        )
        self.assertIsNotNone(visible)

    def test_nonmonotonic_cumulative_series_is_flagged(self) -> None:
        flagged = [
            obs
            for obs in self.capture.cumulative
            if CboeOptionsQualityFlag.CUMULATIVE_SERIES_NONMONOTONIC.value in obs.quality_flags
        ]
        self.assertGreaterEqual(len(flagged), 1)
        for interval in self.capture.intervals:
            for value in (interval.call_value, interval.put_value, interval.total_value):
                if value is not None:
                    self.assertGreaterEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
