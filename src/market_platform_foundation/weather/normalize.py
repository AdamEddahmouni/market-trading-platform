"""Normalize current NWS captures into provider-neutral weather forecasts."""

from __future__ import annotations

from datetime import datetime

from .contracts import (
    WeatherAvailabilityPrecision,
    WeatherForecastObservation,
    WeatherHistoryClass,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from .nws import NwsForecastCapture, NwsPointMapping


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_nws_forecast(
    capture: NwsForecastCapture,
    *,
    mapping: NwsPointMapping,
    ingested_time: str,
    content_hash: str,
) -> tuple[WeatherForecastObservation, ...]:
    issue = capture.forecast_issue_time
    available = capture.forecast_available_time
    rows: list[WeatherForecastObservation] = []
    for period in capture.periods:
        lead_hours = None
        if issue and period.start_time:
            lead_hours = int((_datetime(period.start_time) - _datetime(issue)).total_seconds() // 3600)
        rows.append(
            WeatherForecastObservation(
                canonical_weather_indicator="NWS_POINT_TEMPERATURE",
                source="nws",
                source_product=f"NWS_{capture.forecast_kind}_FORECAST",
                source_product_version=issue,
                region_type=WeatherRegionType.NWS_POINT,
                region_id=f"{mapping.latitude:.4f},{mapping.longitude:.4f}",
                region_name=mapping.time_zone,
                source_region_id=mapping.mapping_identity,
                weighting_method=WeatherWeightingMethod.NONE,
                variable=WeatherVariable.TEMPERATURE,
                forecast_issue_time=issue,
                forecast_available_time=available,
                availability_precision=WeatherAvailabilityPrecision.FIRST_OBSERVED,
                target_start=period.start_time,
                target_end=period.end_time,
                lead_hours=lead_hours,
                lead_days=(lead_hours // 24) if lead_hours is not None else None,
                raw_value=str(period.temperature) if period.temperature is not None else None,
                value=period.temperature,
                unit=period.temperature_unit,
                source_file_id=capture.provider_url,
                provider_first_observed_time=available,
                retrieved_time=capture.retrieved_time,
                ingested_time=ingested_time,
                content_hash=f"{content_hash}:{period.number}",
                history_class=WeatherHistoryClass.CURRENT_API_FORECAST,
                provenance_ref=f"nws:{capture.provider_url}",
                predictive=False,
            )
        )
    return tuple(rows)


__all__ = ["normalize_nws_forecast"]
