"""Prospective capture, canonical NWS normalization, and source health."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.reference import ReferenceKind
from market_platform_foundation.weather.contracts import WeatherReferenceType, WeatherVariable
from market_platform_foundation.weather.health import capability_report, source_health
from market_platform_foundation.weather.normalize import normalize_nws_forecast
from market_platform_foundation.weather.nws import parse_nws_forecast, parse_nws_point_mapping
from market_platform_foundation.weather.store import WeatherStore
from market_platform_foundation.weather.sync import WeatherSync, WeatherSyncCheckpoint

FIXTURES = ROOT / "tests" / "fixtures" / "weather"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _json(name: str) -> dict:
    return json.loads(_text(name))


class NwsCanonicalNormalizeTests(unittest.TestCase):
    def test_current_periods_become_provider_neutral_forecasts(self) -> None:
        mapping = parse_nws_point_mapping(
            _json("nws_points.json"),
            requested_latitude=39.7456,
            requested_longitude=-97.0892,
            retrieved_time="2026-08-20T18:30:00Z",
        )
        capture = parse_nws_forecast(
            _json("nws_forecast.json"),
            retrieved_time="2026-08-20T18:31:00Z",
            provider_first_observed_time="2026-08-20T18:30:30Z",
        )
        observations = normalize_nws_forecast(
            capture,
            mapping=mapping,
            ingested_time="2026-08-20T18:31:30Z",
            content_hash="nws-point-v1",
        )
        self.assertEqual(len(observations), len(capture.periods))
        first = observations[0]
        self.assertEqual(first.variable, WeatherVariable.TEMPERATURE)
        self.assertEqual(first.forecast_issue_time, capture.forecast_issue_time)
        self.assertEqual(first.forecast_available_time, "2026-08-20T18:30:30Z")
        self.assertEqual(first.target_start, capture.periods[0].start_time)
        self.assertEqual(first.target_end, capture.periods[0].end_time)
        self.assertEqual(first.source_region_id, "TOP:31,80")
        self.assertFalse(first.predictive)

        sync = WeatherSync()
        result = sync.sync_nws_current_forecast(
            capture,
            mapping=mapping,
            ingested_time="2026-08-20T18:31:30Z",
            content_hash="nws-point-v1",
        )
        self.assertEqual(result["observations_added"], len(capture.periods))
        self.assertEqual(len(sync.store.forecasts), len(capture.periods))


class WeatherSyncTests(unittest.TestCase):
    def test_prospective_capture_hashes_and_deduplicates_same_content(self) -> None:
        sync = WeatherSync()
        kwargs = {
            "forecast_available_time": "2025-08-18T15:02:00Z",
            "source_file_id": "2025/08/18/UtilityGas.Heating.txt",
            "source_file_last_modified": "2025-08-18T15:00:00Z",
            "provider_first_observed_time": "2025-08-18T15:02:00Z",
            "retrieved_time": "2025-08-18T15:02:00Z",
            "ingested_time": "2025-08-18T15:03:00Z",
        }
        first = sync.capture_forecast_vintage(
            _text("cpc_forecast_utility_gas_heating.txt"),
            **kwargs,
        )
        second = sync.capture_forecast_vintage(
            _text("cpc_forecast_utility_gas_heating.txt"),
            **kwargs,
        )
        self.assertEqual(first["observations_added"], 14)
        self.assertEqual(second["observations_added"], 0)
        self.assertEqual(len(first["content_hash"]), 64)
        self.assertEqual(sync.checkpoint.latest_forecast_issue, "2025-08-18")

    def test_issue_scan_is_recent_and_keeps_correction_overlap(self) -> None:
        checkpoint = WeatherSyncCheckpoint(
            captured_issue_dates={"2025-08-17", "2025-08-18"},
            latest_forecast_issue="2025-08-18",
            overlap_days=2,
            max_backfill_dates=7,
        )
        sync = WeatherSync(checkpoint=checkpoint)
        selected = sync.issues_to_check(
            [f"2025-08-{day:02d}" for day in range(1, 20)]
        )
        self.assertEqual(selected, ("2025-08-17", "2025-08-18", "2025-08-19"))
        self.assertNotIn("2025-08-01", selected)

    def test_versioned_climatology_is_weather_reference_evidence(self) -> None:
        sync = WeatherSync()
        result = sync.sync_cpc_climatology(
            _text("cpc_climatology_1981_2010.txt"),
            normal_period="1981-2010",
            normal_version="CPC_DAILY_1981_2010_V1",
            weight_vintage="2010",
            available_time="2013-11-06T21:46:00Z",
        )
        self.assertGreater(result["references_added"], 0)
        reference = sync.store.references[0]
        self.assertEqual(reference.reference_type, WeatherReferenceType.CLIMATOLOGY)
        records = sync.store.bitemporal.versions(
            ReferenceKind.WEATHER_REFERENCE,
            sync.store.reference_entity_key(reference),
        )
        self.assertEqual(len(records), 1)


class WeatherHealthTests(unittest.TestCase):
    def test_component_health_is_not_collapsed_to_one_boolean(self) -> None:
        health = source_health(store=WeatherStore(), live=False)
        for key in (
            "NWS_API_REACHABLE",
            "POINT_MAPPING_HEALTH",
            "CPC_REALIZED_DEGREE_DAYS",
            "CPC_7DAY_FORECAST",
            "CPC_FORECAST_ARCHIVE",
            "CPC_CLIMATOLOGY",
            "NDFD_ARCHIVE_REACHABLE",
            "NDFD_DECODE_CAPABILITY",
            "CPC_610_OUTLOOK",
            "CPC_814_OUTLOOK",
        ):
            self.assertIn(key, health)
        self.assertEqual(health["NDFD_DECODE_CAPABILITY"], "DEFERRED")

    def test_capability_report_is_credential_free_and_records_deferrals(self) -> None:
        report = capability_report(live=False, store=WeatherStore())
        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["source_family"], "noaa_nws_cpc")
        self.assertEqual(report["ndfd_archive"]["decode_capability"], "ARCHIVE_AVAILABLE_DECODE_DEFERRED")
        self.assertEqual(report["medium_range"]["implementation"], "CHARACTERIZED_PROSPECTIVE_DEFERRED")
        self.assertEqual(report["credential_access"]["cdo_live_validation"], "DEFERRED_TOKEN_UNAVAILABLE")
        self.assertNotIn("api_key", serialized.lower())
        self.assertNotIn("token_value", serialized.lower())


if __name__ == "__main__":
    unittest.main()
