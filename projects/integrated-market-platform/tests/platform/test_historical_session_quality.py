"""Lane D: historical session calendar and quality report hardening."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.builder import (  # noqa: E402
    _dedupe_raw_rows,
)
from market_platform_foundation.market_data.historical_development.quality import (  # noqa: E402
    build_quality_report,
)
from market_platform_foundation.market_data.historical_development.rth_session import (  # noqa: E402
    RTH_MINUTES_EARLY_CLOSE_SESSION,
    RTH_MINUTES_FULL_SESSION,
    UsEquitySessionDayKind,
    bar_start_is_rth,
    classify_us_equity_session_day,
    expected_rth_minute_keys,
    filter_raw_rows_rth,
    iter_us_equity_session_dates,
    ohlc_row_valid,
)


def _synthetic_minute_rows(session_date: str, minute_count: int, start_offset: int = 0) -> list[dict]:
    base = datetime.strptime(f"{session_date} 09:30:00", "%Y-%m-%d %H:%M:%S")
    rows: list[dict] = []
    for i in range(minute_count):
        stamp = base + timedelta(minutes=start_offset + i)
        rows.append(
            {
                "time_key": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
            }
        )
    return rows


class HistoricalSessionCalendarTests(unittest.TestCase):
    def test_regular_session_minute_grid(self) -> None:
        self.assertEqual(len(expected_rth_minute_keys("2026-09-15")), RTH_MINUTES_FULL_SESSION)

    def test_early_close_included_in_session_dates(self) -> None:
        dates = iter_us_equity_session_dates(
            "2026-09-04",
            "2026-09-04",
            early_closes=frozenset({"2026-09-04"}),
        )
        self.assertEqual(dates, ("2026-09-04",))

    def test_holiday_excluded_from_session_dates(self) -> None:
        dates = iter_us_equity_session_dates(
            "2026-09-07",
            "2026-09-07",
            holidays=frozenset({"2026-09-07"}),
        )
        self.assertEqual(dates, ())

    def test_early_close_short_grid_and_afternoon_excluded(self) -> None:
        day = "2026-06-15"
        early = frozenset({day})
        self.assertEqual(
            classify_us_equity_session_day(day, early_closes=early),
            UsEquitySessionDayKind.EARLY_CLOSE,
        )
        keys = expected_rth_minute_keys(day, early_closes=early)
        self.assertEqual(len(keys), RTH_MINUTES_EARLY_CLOSE_SESSION)
        self.assertEqual(keys[-1], f"{day} 12:59:00")
        full_session_row = {"time_key": f"{day} 15:00:00", "open": 1, "high": 1, "low": 1, "close": 1}
        kept, excluded = filter_raw_rows_rth([full_session_row], early_closes=early)
        self.assertEqual(kept, [])
        self.assertEqual(excluded, 1)
        self.assertFalse(bar_start_is_rth(full_session_row["time_key"], early_closes=early))

    def test_early_close_complete_session_not_reported_as_gap(self) -> None:
        day = "2026-06-15"
        early = frozenset({day})
        rows = _synthetic_minute_rows(day, RTH_MINUTES_EARLY_CLOSE_SESSION)
        report = build_quality_report(
            start_date=day,
            end_date=day,
            session_dates=[day],
            raw_rows=rows,
            normalized_bars=rows,
            duplicate_row_count=0,
            excluded_row_count=0,
            malformed_timestamp_count=0,
            outside_session_count=0,
            incomplete_final_bar_count=0,
            provider_gap_pages=0,
            holidays=[],
            early_closes=[day],
            corporate_action_status="PROVIDER_QFQ_NOT_RECONCILED",
            volume_anomaly_count=0,
        )
        self.assertEqual(report["missing_rows"], 0)
        self.assertEqual(report["short_session_count"], 1)
        self.assertEqual(report["quality_status"], "PASS")


class HistoricalQualitySchemaTests(unittest.TestCase):
    def test_quality_report_required_fields(self) -> None:
        day = "2026-09-15"
        rows = _synthetic_minute_rows(day, 5)
        report = build_quality_report(
            start_date=day,
            end_date=day,
            session_dates=[day],
            raw_rows=rows,
            normalized_bars=rows[:3],
            duplicate_row_count=1,
            excluded_row_count=2,
            malformed_timestamp_count=0,
            outside_session_count=1,
            incomplete_final_bar_count=1,
            provider_gap_pages=1,
            holidays=["2026-09-07"],
            early_closes=[],
            corporate_action_status="PROVIDER_QFQ_NOT_RECONCILED",
            volume_anomaly_count=0,
        )
        for key in (
            "requested_sessions",
            "actual_sessions",
            "expected_rows",
            "observed_rows",
            "missing_rows",
            "duplicate_rows",
            "out_of_order_rows",
            "malformed_rows",
            "outside_session_rows",
            "incomplete_rows",
            "invalid_ohlc_rows",
            "volume_anomalies",
            "provider_gap_intervals",
            "short_session_count",
            "holiday_count",
            "quality_status",
        ):
            self.assertIn(key, report)

    def test_invalid_ohlc_and_duplicates_fail_or_warn(self) -> None:
        day = "2026-09-16"
        bad = {"time_key": f"{day} 09:30:00", "open": 10, "high": 9, "low": 11, "close": 10}
        self.assertFalse(ohlc_row_valid(bad))
        kept, dups, _empty = _dedupe_raw_rows(
            (
                {"time_key": f"{day} 09:30:00", "open": 1, "high": 2, "low": 1, "close": 1},
                {"time_key": f"{day} 09:30:00", "open": 1, "high": 2, "low": 1, "close": 1},
            )
        )
        self.assertEqual(dups, 1)
        self.assertEqual(len(kept), 1)
        report = build_quality_report(
            start_date=day,
            end_date=day,
            session_dates=[day],
            raw_rows=[bad],
            normalized_bars=[],
            duplicate_row_count=dups,
            excluded_row_count=1,
            malformed_timestamp_count=0,
            outside_session_count=0,
            incomplete_final_bar_count=1,
            provider_gap_pages=0,
            holidays=[],
            early_closes=[],
            corporate_action_status="PROVIDER_QFQ_NOT_RECONCILED",
            volume_anomaly_count=0,
        )
        self.assertEqual(report["invalid_ohlc_rows"], 1)
        self.assertEqual(report["quality_status"], "FAIL")


class HistoricalEarlyCloseBuildTests(unittest.TestCase):
    def test_fixture_build_early_close_day(self) -> None:
        day = "2026-06-15"
        rows = {day: _synthetic_minute_rows(day, RTH_MINUTES_EARLY_CLOSE_SESSION)}
        provider = FixtureHistoricalMarketDataProvider(rows)
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=day,
                end_date=day,
                early_closes=frozenset({day}),
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.quality["short_session_count"], 1)
            self.assertEqual(result.quality["missing_rows"], 0)
            self.assertEqual(result.quality["expected_rows"], RTH_MINUTES_EARLY_CLOSE_SESSION)


if __name__ == "__main__":
    unittest.main()
