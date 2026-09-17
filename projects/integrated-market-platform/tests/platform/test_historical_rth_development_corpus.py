"""Lane B: historical RTH development corpus builder tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.market_data.historical_development.rth_session import (  # noqa: E402
    bar_start_is_rth,
    expected_rth_minute_keys,
    filter_raw_rows_rth,
    iter_us_equity_session_dates,
)
from market_platform_foundation.paper.calibration.dual_corpus.discovery import (  # noqa: E402
    is_historical_development_storage_path,
    validate_item9_prospective_receipt_output_dir,
)
from market_platform_foundation.paper.calibration.dual_corpus.historical_manifest import (  # noqa: E402
    validate_historical_development_dataset_manifest,
)


FIXTURE = ROOT / "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
SESSION_DAY = "2026-09-15"


class HistoricalRthSessionTests(unittest.TestCase):
    def test_iter_skips_weekend(self) -> None:
        dates = iter_us_equity_session_dates("2026-09-11", "2026-09-13")
        self.assertEqual(dates, ("2026-09-11",))

    def test_rth_filter_and_expected_minutes(self) -> None:
        rows = load_fixture_rows_from_json(FIXTURE)[SESSION_DAY]
        kept, excluded = filter_raw_rows_rth(rows)
        self.assertGreater(excluded, 0)
        self.assertTrue(all(bar_start_is_rth(str(r["time_key"])) for r in kept))
        self.assertEqual(len(expected_rth_minute_keys(SESSION_DAY)), 390)

    def test_pagination_fixture_provider(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        pages = provider.fetch_session_day("canonical:EQUITY:XNAS:AAPL", SESSION_DAY)
        self.assertEqual(len(pages), 1)
        self.assertGreater(len(pages[0].raw_rows), 0)


class HistoricalRthBuildTests(unittest.TestCase):
    def test_fixture_build_manifest_and_fingerprints(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "artifacts" / "historical-rth-development"
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=SESSION_DAY,
                end_date=SESSION_DAY,
                artifact_root=artifact_root,
                fixture_only=True,
            )
            self.assertTrue(result.ok)
            gate = validate_historical_development_dataset_manifest(result.manifest)
            self.assertTrue(gate["ok"])
            self.assertTrue(result.normalized_fingerprint)
            self.assertEqual(result.manifest["duplicate_row_count"], 1)
            self.assertGreater(result.manifest["excluded_row_count"], 0)
            self.assertIn("missing_intervals", result.manifest)
            self.assertTrue(result.quality["forward_fill_applied"] is False)
            self.assertTrue(result.manifest["dataset_fingerprint"])

    def test_item9_discovery_refuses_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist_root = Path(tmp) / "artifacts" / "historical-rth-development" / "runs" / "x"
            hist_root.mkdir(parents=True)
            self.assertTrue(is_historical_development_storage_path(hist_root))
            gate = validate_item9_prospective_receipt_output_dir(hist_root)
            self.assertFalse(gate["ok"])

    def test_missing_intervals_reported(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=SESSION_DAY,
                end_date=SESSION_DAY,
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            self.assertGreater(len(result.manifest["missing_intervals"]), 0)
            self.assertGreater(result.quality["missing_intervals"][0]["missing_minute_count"], 0)

    def test_ordering_dedup_timezone_malformed(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            result = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=SESSION_DAY,
                end_date=SESSION_DAY,
                artifact_root=Path(tmp) / "artifacts" / "historical-rth-development",
                fixture_only=True,
            )
            bars = json.loads(
                (result.paths.normalized_dir / "AAPL_normalized.json").read_text(encoding="utf-8")
            )
            times = [int(b["available_time"]) for b in bars]
            self.assertEqual(times, sorted(times))
            self.assertEqual(result.manifest["row_count"], 2)


if __name__ == "__main__":
    unittest.main()
