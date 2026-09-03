"""Deterministic, non-predictive weather-demand features."""

from __future__ import annotations

from .contracts import (
    WeatherDegreeDayAnomaly,
    WeatherDemandState,
    WeatherForecastObservation,
    WeatherReferenceObservation,
    WeatherReferenceType,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from .store import WeatherStore
from .pit import forecast_revision


def forecast_vs_normal(
    forecast: WeatherForecastObservation,
    references: tuple[WeatherReferenceObservation, ...] | list[WeatherReferenceObservation],
    *,
    decision_time: str,
) -> WeatherDegreeDayAnomaly | None:
    """Subtract only a PIT-visible, region/variable/weight-compatible normal."""

    if forecast.value is None or forecast.forecast_available_time > decision_time:
        return None
    calendar_day = forecast.target_start[5:10].replace("-", "")
    compatible = [
        ref
        for ref in references
        if ref.reference_type == WeatherReferenceType.CLIMATOLOGY
        and ref.available_from
        and ref.available_from <= decision_time
        and ref.region_type == forecast.region_type
        and ref.region_id == forecast.region_id
        and ref.weighting_method == forecast.weighting_method
        and ref.weighting_version == forecast.weighting_version
        and ref.payload.get("variable") == forecast.variable.value
        and ref.payload.get("calendar_day") == calendar_day
        and ref.payload.get("value") is not None
    ]
    if not compatible:
        return None
    normal = max(compatible, key=lambda ref: (ref.available_from, ref.reference_version))
    normal_value = float(normal.payload["value"])
    return WeatherDegreeDayAnomaly(
        canonical_weather_indicator=forecast.canonical_weather_indicator,
        target_start=forecast.target_start,
        forecast_value=forecast.value,
        normal_value=normal_value,
        value=forecast.value - normal_value,
        unit=forecast.unit,
        normal_period=normal.normal_period,
        normal_version=normal.reference_version,
        weighting_version=normal.weighting_version,
        available_time=max(forecast.forecast_available_time, normal.available_from),
    )


def _latest_vintage_rows(
    forecasts: list[WeatherForecastObservation],
    *,
    decision_time: str,
    region_type: WeatherRegionType,
    region_id: str,
    variable: WeatherVariable,
    weighting: WeatherWeightingMethod,
) -> tuple[WeatherForecastObservation, ...]:
    visible = [
        obs
        for obs in forecasts
        if obs.forecast_available_time
        and obs.forecast_available_time <= decision_time
        and obs.region_type == region_type
        and obs.region_id == region_id
        and obs.variable == variable
        and obs.weighting_method == weighting
    ]
    if not visible:
        return ()
    latest_issue = max(obs.forecast_issue_time for obs in visible)
    corrected_by_target: dict[tuple[str, str], WeatherForecastObservation] = {}
    for obs in visible:
        if obs.forecast_issue_time != latest_issue:
            continue
        key = (obs.target_start, obs.target_end)
        current = corrected_by_target.get(key)
        if current is None or (obs.forecast_available_time, obs.ingested_time, obs.content_hash) > (
            current.forecast_available_time,
            current.ingested_time,
            current.content_hash,
        ):
            corrected_by_target[key] = obs
    return tuple(sorted(corrected_by_target.values(), key=lambda obs: obs.target_start))


def _complete_sum(rows: tuple[WeatherForecastObservation, ...], count: int) -> float | None:
    selected = rows[:count]
    if len(selected) != count or any(obs.value is None for obs in selected):
        return None
    return sum(float(obs.value) for obs in selected if obs.value is not None)


def build_weather_demand_state(
    store: WeatherStore,
    *,
    decision_time: str,
    region_type: WeatherRegionType = WeatherRegionType.CONUS,
    region_id: str = "CONUS",
) -> WeatherDemandState:
    utility_hdd = _latest_vintage_rows(
        store.forecasts,
        decision_time=decision_time,
        region_type=region_type,
        region_id=region_id,
        variable=WeatherVariable.HDD65,
        weighting=WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
    )
    population_hdd = _latest_vintage_rows(
        store.forecasts,
        decision_time=decision_time,
        region_type=region_type,
        region_id=region_id,
        variable=WeatherVariable.HDD65,
        weighting=WeatherWeightingMethod.POPULATION,
    )
    population_cdd = _latest_vintage_rows(
        store.forecasts,
        decision_time=decision_time,
        region_type=region_type,
        region_id=region_id,
        variable=WeatherVariable.CDD65,
        weighting=WeatherWeightingMethod.POPULATION,
    )
    preferred_hdd = utility_hdd or population_hdd
    all_selected = preferred_hdd + population_hdd + population_cdd
    latest_available = max(
        (obs.forecast_available_time for obs in all_selected if obs.forecast_available_time),
        default="",
    )
    hdd_revision = None
    if preferred_hdd:
        hdd_revision = forecast_revision(
            store.forecasts,
            target_time=preferred_hdd[0].target_start,
            decision_time=decision_time,
            region_type=region_type,
            region_id=region_id,
            variable=WeatherVariable.HDD65,
            weighting_method=preferred_hdd[0].weighting_method,
        )
    cdd_revision = None
    if population_cdd:
        cdd_revision = forecast_revision(
            store.forecasts,
            target_time=population_cdd[0].target_start,
            decision_time=decision_time,
            region_type=region_type,
            region_id=region_id,
            variable=WeatherVariable.CDD65,
            weighting_method=WeatherWeightingMethod.POPULATION,
        )
    realized_hdd = tuple(
        obs
        for obs in store.realizations
        if obs.available_time <= decision_time
        and obs.region_type == region_type
        and obs.region_id == region_id
        and obs.variable == WeatherVariable.HDD65
    )
    realized_cdd = tuple(
        obs
        for obs in store.realizations
        if obs.available_time <= decision_time
        and obs.region_type == region_type
        and obs.region_id == region_id
        and obs.variable == WeatherVariable.CDD65
    )
    return WeatherDemandState(
        decision_time=decision_time,
        forecast_hdd_1_7d=preferred_hdd,
        forecast_cdd_1_7d=population_cdd,
        realized_hdd=realized_hdd,
        realized_cdd=realized_cdd,
        next_3d_hdd=_complete_sum(preferred_hdd, 3),
        next_7d_hdd=_complete_sum(preferred_hdd, 7),
        next_3d_cdd=_complete_sum(population_cdd, 3),
        next_7d_cdd=_complete_sum(population_cdd, 7),
        utility_gas_hdd_7d=_complete_sum(utility_hdd, 7),
        population_hdd_7d=_complete_sum(population_hdd, 7),
        population_cdd_7d=_complete_sum(population_cdd, 7),
        forecast_revision_hdd=hdd_revision,
        forecast_revision_cdd=cdd_revision,
        latest_forecast_available_time=latest_available,
        source_age={"weather": latest_available or None},
        provenance_ref="weather.weather_demand_state",
        predictive=False,
    )


__all__ = ["build_weather_demand_state", "forecast_vs_normal"]
