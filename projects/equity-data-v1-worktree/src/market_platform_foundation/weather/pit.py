"""Weather-specific point-in-time selectors."""

from __future__ import annotations

from .contracts import (
    WeatherForecastError,
    WeatherForecastObservation,
    WeatherForecastRevision,
    WeatherRealizationObservation,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)


def _target_contains(start: str, end: str, target_time: str) -> bool:
    return bool(start and target_time >= start and (not end or target_time < end))


def _forecast_matches(
    obs: WeatherForecastObservation,
    *,
    target_time: str,
    region_type: WeatherRegionType,
    region_id: str,
    variable: WeatherVariable,
    weighting_method: WeatherWeightingMethod,
    source_product: str | None,
) -> bool:
    return (
        _target_contains(obs.target_start, obs.target_end, target_time)
        and obs.region_type == region_type
        and obs.region_id == region_id
        and obs.variable == variable
        and obs.weighting_method == weighting_method
        and (source_product is None or obs.source_product == source_product)
    )


def forecast_versions_as_of(
    observations: list[WeatherForecastObservation] | tuple[WeatherForecastObservation, ...],
    *,
    target_time: str,
    decision_time: str,
    region_type: WeatherRegionType,
    region_id: str,
    variable: WeatherVariable,
    weighting_method: WeatherWeightingMethod,
    source_product: str | None = None,
) -> tuple[WeatherForecastObservation, ...]:
    visible = [
        obs
        for obs in observations
        if obs.forecast_available_time
        and obs.forecast_available_time <= decision_time
        and _forecast_matches(
            obs,
            target_time=target_time,
            region_type=region_type,
            region_id=region_id,
            variable=variable,
            weighting_method=weighting_method,
            source_product=source_product,
        )
    ]
    latest_correction_by_issue: dict[tuple[str, str], WeatherForecastObservation] = {}
    for obs in visible:
        key = (obs.source_product, obs.forecast_issue_time)
        current = latest_correction_by_issue.get(key)
        if current is None or (obs.forecast_available_time, obs.ingested_time, obs.content_hash) > (
            current.forecast_available_time,
            current.ingested_time,
            current.content_hash,
        ):
            latest_correction_by_issue[key] = obs
    return tuple(
        sorted(
            latest_correction_by_issue.values(),
            key=lambda obs: (obs.forecast_issue_time, obs.forecast_available_time),
        )
    )


def forecast_as_of(
    observations: list[WeatherForecastObservation] | tuple[WeatherForecastObservation, ...],
    **query,
) -> WeatherForecastObservation | None:
    visible = forecast_versions_as_of(observations, **query)
    return visible[-1] if visible else None


def forecast_revision(
    observations: list[WeatherForecastObservation] | tuple[WeatherForecastObservation, ...],
    **query,
) -> WeatherForecastRevision | None:
    visible = forecast_versions_as_of(observations, **query)
    if len(visible) < 2:
        return None
    previous, latest = visible[-2], visible[-1]
    delta = None
    if latest.value is not None and previous.value is not None:
        delta = latest.value - previous.value
    return WeatherForecastRevision(
        target_start=latest.target_start,
        target_end=latest.target_end,
        latest_issue_time=latest.forecast_issue_time,
        previous_issue_time=previous.forecast_issue_time,
        latest_available_time=latest.forecast_available_time,
        latest_value=latest.value,
        previous_value=previous.value,
        delta=delta,
        unit=latest.unit,
    )


def realization_as_of(
    observations: list[WeatherRealizationObservation] | tuple[WeatherRealizationObservation, ...],
    *,
    target_time: str,
    decision_time: str,
    region_type: WeatherRegionType,
    region_id: str,
    variable: WeatherVariable,
    weighting_method: WeatherWeightingMethod,
) -> WeatherRealizationObservation | None:
    visible = [
        obs
        for obs in observations
        if obs.available_time
        and obs.available_time <= decision_time
        and _target_contains(obs.period_start, obs.period_end, target_time)
        and obs.region_type == region_type
        and obs.region_id == region_id
        and obs.variable == variable
        and obs.weighting_method == weighting_method
    ]
    if not visible:
        return None
    return max(visible, key=lambda obs: (obs.available_time, obs.ingested_time, obs.content_hash))


def forecast_error_as_of(
    forecasts: list[WeatherForecastObservation] | tuple[WeatherForecastObservation, ...],
    realizations: list[WeatherRealizationObservation] | tuple[WeatherRealizationObservation, ...],
    **query,
) -> WeatherForecastError | None:
    forecast = forecast_as_of(forecasts, **query)
    realization = realization_as_of(realizations, **query)
    if forecast is None or realization is None or forecast.value is None or realization.value is None:
        return None
    signed = realization.value - forecast.value
    return WeatherForecastError(
        forecast_issue_time=forecast.forecast_issue_time,
        target_start=forecast.target_start,
        target_end=forecast.target_end,
        forecast_value=forecast.value,
        realized_value=realization.value,
        signed_error=signed,
        absolute_error=abs(signed),
        available_time=max(forecast.forecast_available_time, realization.available_time),
        unit=forecast.unit,
    )


__all__ = [
    "forecast_as_of",
    "forecast_error_as_of",
    "forecast_revision",
    "forecast_versions_as_of",
    "realization_as_of",
]
