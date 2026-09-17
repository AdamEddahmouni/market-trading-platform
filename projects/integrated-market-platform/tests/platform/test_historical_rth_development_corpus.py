"""Lane B: historical RTH development corpus builder tests."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    MoomooOpendHistoricalMarketDataProvider,
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
            self.assertEqual(result.quality["incomplete_final_bar_count"], 1)

    def test_dedupe_empty_time_key_increments_malformed_exclusion(self) -> None:
        kept, dups, empty = _dedupe_raw_rows(
            (
                {"time_key": ""},
                {"time_key": "2026-09-15 09:30:00", "open": 1, "high": 1, "low": 1, "close": 1},
            )
        )
        self.assertEqual(empty, 1)
        self.assertEqual(dups, 0)
        self.assertEqual(len(kept), 1)

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


class HistoricalRthCliGovernanceTests(unittest.TestCase):
    def test_build_cli_prints_governance_lines(self) -> None:
        from tools.historical_data.build_cli import main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                [
                    "--provider",
                    "fixture",
                    "--fixture-path",
                    str(FIXTURE),
                    "--instrument",
                    "AAPL",
                    "--start",
                    SESSION_DAY,
                    "--end",
                    SESSION_DAY,
                ]
            )
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("AUTHORITY: HISTORICAL_DEVELOPMENT", output)
        self.assertIn("PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED", output)
        self.assertIn("CALIBRATION_STATE_CHANGED: NO", output)
        self.assertIn("FTEP_STATE_CHANGED: NO", output)


class MoomooHistoricalProviderTests(unittest.TestCase):
    def test_status_provider_unverified_when_opend_unavailable(self) -> None:
        provider = MoomooOpendHistoricalMarketDataProvider(repository_root=ROOT)
        with mock.patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.opend_endpoint",
            return_value=("127.0.0.1", 11111),
        ), mock.patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.opend_is_loopback",
            return_value=True,
        ), mock.patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.opend_reachable",
            return_value=False,
        ):
            status = provider.status()
        self.assertFalse(status.verified)
        self.assertIn("PROVIDER_UNVERIFIED", str(status.reason_code))


if __name__ == "__main__":
    unittest.main()
