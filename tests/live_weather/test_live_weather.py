"""Bounded opt-in live NOAA/NWS/CPC weather validation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.weather.cpc import parse_cpc_forecast, parse_cpc_realized
from market_platform_foundation.weather.health import source_health
from market_platform_foundation.weather.live import live_enabled, transport_from_env
from market_platform_foundation.weather.nws import NwsClient

LIVE = live_enabled()
CPC_ROOT = "https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_modified_or_now(transport, fallback: str) -> str:
    raw = transport.last_response_headers.get("last-modified", "")
    if not raw:
        return fallback
    return parsedate_to_datetime(raw).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@unittest.skipUnless(LIVE, "IMP_WEATHER_LIVE=1 required")
class LiveWeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.transport = transport_from_env()
        cls.client = NwsClient(transport=cls.transport)
        cls.mapping = cls.client.lookup_point(
            40.7128,
            -74.0060,
            retrieved_time=_now(),
        )

    def test_nws_user_agent_points_and_mapping_semantics(self) -> None:
        self.assertIn("integrated-market-platform", self.transport.user_agent.lower())
        self.assertTrue(self.mapping.office)
        self.assertGreater(self.mapping.grid_x, 0)
        self.assertGreater(self.mapping.grid_y, 0)
        self.assertTrue(self.mapping.forecast_url.startswith("https://api.weather.gov/"))
        self.assertTrue(self.mapping.revalidate_after > self.mapping.retrieved_time)

    def test_nws_current_forecast_hourly_and_raw_grid_semantics(self) -> None:
        retrieved = _now()
        forecast = self.client.fetch_forecast(self.mapping, retrieved_time=retrieved)
        hourly = self.client.fetch_hourly_forecast(self.mapping, retrieved_time=retrieved)
        grid = self.client.fetch_grid_data(self.mapping, retrieved_time=retrieved)
        self.assertTrue(forecast.periods)
        self.assertTrue(hourly.periods)
        self.assertNotEqual(len(hourly.periods), 0)
        self.assertLess(forecast.horizon_start, forecast.horizon_end)
        self.assertLess(hourly.horizon_start, hourly.horizon_end)
        self.assertIn("temperature", grid.elements)
        self.assertTrue(grid.elements["temperature"].unit)
        self.assertTrue(grid.elements["temperature"].values[0].raw_valid_time)

    def test_nws_station_observation_keeps_latency_clocks(self) -> None:
        stations = self.client.fetch_station_collection(self.mapping)
        features = stations.get("features") or []
        self.assertTrue(features)
        properties = features[0].get("properties") or {}
        station_id = properties.get("stationIdentifier") or str(features[0].get("id", "")).rstrip("/").split("/")[-1]
        self.assertTrue(station_id)
        retrieved = _now()
        observation = self.client.fetch_latest_observation(
            station_id,
            retrieved_time=retrieved,
        )
        self.assertTrue(observation.observation_time)
        self.assertEqual(observation.retrieved_time, retrieved)
        self.assertIn("OBSERVATION_LATENCY_UNCERTAIN", observation.quality_flags)

    def test_cpc_latest_forecast_parses_issue_availability_and_seven_targets(self) -> None:
        url = f"{CPC_ROOT}/daily_forecasts_7day/latest/UtilityGas.Heating.txt"
        retrieved = _now()
        text = self.transport.request_bytes(url, accept="text/plain").decode("utf-8")
        available = _last_modified_or_now(self.transport, retrieved)
        rows = parse_cpc_forecast(
            text,
            forecast_available_time=available,
            source_file_id=url,
            source_file_last_modified=available,
            provider_first_observed_time=retrieved,
            retrieved_time=retrieved,
            ingested_time=retrieved,
        )
        self.assertTrue(rows)
        self.assertEqual(len({row.target_start for row in rows}), 7)
        self.assertEqual({row.weighting_method.value for row in rows}, {"UTILITY_GAS_CUSTOMERS"})
        self.assertTrue(all(row.forecast_issue_time != row.target_end for row in rows))
        self.assertTrue(all(row.forecast_available_time == available for row in rows))

    def test_cpc_realized_degree_days_have_separate_availability(self) -> None:
        url = f"{CPC_ROOT}/daily_data/latest/Population.Heating.txt"
        retrieved = _now()
        text = self.transport.request_bytes(url, accept="text/plain").decode("utf-8")
        available = _last_modified_or_now(self.transport, retrieved)
        rows = parse_cpc_realized(
            text,
            available_time=available,
            source_file_id=url,
            provider_first_observed_time=retrieved,
            retrieved_time=retrieved,
            ingested_time=retrieved,
        )
        self.assertTrue(rows)
        latest_period = max(row.period_start for row in rows)
        self.assertLessEqual(latest_period[:10], retrieved[:10])
        self.assertTrue(all(row.available_time == available for row in rows))
        self.assertTrue(all(not hasattr(row, "forecast_issue_time") for row in rows))

    def test_cpc_archived_vintage_is_date_addressable_and_parseable(self) -> None:
        url = f"{CPC_ROOT}/daily_forecasts_7day/2014/01/01/UtilityGas.Heating.txt"
        retrieved = _now()
        text = self.transport.request_bytes(url, accept="text/plain").decode("utf-8")
        available = _last_modified_or_now(self.transport, retrieved)
        rows = parse_cpc_forecast(
            text,
            forecast_available_time=available,
            source_file_id=url,
            source_file_last_modified=available,
            provider_first_observed_time=retrieved,
            retrieved_time=retrieved,
            ingested_time=retrieved,
        )
        self.assertTrue(rows)
        self.assertEqual(rows[0].forecast_issue_time[:10], "2014-01-01")
        self.assertEqual(len({row.target_start for row in rows}), 7)

    def test_ndfd_catalog_is_reachable_without_bulk_or_decode(self) -> None:
        url = "https://www.ncei.noaa.gov/thredds/catalog/model/ndfd.html"
        body = self.transport.request_bytes(url, accept="application/xml, text/xml")
        self.assertLess(len(body), 2_000_000)
        self.assertIn(b"NDFD", body.upper())
        health = source_health(live=True)
        self.assertEqual(health["NDFD_DECODE_CAPABILITY"], "DEFERRED")


if __name__ == "__main__":
    unittest.main()
