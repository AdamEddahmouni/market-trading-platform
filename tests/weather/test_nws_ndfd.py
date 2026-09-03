"""Offline NWS current/prospective and NDFD archive contract tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = ROOT / "tests" / "fixtures" / "weather"

from market_platform_foundation.weather.capture import build_weather_capture_envelope
from market_platform_foundation.weather.live import load_nws_user_agent
from market_platform_foundation.weather.ndfd import (
    NDFD_DECODE_STATUS,
    characterize_ndfd_metadata,
    recognize_grib2,
)
from market_platform_foundation.weather.nws import (
    NwsClient,
    mapping_needs_revalidation,
    parse_nws_forecast,
    parse_nws_grid,
    parse_nws_observation,
    parse_nws_point_mapping,
)
from market_platform_foundation.weather.transport import (
    DEFAULT_NWS_USER_AGENT,
    WeatherTransport,
    WeatherTransportError,
)


def _load(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class NwsUserAgentTests(unittest.TestCase):
    def test_safe_default_and_environment_override(self) -> None:
        self.assertNotIn("python-urllib", DEFAULT_NWS_USER_AGENT.lower())
        with patch.dict(os.environ, {"IMP_NWS_USER_AGENT": "imp-weather-test/9.1"}):
            self.assertEqual(load_nws_user_agent(), "imp-weather-test/9.1")

    def test_transport_rejects_blank_user_agent(self) -> None:
        with self.assertRaisesRegex(ValueError, "NWS_USER_AGENT_REQUIRED"):
            WeatherTransport(user_agent="")


class WeatherTransportTests(unittest.TestCase):
    def test_retry_is_bounded_and_honors_retry_after(self) -> None:
        attempts = 0
        sleeps: list[float] = []

        def requester(url: str, headers: dict[str, str], timeout: float):
            nonlocal attempts
            attempts += 1
            raise HTTPError(url, 429, "rate limited", {"Retry-After": "0.25"}, None)

        transport = WeatherTransport(
            requester=requester,
            max_retries=2,
            min_interval_seconds=0,
            sleeper=sleeps.append,
        )
        with self.assertRaisesRegex(WeatherTransportError, "NWS_HTTP_429"):
            transport.request_json("https://api.weather.gov/points/39,-97")
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [0.25, 0.25])

    def test_client_uses_links_returned_by_points(self) -> None:
        forecast_payload = _load("nws_forecast.json")
        forecast_payload.pop("@id", None)
        payloads = {
            "https://api.weather.gov/points/39.7456,-97.0892": _load("nws_points.json"),
            "https://api.weather.gov/gridpoints/TOP/31,80/forecast": forecast_payload,
        }

        class FixtureTransport:
            def request_json(self, url: str):
                return payloads[url]

        client = NwsClient(transport=FixtureTransport())
        mapping = client.lookup_point(
            39.7456,
            -97.0892,
            retrieved_time="2026-08-20T18:30:00Z",
        )
        forecast = client.fetch_forecast(mapping, retrieved_time="2026-08-20T18:31:00Z")
        self.assertEqual(forecast.provider_url, mapping.forecast_url)


class NwsPointMappingTests(unittest.TestCase):
    def test_mapping_identity_and_periodic_revalidation(self) -> None:
        mapping = parse_nws_point_mapping(
            _load("nws_points.json"),
            requested_latitude=39.7456,
            requested_longitude=-97.0892,
            retrieved_time="2026-08-20T18:30:00Z",
            revalidate_after_days=7,
        )
        self.assertEqual(mapping.office, "TOP")
        self.assertEqual(mapping.grid_x, 31)
        self.assertEqual(mapping.grid_y, 80)
        self.assertEqual(mapping.mapping_identity, "TOP:31,80")
        self.assertFalse(mapping_needs_revalidation(mapping, "2026-08-27T18:29:59Z"))
        self.assertTrue(mapping_needs_revalidation(mapping, "2026-08-27T18:30:00Z"))

    def test_changed_office_or_grid_is_observable(self) -> None:
        original = parse_nws_point_mapping(
            _load("nws_points.json"),
            requested_latitude=39.7456,
            requested_longitude=-97.0892,
            retrieved_time="2026-08-20T18:30:00Z",
        )
        remapped_payload = _load("nws_points.json")
        remapped_payload["properties"].update({"gridId": "EAX", "gridX": 52, "gridY": 38})
        remapped = parse_nws_point_mapping(
            remapped_payload,
            requested_latitude=39.7456,
            requested_longitude=-97.0892,
            retrieved_time="2026-08-28T18:30:00Z",
            previous=original,
        )
        self.assertTrue(remapped.mapping_changed)
        self.assertEqual(remapped.previous_mapping_identity, "TOP:31,80")
        self.assertEqual(remapped.mapping_identity, "EAX:52,38")


class NwsForecastTests(unittest.TestCase):
    def test_forecast_keeps_actual_periods_and_horizon(self) -> None:
        forecast = parse_nws_forecast(
            _load("nws_forecast.json"),
            retrieved_time="2026-08-20T18:30:00Z",
        )
        hourly = parse_nws_forecast(
            _load("nws_hourly.json"),
            retrieved_time="2026-08-20T18:30:00Z",
            forecast_kind="HOURLY",
        )
        self.assertEqual(len(forecast.periods), 2)
        self.assertEqual(forecast.horizon_start, "2026-08-20T13:00:00-05:00")
        self.assertEqual(forecast.horizon_end, "2026-08-21T06:00:00-05:00")
        self.assertEqual(len(hourly.periods), 3)
        self.assertEqual(hourly.horizon_end, "2026-08-20T16:00:00-05:00")
        self.assertNotEqual(len(hourly.periods), 168)

    def test_grid_preserves_interval_and_provider_units(self) -> None:
        grid = parse_nws_grid(
            _load("nws_grid.json"),
            retrieved_time="2026-08-20T18:30:00Z",
        )
        temperature = grid.elements["temperature"]
        self.assertEqual(temperature.unit, "wmoUnit:degC")
        self.assertEqual(temperature.values[0].duration, "PT3H")
        self.assertEqual(temperature.values[0].start_time, "2026-08-20T18:00:00+00:00")
        self.assertEqual(temperature.values[0].value, 32.2)
        self.assertEqual(grid.horizon_end, "2026-08-21T06:00:00+00:00")

    def test_observation_time_is_not_retrieval_time(self) -> None:
        observation = parse_nws_observation(
            _load("nws_observation.json"),
            retrieved_time="2026-08-20T18:37:00Z",
            provider_first_observed_time="2026-08-20T18:36:00Z",
        )
        self.assertEqual(observation.observation_time, "2026-08-20T18:15:00+00:00")
        self.assertEqual(observation.provider_first_observed_time, "2026-08-20T18:36:00Z")
        self.assertEqual(observation.retrieved_time, "2026-08-20T18:37:00Z")
        self.assertEqual(observation.measurements["temperature"].quality_control, "V")


class WeatherCaptureTests(unittest.TestCase):
    def test_envelope_hashes_sanitized_payload_and_request(self) -> None:
        fake_secret = "NOT_A_REAL_TOKEN_123"
        payload = _load("nws_forecast.json")
        payload["requestEcho"] = {"token": fake_secret, "safe": "kept"}
        payload["diagnosticUrl"] = f"https://example.test/data?token={fake_secret}"
        envelope = build_weather_capture_envelope(
            source="nws",
            endpoint_family="forecast",
            request_url=f"https://api.weather.gov/example?token={fake_secret}&format=json",
            response_payload=payload,
            retrieved_time="2026-08-20T18:30:00Z",
            provider_first_observed_time="2026-08-20T18:30:00Z",
            response_headers={"ETag": "abc", "Set-Cookie": fake_secret},
        )
        serialized = json.dumps(envelope, sort_keys=True)
        self.assertNotIn(fake_secret, serialized)
        self.assertEqual(len(envelope["response_hash"]), 64)
        self.assertEqual(envelope["response_headers"], {"etag": "abc"})


class NdfdTests(unittest.TestCase):
    def test_metadata_characterization_defers_decode(self) -> None:
        result = characterize_ndfd_metadata(_load("ndfd_catalog.json"))
        self.assertTrue(result["archive_available"])
        self.assertEqual(result["period_of_record_start"], "2004-06-06")
        self.assertEqual(result["cloud_access_start"], "2020-04-16")
        self.assertEqual(result["decode_status"], NDFD_DECODE_STATUS)
        self.assertFalse(result["bulk_download_performed"])
        self.assertEqual(result["format"], "GRIB2")
        self.assertIn(
            {"kind": "NODD_S3", "url": "s3://noaa-ndfd-pds/wmo/"},
            result["access_methods"],
        )

    def test_grib_marker_probe_is_bounded_and_does_not_decode(self) -> None:
        grib2 = b"GRIB\x00\x00\x00\x02" + b"\x00" * 8
        self.assertTrue(recognize_grib2(grib2 + b"fixture"))
        self.assertTrue(recognize_grib2(b"WMO-PREAMBLE\r\r\n" + grib2))
        self.assertFalse(recognize_grib2(b"GRIB\x00\x00\x00\x01" + b"\x00" * 8))
        self.assertFalse(recognize_grib2(b"not-a-grib-file"))
        with self.assertRaisesRegex(ValueError, "NDFD_PROBE_TOO_LARGE"):
            recognize_grib2(b"GRIB" + b"\x00" * 16385)


if __name__ == "__main__":
    unittest.main()
