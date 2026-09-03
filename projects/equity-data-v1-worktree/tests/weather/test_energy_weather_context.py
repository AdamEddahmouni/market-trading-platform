"""FRED + CFTC + EIA + weather independent-clock integration."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.contracts import (
    CotParticipantCategory,
    CotPositionScope,
    CotReportFamily,
    InstitutionalPositioningObservation,
)
from market_platform_foundation.cftc.store import CotStore
from market_platform_foundation.eia.cross_asset import build_energy_market_context
from market_platform_foundation.eia.normalize import normalize_api_row
from market_platform_foundation.eia.registry import lookup_canonical as lookup_energy
from market_platform_foundation.eia.store import EiaStore
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.registry import lookup_canonical as lookup_macro
from market_platform_foundation.weather.contracts import (
    WeatherAvailabilityPrecision,
    WeatherForecastObservation,
    WeatherHistoryClass,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from market_platform_foundation.weather.store import WeatherStore

FIXTURE = ROOT / "tests" / "fixtures" / "weather" / "energy_weather_timeline.json"


class EnergyWeatherContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.weather_store = WeatherStore()
        for day, available, base in (
            (17, self.timeline["weather_monday_available"], 10.0),
            (18, self.timeline["weather_tuesday_available"], 12.0),
            (19, self.timeline["weather_wednesday_available"], 15.0),
        ):
            issue = f"2026-08-{day:02d}T00:00:00Z"
            rows = tuple(self._weather_row(issue, available, lead, base + lead) for lead in range(7))
            self.weather_store.add_forecasts(rows)

        self.eia_store = EiaStore()
        entry = lookup_energy("LOWER48_WORKING_GAS_STORAGE")
        assert entry
        storage = normalize_api_row(
            {"period": "2026-08-14", "series": entry.series, "value": 3169},
            entry=entry,
            observed_time=self.timeline["wngsr_available"],
            retrieved_time=self.timeline["wngsr_available"],
            api_first_observed_time=self.timeline["wngsr_available"],
        )
        assert storage
        self.eia_store.add_observation(storage)

        self.cot_store = CotStore()
        self.cot_store.add_observation(
            InstitutionalPositioningObservation(
                market_id="NG",
                contract_family_id="NG",
                cftc_contract_market_code="023651",
                cftc_commodity_code="023651",
                market_and_exchange_names="HENRY HUB NATURAL GAS",
                report_family=CotReportFamily.DISAGGREGATED,
                position_scope=CotPositionScope.FUTURES_ONLY,
                participant_category=CotParticipantCategory.MANAGED_MONEY,
                position_date="2026-08-18",
                publication_time=self.timeline["cot_available"],
                available_time=self.timeline["cot_available"],
                observed_time=self.timeline["cot_available"],
                long_positions=150,
                short_positions=100,
            )
        )

    @staticmethod
    def _weather_row(issue: str, available: str, lead: int, value: float) -> WeatherForecastObservation:
        issue_dt = datetime.fromisoformat(issue.replace("Z", "+00:00"))
        target = issue_dt + timedelta(days=lead)
        target_end = target + timedelta(days=1)
        return WeatherForecastObservation(
            canonical_weather_indicator="CPC_HDD65_CONUS_UTILITY_GAS_CUSTOMERS",
            source="cpc",
            source_product="CPC_HDD65_NDFD_7DAY_FORECAST",
            source_product_version=issue,
            region_type=WeatherRegionType.CONUS,
            region_id="CONUS",
            weighting_method=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
            weighting_version="2010",
            variable=WeatherVariable.HDD65,
            forecast_issue_time=issue,
            forecast_available_time=available,
            availability_precision=WeatherAvailabilityPrecision.FIRST_OBSERVED,
            target_start=target.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            target_end=target_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            lead_hours=lead * 24,
            lead_days=lead,
            value=value,
            unit="degree_days",
            content_hash=f"{issue}:{lead}",
            history_class=WeatherHistoryClass.ARCHIVED_FORECAST_VINTAGE,
        )

    def _macro(self) -> MacroObservation:
        entry = lookup_macro("US_REAL_GDP")
        assert entry
        return MacroObservation(
            canonical_indicator_id="US_REAL_GDP",
            series_id=entry.fred_series_id,
            observation_date="2026-07-01",
            raw_value="2.1",
            normalized_value=2.1,
            frequency=entry.frequency,
            units=entry.units,
            seasonal_adjustment=entry.seasonal_adjustment,
            source_agency="BEA",
            fred_release_id=None,
            realtime_start="2026-07-01",
            realtime_end="2026-07-01",
            vintage_date="2026-07-01",
            available_time=self.timeline["macro_available"],
            availability_precision="TIMESTAMP",
        )

    def test_four_sources_keep_independent_clocks(self) -> None:
        for step in self.timeline["timeline"]:
            context = build_energy_market_context(
                macro_observations=[self._macro()],
                cot_store=self.cot_store,
                eia_store=self.eia_store,
                weather_store=self.weather_store,
                decision_time=step["decision_time"],
                contract_family_id="NG",
            )
            self.assertIsNotNone(context.weather_demand_state, step["label"])
            self.assertEqual(
                {row.forecast_issue_time for row in context.weather_demand_state.forecast_hdd_1_7d},
                {step["weather_issue"]},
                step["label"],
            )
            self.assertEqual(
                context.physical_fundamentals_state.natural_gas.lower48_storage is not None,
                step["storage_visible"],
                step["label"],
            )
            self.assertEqual(
                context.institutional_positioning_state is not None,
                step["cot_visible"],
                step["label"],
            )
            self.assertLessEqual(context.weather_available_time, step["decision_time"])
            self.assertEqual(context.staleness["weather"], context.weather_available_time)

    def test_context_has_no_weather_score_or_direction(self) -> None:
        context = build_energy_market_context(
            macro_observations=[self._macro()],
            cot_store=self.cot_store,
            eia_store=self.eia_store,
            weather_store=self.weather_store,
            decision_time="2026-08-21T20:00:00Z",
            contract_family_id="NG",
        )
        self.assertFalse(hasattr(context.weather_demand_state, "weather_score"))
        self.assertFalse(hasattr(context.weather_demand_state, "temperature_signal"))
        self.assertEqual(context.contradictions, ())


if __name__ == "__main__":
    unittest.main()
