"""Weather forecast-vintage and realization PIT invariants."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.reference import ReferenceKind
from market_platform_foundation.weather.contracts import (
    WeatherAvailabilityPrecision,
    WeatherForecastObservation,
    WeatherHistoryClass,
    WeatherRealizationObservation,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from market_platform_foundation.weather.pit import (
    forecast_as_of,
    forecast_error_as_of,
    forecast_revision,
    realization_as_of,
)
from market_platform_foundation.weather.store import WeatherStore


TARGET_START = "2026-08-21T00:00:00Z"
TARGET_END = "2026-08-22T00:00:00Z"


def _forecast(
    *,
    issue: str,
    available: str,
    value: float,
    content_hash: str,
    ingested: str | None = None,
) -> WeatherForecastObservation:
    return WeatherForecastObservation(
        canonical_weather_indicator="CPC_UTILITY_GAS_HDD65",
        source="noaa_cpc",
        source_product="UtilityGas.Heating",
        source_product_version="cpc.degree_days.v1",
        region_type=WeatherRegionType.CENSUS_DIVISION,
        region_id="5",
        region_name="SOUTH_ATLANTIC",
        weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        weighting_version="ACS_2010",
        variable=WeatherVariable.HDD65,
        forecast_issue_time=issue,
        forecast_available_time=available,
        availability_precision=WeatherAvailabilityPrecision.FIRST_OBSERVED,
        target_start=TARGET_START,
        target_end=TARGET_END,
        lead_hours=72,
        lead_days=3,
        value=value,
        unit="degree_day_fahrenheit",
        source_file_id=f"{issue}:UtilityGas.Heating",
        provider_first_observed_time=available,
        retrieved_time=available,
        ingested_time=ingested or available,
        content_hash=content_hash,
        history_class=WeatherHistoryClass.ARCHIVED_FORECAST_VINTAGE,
    )


def _realization(*, available: str, value: float) -> WeatherRealizationObservation:
    return WeatherRealizationObservation(
        canonical_weather_indicator="CPC_UTILITY_GAS_HDD65",
        source="noaa_cpc",
        source_product="UtilityGas.Heating",
        source_product_version="cpc.degree_days.v1",
        region_type=WeatherRegionType.CENSUS_DIVISION,
        region_id="5",
        region_name="SOUTH_ATLANTIC",
        weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        weighting_version="ACS_2010",
        variable=WeatherVariable.HDD65,
        period_start=TARGET_START,
        period_end=TARGET_END,
        observation_time=TARGET_END,
        available_time=available,
        availability_precision=WeatherAvailabilityPrecision.FIRST_OBSERVED,
        raw_value="30",
        value=value,
        unit="degree_day_fahrenheit",
        retrieved_time=available,
        ingested_time=available,
        content_hash="actual-v1",
    )


class WeatherForecastPitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = WeatherStore()
        self.monday = _forecast(
            issue="2026-08-17T00:00:00Z",
            available="2026-08-17T15:00:00Z",
            value=20.0,
            content_hash="mon-v1",
        )
        self.tuesday = _forecast(
            issue="2026-08-18T00:00:00Z",
            available="2026-08-18T15:00:00Z",
            value=24.0,
            content_hash="tue-v1",
        )
        self.wednesday = _forecast(
            issue="2026-08-19T00:00:00Z",
            available="2026-08-19T15:00:00Z",
            value=29.0,
            content_hash="wed-v1",
        )
        self.store.add_forecasts((self.monday, self.tuesday, self.wednesday))

    def _query(self, decision_time: str):
        return forecast_as_of(
            self.store.forecasts,
            target_time="2026-08-21T12:00:00Z",
            decision_time=decision_time,
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )

    def test_issue_time_does_not_make_forecast_visible(self) -> None:
        self.assertIsNone(self._query("2026-08-17T10:00:00Z"))
        self.assertEqual(self._query("2026-08-17T16:00:00Z").value, 20.0)

    def test_future_target_is_visible_after_source_availability(self) -> None:
        selected = self._query("2026-08-17T16:00:00Z")
        self.assertIsNotNone(selected)
        self.assertGreater(selected.target_start, "2026-08-17T16:00:00Z")

    def test_latest_available_distinct_issue_is_selected(self) -> None:
        self.assertEqual(self._query("2026-08-18T14:59:59Z").value, 20.0)
        self.assertEqual(self._query("2026-08-18T15:00:00Z").value, 24.0)
        self.assertEqual(self._query("2026-08-19T15:00:00Z").value, 29.0)

    def test_revision_uses_distinct_issue_vintages(self) -> None:
        revision = forecast_revision(
            self.store.forecasts,
            target_time="2026-08-21T12:00:00Z",
            decision_time="2026-08-18T15:00:00Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        self.assertEqual(revision.latest_value, 24.0)
        self.assertEqual(revision.previous_value, 20.0)
        self.assertEqual(revision.delta, 4.0)
        self.assertFalse(revision.predictive)

    def test_same_issue_correction_versions_only_that_vintage(self) -> None:
        correction = _forecast(
            issue=self.monday.forecast_issue_time,
            available="2026-08-20T12:00:00Z",
            value=21.0,
            content_hash="mon-v2",
        )
        self.store.add_forecast(correction)

        before = self.store.forecast_vintage_as_of(
            issue_time=self.monday.forecast_issue_time,
            target_time="2026-08-21T12:00:00Z",
            decision_time="2026-08-20T11:59:59Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        after = self.store.forecast_vintage_as_of(
            issue_time=self.monday.forecast_issue_time,
            target_time="2026-08-21T12:00:00Z",
            decision_time="2026-08-20T12:00:00Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        self.assertEqual(before.value, 20.0)
        self.assertEqual(after.value, 21.0)
        self.assertEqual(self._query("2026-08-20T12:00:00Z").forecast_issue_time, self.wednesday.forecast_issue_time)
        records = self.store.bitemporal.versions(ReferenceKind.WEATHER_FORECAST, self.store.forecast_entity_key(self.monday))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].known_to, correction.forecast_available_time)


class WeatherRealizationPitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forecast = _forecast(
            issue="2026-08-17T00:00:00Z",
            available="2026-08-17T15:00:00Z",
            value=20.0,
            content_hash="mon-v1",
        )
        self.actual = _realization(available="2026-08-22T15:00:00Z", value=30.0)

    def test_realization_is_hidden_before_its_availability(self) -> None:
        self.assertIsNone(
            realization_as_of(
                [self.actual],
                target_time="2026-08-21T12:00:00Z",
                decision_time="2026-08-19T18:00:00Z",
                region_type=WeatherRegionType.CENSUS_DIVISION,
                region_id="5",
                variable=WeatherVariable.HDD65,
                weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
            )
        )

    def test_forecast_error_appears_only_after_realization(self) -> None:
        before = forecast_error_as_of(
            [self.forecast],
            [self.actual],
            target_time="2026-08-21T12:00:00Z",
            decision_time="2026-08-21T18:00:00Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        after = forecast_error_as_of(
            [self.forecast],
            [self.actual],
            target_time="2026-08-21T12:00:00Z",
            decision_time="2026-08-22T15:00:00Z",
            region_type=WeatherRegionType.CENSUS_DIVISION,
            region_id="5",
            variable=WeatherVariable.HDD65,
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        self.assertIsNone(before)
        self.assertEqual(after.signed_error, 10.0)
        self.assertEqual(after.available_time, self.actual.available_time)
        self.assertFalse(after.predictive)


if __name__ == "__main__":
    unittest.main()
