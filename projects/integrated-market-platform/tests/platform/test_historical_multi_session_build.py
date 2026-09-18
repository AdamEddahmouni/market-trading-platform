"""Lane C: bounded multi-session historical development dataset builds."""

from __future__ import annotations

import json
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
from market_platform_foundation.market_data.historical_development.rth_session import (  # noqa: E402
    RTH_MINUTES_EARLY_CLOSE_SESSION,
    RTH_MINUTES_FULL_SESSION,
    iter_us_equity_session_dates,
    sort_raw_rows_by_time_key,
)
from market_platform_foundation.paper.calibration.dual_corpus.historical_manifest import (  # noqa: E402
    validate_historical_development_dataset_manifest,
)


def _synthetic_minute_rows(session_date: str, minute_count: int) -> list[dict]:
    base = datetime.strptime(f"{session_date} 09:30:00", "%Y-%m-%d %H:%M:%S")
    rows: list[dict] = []
    for i in range(minute_count):
        stamp = base + timedelta(minutes=i)
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


class HistoricalMultiSessionBuildTests(unittest.TestCase):
    def test_three_session_week_span_skips_weekend(self) -> None:
        start = "2026-09-11"
        end = "2026-09-15"
        session_dates = iter_us_equity_session_dates(start, end)
        self.assertEqual(session_dates, ("2026-09-11", "2026-09-14", "2026-09-15"))
        rows_by_day = {
            day: _synthetic_minute_rows(day, RTH_MINUTES_FULL_SESSION) for day in session_dates
        }
        provider = FixtureHistoricalMarketDataProvider(rows_by_day)
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=start,
                end_date=end,
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(len(result.manifest["interval"]["session_dates"]), 3)
            self.assertEqual(len(result.quality["session_summaries"]), 3)
            self.assertEqual(result.quality["missing_rows"], 0)
            self.assertEqual(result.quality["raw_time_key_ordering_violations"], 0)
            self.assertEqual(result.manifest["row_count"], 3 * RTH_MINUTES_FULL_SESSION)
            gate = validate_historical_development_dataset_manifest(result.manifest)
            self.assertTrue(gate["ok"])
            for day in session_dates:
                raw_path = result.paths.raw_dir / f"AAPL_{day}.json"
                self.assertTrue(raw_path.is_file())
            bars = json.loads(
                (result.paths.normalized_dir / "AAPL_normalized.json").read_text(encoding="utf-8")
            )
            times = [int(b["available_time"]) for b in bars]
            self.assertEqual(times, sorted(times))

    def test_holiday_and_early_close_mixed_range(self) -> None:
        start = "2026-09-04"
        end = "2026-09-07"
        early_day = "2026-09-04"
        holiday = "2026-09-07"
        session_dates = iter_us_equity_session_dates(
            start,
            end,
            holidays=frozenset({holiday}),
            early_closes=frozenset({early_day}),
        )
        self.assertEqual(session_dates, (early_day,))
        rows_by_day = {early_day: _synthetic_minute_rows(early_day, RTH_MINUTES_EARLY_CLOSE_SESSION)}
        provider = FixtureHistoricalMarketDataProvider(rows_by_day)
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=start,
                end_date=end,
                holidays=frozenset({holiday}),
                early_closes=frozenset({early_day}),
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            self.assertTrue(result.ok)
            summary = result.quality["session_summaries"][0]
            self.assertEqual(summary["session_kind"], "EARLY_CLOSE")
            self.assertEqual(summary["expected_minute_count"], RTH_MINUTES_EARLY_CLOSE_SESSION)

    def test_manifest_fingerprint_matches_validator(self) -> None:
        start = "2026-09-14"
        end = "2026-09-15"
        session_dates = iter_us_equity_session_dates(start, end)
        rows_by_day = {
            day: _synthetic_minute_rows(day, RTH_MINUTES_FULL_SESSION) for day in session_dates
        }
        provider = FixtureHistoricalMarketDataProvider(rows_by_day)
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=start,
                end_date=end,
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            self.assertTrue(result.ok)
            self.assertTrue(result.manifest["dataset_fingerprint"])
            self.assertTrue(result.normalized_fingerprint)
            self.assertTrue(result.quality["quality_fingerprint"])
            gate = validate_historical_development_dataset_manifest(result.manifest)
            self.assertTrue(gate["ok"])

    def test_sort_raw_rows_orders_cross_session(self) -> None:
        rows = [
            {"time_key": "2026-09-15 09:31:00", "open": 1, "high": 1, "low": 1, "close": 1},
            {"time_key": "2026-09-14 15:59:00", "open": 1, "high": 1, "low": 1, "close": 1},
            {"time_key": "2026-09-15 09:30:00", "open": 1, "high": 1, "low": 1, "close": 1},
        ]
        ordered = sort_raw_rows_by_time_key(rows)
        keys = [row["time_key"] for row in ordered]
        self.assertEqual(
            keys,
            ["2026-09-14 15:59:00", "2026-09-15 09:30:00", "2026-09-15 09:31:00"],
        )


if __name__ == "__main__":
    unittest.main()
