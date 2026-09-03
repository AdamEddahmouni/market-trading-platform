"""Deterministic weather-demand state and climatology compatibility tests."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.weather.contracts import (
    WeatherRegionType,
    WeatherWeightingMethod,
)
from market_platform_foundation.weather.cpc import parse_cpc_climatology, parse_cpc_forecast
from market_platform_foundation.weather.derived import (
    build_weather_demand_state,
    forecast_vs_normal,
)
from market_platform_foundation.weather.store import WeatherStore

FIXTURES = ROOT / "tests" / "fixtures" / "weather"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class WeatherNormalCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forecast = parse_cpc_forecast(
            _text("cpc_forecast_utility_gas_heating.txt"),
            forecast_available_time="2025-08-18T15:00:00Z",
            weighting_version="2010",
        )[0]
        self.normals = parse_cpc_climatology(
            _text("cpc_climatology_1981_2010.txt"),
            normal_period="1981-2010",
            normal_version="CPC_DAILY_1981_2010_V1",
            weight_vintage="2010",
            available_time="2013-11-06T21:46:00Z",
        )

    def test_compatible_normal_produces_nonpredictive_anomaly(self) -> None:
        anomaly = forecast_vs_normal(
            self.forecast,
            self.normals,
            decision_time="2025-08-18T16:00:00Z",
        )
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.value, 2.0)
        self.assertEqual(anomaly.normal_period, "1981-2010")
        self.assertEqual(anomaly.weighting_version, "2010")
        self.assertFalse(anomaly.predictive)

    def test_future_normal_is_not_visible(self) -> None:
        future_normals = tuple(
            replace(item, available_from="2026-01-01T00:00:00Z") for item in self.normals
        )
        self.assertIsNone(
            forecast_vs_normal(
                self.forecast,
                future_normals,
                decision_time="2025-08-18T16:00:00Z",
            )
        )

    def test_population_normal_cannot_normalize_utility_gas_forecast(self) -> None:
        incompatible = tuple(
            replace(item, weighting_method=WeatherWeightingMethod.POPULATION)
            for item in self.normals
        )
        self.assertIsNone(
            forecast_vs_normal(
                self.forecast,
                incompatible,
                decision_time="2025-08-18T16:00:00Z",
            )
        )


class WeatherDemandStateTests(unittest.TestCase):
    def test_summary_uses_only_latest_available_issue_vintage(self) -> None:
        issue_a = parse_cpc_forecast(
            _text("cpc_forecast_utility_gas_heating.txt"),
            forecast_available_time="2025-08-18T15:00:00Z",
            content_hash="issue-a",
        )
        issue_b = tuple(
            replace(
                item,
                forecast_issue_time="2025-08-19T00:00:00Z",
                forecast_available_time="2025-08-19T15:00:00Z",
                value=(item.value + 1.0) if item.value is not None else None,
                content_hash="issue-b",
            )
            for item in issue_a
        )
        store = WeatherStore()
        store.add_forecasts(issue_a)
        store.add_forecasts(issue_b)

        state = build_weather_demand_state(
            store,
            decision_time="2025-08-19T16:00:00Z",
            region_type=WeatherRegionType.CONUS,
            region_id="CONUS",
        )

        self.assertEqual({item.forecast_issue_time for item in state.forecast_hdd_1_7d}, {"2025-08-19T00:00:00Z"})
        self.assertEqual(state.next_3d_hdd, 5.0)
        self.assertEqual(state.next_7d_hdd, 14.0)
        self.assertEqual(state.utility_gas_hdd_7d, 14.0)
        self.assertEqual(state.latest_forecast_available_time, "2025-08-19T15:00:00Z")
        self.assertIsNotNone(state.forecast_revision_hdd)
        self.assertEqual(state.forecast_revision_hdd.delta, 1.0)
        self.assertFalse(state.predictive)

    def test_missing_day_makes_window_unknown_not_zero(self) -> None:
        observations = parse_cpc_forecast(
            _text("cpc_forecast_utility_gas_heating.txt"),
            forecast_available_time="2025-08-18T15:00:00Z",
        )
        store = WeatherStore()
        store.add_forecasts(observations)
        state = build_weather_demand_state(
            store,
            decision_time="2025-08-18T16:00:00Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="1",
        )
        self.assertIsNone(state.next_3d_hdd)
        self.assertIsNone(state.next_7d_hdd)


if __name__ == "__main__":
    unittest.main()
