"""CPC degree-day parser tests using compact official-format slices."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.weather.contracts import (
    WeatherAvailabilityPrecision,
    WeatherHistoryClass,
    WeatherRegionType,
    WeatherReferenceType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from market_platform_foundation.weather.cpc import (
    parse_cpc_climatology,
    parse_cpc_forecast,
    parse_cpc_realized,
)
from market_platform_foundation.weather.regions import (
    parse_cpc_regions,
    region_identity,
)


FIXTURES = ROOT / "tests" / "fixtures" / "weather"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


FORECAST_METADATA = {
    "forecast_available_time": "2025-08-18T15:00:00Z",
    "source_file_id": "2025/08/18/UtilityGas.Heating.txt",
    "source_file_last_modified": "2025-08-18T15:00:00Z",
    "provider_first_observed_time": "2025-08-18T15:02:00Z",
    "retrieved_time": "2025-08-18T15:03:00Z",
    "ingested_time": "2025-08-18T15:04:00Z",
    "content_hash": "sha256:fixture-utility-gas-heating",
    "provenance_ref": "fixture:cpc:utility-gas-heating:20250818",
}


class CpcForecastParserTests(unittest.TestCase):
    def test_forecast_preserves_issue_availability_and_target_clocks(self) -> None:
        observations = parse_cpc_forecast(
            _fixture("cpc_forecast_utility_gas_heating.txt"),
            **FORECAST_METADATA,
        )
        first = next(obs for obs in observations if obs.region_id == "1")
        self.assertEqual(first.forecast_issue_time, "2025-08-18T00:00:00Z")
        self.assertEqual(first.forecast_available_time, "2025-08-18T15:00:00Z")
        self.assertEqual(first.target_start, "2025-08-18T00:00:00Z")
        self.assertEqual(first.target_end, "2025-08-19T00:00:00Z")
        self.assertNotEqual(first.forecast_issue_time, first.forecast_available_time)
        self.assertNotEqual(first.forecast_available_time[:10], observations[-1].target_start)
        self.assertEqual(first.source_file_id, FORECAST_METADATA["source_file_id"])
        self.assertEqual(first.source_file_last_modified, FORECAST_METADATA["source_file_last_modified"])
        self.assertEqual(first.provider_first_observed_time, FORECAST_METADATA["provider_first_observed_time"])
        self.assertEqual(first.retrieved_time, FORECAST_METADATA["retrieved_time"])
        self.assertEqual(first.ingested_time, FORECAST_METADATA["ingested_time"])
        self.assertEqual(first.content_hash, FORECAST_METADATA["content_hash"])
        self.assertEqual(
            first.availability_precision,
            WeatherAvailabilityPrecision.HTTP_LAST_MODIFIED_PROXY,
        )
        self.assertEqual(first.history_class, WeatherHistoryClass.ARCHIVED_FORECAST_VINTAGE)
        self.assertFalse(first.predictive)

    def test_total_column_is_not_an_independent_observation(self) -> None:
        observations = parse_cpc_forecast(
            _fixture("cpc_forecast_population_heating.txt"),
            **FORECAST_METADATA,
        )
        self.assertEqual(len(observations), 14)
        self.assertFalse(any(obs.target_start.lower() == "total" for obs in observations))

    def test_population_and_utility_gas_are_distinct_series(self) -> None:
        utility = parse_cpc_forecast(
            _fixture("cpc_forecast_utility_gas_heating.txt"),
            **FORECAST_METADATA,
        )
        population = parse_cpc_forecast(
            _fixture("cpc_forecast_population_heating.txt"),
            **FORECAST_METADATA,
        )
        utility_first = next(obs for obs in utility if obs.region_id == "1")
        population_first = next(obs for obs in population if obs.region_id == "1")
        self.assertEqual(utility_first.variable, WeatherVariable.HDD65)
        self.assertEqual(utility_first.region_type, WeatherRegionType.CENSUS_DIVISION)
        self.assertEqual(
            utility_first.weighting_method,
            WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        self.assertEqual(population_first.weighting_method, WeatherWeightingMethod.POPULATION)
        self.assertNotEqual(utility_first.value, population_first.value)

    def test_states_and_conus_keep_distinct_region_types(self) -> None:
        observations = parse_cpc_forecast(
            _fixture("cpc_forecast_states_cooling.txt"),
            **FORECAST_METADATA,
        )
        texas = next(obs for obs in observations if obs.region_id == "TX")
        conus = next(obs for obs in observations if obs.region_id == "CONUS")
        self.assertEqual(texas.variable, WeatherVariable.CDD65)
        self.assertEqual(texas.region_type, WeatherRegionType.STATE)
        self.assertEqual(conus.region_type, WeatherRegionType.CONUS)

    def test_missing_forecast_value_remains_unknown_not_zero(self) -> None:
        observations = parse_cpc_forecast(
            _fixture("cpc_forecast_utility_gas_heating.txt"),
            **FORECAST_METADATA,
        )
        missing = next(
            obs
            for obs in observations
            if obs.region_id == "1" and obs.target_start == "2025-08-20T00:00:00Z"
        )
        self.assertIsNone(missing.value)
        self.assertEqual(missing.raw_value, "M")
        self.assertIn("MISSING_VALUE", missing.quality_flags)


class CpcRealizationAndClimatologyTests(unittest.TestCase):
    def test_realized_data_is_separate_and_has_its_own_availability(self) -> None:
        observations = parse_cpc_realized(
            _fixture("cpc_realized_population_heating.txt"),
            available_time="2025-08-19T08:07:00Z",
            retrieved_time="2025-08-19T08:10:00Z",
            source_file_id="2025/Population.Heating.txt",
            content_hash="sha256:fixture-realized",
        )
        realized = next(obs for obs in observations if obs.region_id == "1")
        self.assertEqual(realized.variable, WeatherVariable.HDD65)
        self.assertEqual(realized.period_start, "2025-08-16T00:00:00Z")
        self.assertEqual(realized.period_end, "2025-08-17T00:00:00Z")
        self.assertEqual(realized.available_time, "2025-08-19T08:07:00Z")
        self.assertFalse(hasattr(realized, "forecast_issue_time"))
        missing = next(
            obs
            for obs in observations
            if obs.region_id == "1" and obs.period_start == "2025-08-18T00:00:00Z"
        )
        self.assertIsNone(missing.value)
        self.assertEqual(missing.raw_value, "M")
        self.assertIn("MISSING_VALUE", missing.quality_flags)

    def test_climatology_preserves_normal_and_weight_vintages(self) -> None:
        references = parse_cpc_climatology(
            _fixture("cpc_climatology_1981_2010.txt"),
            normal_period="1981-2010",
            normal_version="CPC_DAILY_1981_2010_V1",
            weight_vintage="2010",
            available_time="2013-11-06T21:46:00Z",
            source_file_id="climatology/1981-2010/UtilityGas.Heating.txt",
            content_hash="sha256:fixture-climatology",
        )
        normal = next(ref for ref in references if ref.region_id == "1")
        self.assertEqual(normal.reference_type, WeatherReferenceType.CLIMATOLOGY)
        self.assertEqual(normal.payload["variable"], WeatherVariable.HDD65.value)
        self.assertEqual(
            normal.weighting_method,
            WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
        )
        self.assertEqual(normal.normal_period, "1981-2010")
        self.assertEqual(normal.reference_version, "CPC_DAILY_1981_2010_V1")
        self.assertEqual(normal.weighting_version, "2010")
        self.assertEqual(normal.available_from, "2013-11-06T21:46:00Z")
        self.assertEqual(normal.payload["calendar_day"], "0818")


class CpcRegionParserTests(unittest.TestCase):
    def test_source_region_anomaly_is_preserved_not_repaired(self) -> None:
        mappings = parse_cpc_regions(
            _fixture("cpc_regions.txt"),
            available_time="2014-02-07T16:40:00Z",
            source_file_id="regions/StatesCONUS-CensusDivisions.txt",
        )
        vermont = next(mapping for mapping in mappings if mapping.region_id == "VT")
        self.assertEqual(vermont.reference_type, WeatherReferenceType.REGION_CROSSWALK)
        self.assertEqual(vermont.payload["raw_census_division_id"], "8")
        self.assertEqual(vermont.payload["raw_census_division_name"], "MOUNTAIN")
        self.assertIn("SOURCE_REGION_MAPPING_ANOMALY", vermont.quality_flags)
        self.assertIsNone(vermont.payload["corrected_census_division_id"])

    def test_region_taxonomies_cannot_conflate(self) -> None:
        identities = {
            region_identity("CPC", WeatherRegionType.STATE, "VT"),
            region_identity("CPC", WeatherRegionType.CENSUS_DIVISION, "8"),
            region_identity("CPC", WeatherRegionType.CLIMATE_DIVISION, "VT-01"),
            region_identity("CPC", WeatherRegionType.CONUS, "CONUS"),
            region_identity("EIA", "STORAGE_REGION", "MOUNTAIN"),
        }
        self.assertEqual(len(identities), 5)


if __name__ == "__main__":
    unittest.main()
