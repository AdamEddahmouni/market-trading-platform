"""Normalization and prospective capture helpers for the current NWS API."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol

from .quality import WeatherQualityFlag
from .transport import NWS_API_BASE, WeatherTransport


class JsonTransport(Protocol):
    def request_json(self, url: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class NwsPointMapping:
    latitude: float
    longitude: float
    office: str
    grid_x: int
    grid_y: int
    forecast_url: str
    hourly_forecast_url: str
    grid_data_url: str
    observation_stations_url: str
    forecast_office_url: str
    forecast_zone_url: str
    county_url: str
    time_zone: str
    radar_station: str
    retrieved_time: str
    revalidate_after: str
    mapping_identity: str
    mapping_hash: str
    mapping_changed: bool = False
    previous_mapping_identity: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NwsForecastPeriod:
    number: int
    name: str
    start_time: str
    end_time: str
    is_daytime: bool | None
    temperature: float | None
    temperature_unit: str
    temperature_trend: str | None
    precipitation_probability: float | None
    precipitation_probability_unit: str
    wind_speed: str
    wind_direction: str
    short_forecast: str
    detailed_forecast: str


@dataclass(frozen=True, slots=True)
class NwsForecastCapture:
    forecast_kind: str
    provider_url: str
    updated_time: str
    generated_at: str
    update_time: str
    valid_times: str
    units: str
    forecast_generator: str
    elevation_value: float | None
    elevation_unit: str
    periods: tuple[NwsForecastPeriod, ...]
    horizon_start: str
    horizon_end: str
    provider_first_observed_time: str
    retrieved_time: str

    @property
    def forecast_issue_time(self) -> str:
        return self.update_time or self.updated_time or self.generated_at

    @property
    def forecast_available_time(self) -> str:
        return self.provider_first_observed_time


@dataclass(frozen=True, slots=True)
class NwsGridValue:
    raw_valid_time: str
    start_time: str
    duration: str
    end_time: str
    value: Any


@dataclass(frozen=True, slots=True)
class NwsGridElement:
    name: str
    unit: str
    values: tuple[NwsGridValue, ...]


@dataclass(frozen=True, slots=True)
class NwsGridCapture:
    provider_url: str
    forecast_office_url: str
    office: str
    grid_x: int | None
    grid_y: int | None
    update_time: str
    valid_times: str
    elevation_value: float | None
    elevation_unit: str
    elements: Mapping[str, NwsGridElement]
    horizon_start: str
    horizon_end: str
    provider_first_observed_time: str
    retrieved_time: str


@dataclass(frozen=True, slots=True)
class NwsMeasurement:
    value: float | int | str | None
    unit: str
    quality_control: str


@dataclass(frozen=True, slots=True)
class NwsObservationCapture:
    provider_url: str
    station_url: str
    observation_time: str
    provider_first_observed_time: str
    retrieved_time: str
    raw_message: str
    text_description: str
    measurements: Mapping[str, NwsMeasurement]
    quality_flags: tuple[str, ...]


def parse_nws_point_mapping(
    payload: dict[str, Any],
    *,
    requested_latitude: float,
    requested_longitude: float,
    retrieved_time: str,
    revalidate_after_days: int = 7,
    previous: NwsPointMapping | None = None,
) -> NwsPointMapping:
    properties = _properties(payload)
    office = str(properties.get("gridId") or properties.get("cwa") or "").strip()
    grid_x = _required_int(properties.get("gridX"), "NWS_GRID_X_MISSING")
    grid_y = _required_int(properties.get("gridY"), "NWS_GRID_Y_MISSING")
    if not office:
        raise ValueError("NWS_GRID_OFFICE_MISSING")
    identity = f"{office}:{grid_x},{grid_y}"
    previous_identity = previous.mapping_identity if previous else ""
    changed = bool(previous and previous_identity != identity)
    flags = (WeatherQualityFlag.GRID_MAPPING_CHANGED.value,) if changed else ()
    revalidate_after = _format_datetime(
        _parse_datetime(retrieved_time) + timedelta(days=max(0, revalidate_after_days))
    )
    identity_payload = {
        "latitude": requested_latitude,
        "longitude": requested_longitude,
        "office": office,
        "grid_x": grid_x,
        "grid_y": grid_y,
    }
    mapping_hash = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return NwsPointMapping(
        latitude=float(requested_latitude),
        longitude=float(requested_longitude),
        office=office,
        grid_x=grid_x,
        grid_y=grid_y,
        forecast_url=str(properties.get("forecast") or ""),
        hourly_forecast_url=str(properties.get("forecastHourly") or ""),
        grid_data_url=str(properties.get("forecastGridData") or ""),
        observation_stations_url=str(properties.get("observationStations") or ""),
        forecast_office_url=str(properties.get("forecastOffice") or ""),
        forecast_zone_url=str(properties.get("forecastZone") or ""),
        county_url=str(properties.get("county") or ""),
        time_zone=str(properties.get("timeZone") or ""),
        radar_station=str(properties.get("radarStation") or ""),
        retrieved_time=retrieved_time,
        revalidate_after=revalidate_after,
        mapping_identity=identity,
        mapping_hash=mapping_hash,
        mapping_changed=changed,
        previous_mapping_identity=previous_identity,
        quality_flags=flags,
    )


def mapping_needs_revalidation(mapping: NwsPointMapping, as_of: str) -> bool:
    return _parse_datetime(as_of) >= _parse_datetime(mapping.revalidate_after)


def parse_nws_forecast(
    payload: dict[str, Any],
    *,
    retrieved_time: str,
    provider_first_observed_time: str = "",
    forecast_kind: str = "TWELVE_HOUR",
    source_url: str = "",
) -> NwsForecastCapture:
    properties = _properties(payload)
    parsed_periods: list[NwsForecastPeriod] = []
    for raw in properties.get("periods") or []:
        if not isinstance(raw, dict):
            continue
        probability = raw.get("probabilityOfPrecipitation")
        probability = probability if isinstance(probability, dict) else {}
        parsed_periods.append(
            NwsForecastPeriod(
                number=int(raw.get("number") or 0),
                name=str(raw.get("name") or ""),
                start_time=str(raw.get("startTime") or ""),
                end_time=str(raw.get("endTime") or ""),
                is_daytime=raw.get("isDaytime") if isinstance(raw.get("isDaytime"), bool) else None,
                temperature=_optional_float(raw.get("temperature")),
                temperature_unit=str(raw.get("temperatureUnit") or ""),
                temperature_trend=(
                    str(raw["temperatureTrend"]) if raw.get("temperatureTrend") is not None else None
                ),
                precipitation_probability=_optional_float(probability.get("value")),
                precipitation_probability_unit=str(probability.get("unitCode") or ""),
                wind_speed=str(raw.get("windSpeed") or ""),
                wind_direction=str(raw.get("windDirection") or ""),
                short_forecast=str(raw.get("shortForecast") or ""),
                detailed_forecast=str(raw.get("detailedForecast") or ""),
            )
        )
    elevation = properties.get("elevation")
    elevation = elevation if isinstance(elevation, dict) else {}
    return NwsForecastCapture(
        forecast_kind=forecast_kind,
        provider_url=str(payload.get("@id") or properties.get("@id") or source_url),
        updated_time=str(properties.get("updated") or ""),
        generated_at=str(properties.get("generatedAt") or ""),
        update_time=str(properties.get("updateTime") or ""),
        valid_times=str(properties.get("validTimes") or ""),
        units=str(properties.get("units") or ""),
        forecast_generator=str(properties.get("forecastGenerator") or ""),
        elevation_value=_optional_float(elevation.get("value")),
        elevation_unit=str(elevation.get("unitCode") or ""),
        periods=tuple(parsed_periods),
        horizon_start=parsed_periods[0].start_time if parsed_periods else "",
        horizon_end=parsed_periods[-1].end_time if parsed_periods else "",
        provider_first_observed_time=provider_first_observed_time or retrieved_time,
        retrieved_time=retrieved_time,
    )


def parse_nws_grid(
    payload: dict[str, Any],
    *,
    retrieved_time: str,
    provider_first_observed_time: str = "",
    source_url: str = "",
) -> NwsGridCapture:
    properties = _properties(payload)
    elements: dict[str, NwsGridElement] = {}
    all_values: list[NwsGridValue] = []
    for name, raw_element in properties.items():
        if not isinstance(raw_element, dict) or "uom" not in raw_element:
            continue
        raw_values = raw_element.get("values")
        if not isinstance(raw_values, list):
            continue
        parsed_values: list[NwsGridValue] = []
        for raw in raw_values:
            if not isinstance(raw, dict):
                continue
            parsed = _parse_grid_value(raw)
            if parsed is not None:
                parsed_values.append(parsed)
                all_values.append(parsed)
        elements[name] = NwsGridElement(
            name=name,
            unit=str(raw_element.get("uom") or ""),
            values=tuple(parsed_values),
        )
    starts = [item.start_time for item in all_values if item.start_time]
    ends = [item.end_time for item in all_values if item.end_time]
    elevation = properties.get("elevation")
    elevation = elevation if isinstance(elevation, dict) else {}
    return NwsGridCapture(
        provider_url=str(payload.get("@id") or properties.get("@id") or source_url),
        forecast_office_url=str(properties.get("forecastOffice") or ""),
        office=str(properties.get("gridId") or ""),
        grid_x=_optional_int(properties.get("gridX")),
        grid_y=_optional_int(properties.get("gridY")),
        update_time=str(properties.get("updateTime") or ""),
        valid_times=str(properties.get("validTimes") or ""),
        elevation_value=_optional_float(elevation.get("value")),
        elevation_unit=str(elevation.get("unitCode") or ""),
        elements=elements,
        horizon_start=_chronological_extreme(starts, minimum=True),
        horizon_end=_chronological_extreme(ends, minimum=False),
        provider_first_observed_time=provider_first_observed_time or retrieved_time,
        retrieved_time=retrieved_time,
    )


def parse_nws_observation(
    payload: dict[str, Any],
    *,
    retrieved_time: str,
    provider_first_observed_time: str = "",
    source_url: str = "",
) -> NwsObservationCapture:
    properties = _properties(payload)
    measurements: dict[str, NwsMeasurement] = {}
    for name, raw in properties.items():
        if not isinstance(raw, dict) or "unitCode" not in raw or "value" not in raw:
            continue
        measurements[name] = NwsMeasurement(
            value=raw.get("value"),
            unit=str(raw.get("unitCode") or ""),
            quality_control=str(raw.get("qualityControl") or ""),
        )
    return NwsObservationCapture(
        provider_url=str(payload.get("@id") or properties.get("@id") or source_url),
        station_url=str(properties.get("station") or ""),
        observation_time=str(properties.get("timestamp") or ""),
        provider_first_observed_time=provider_first_observed_time or retrieved_time,
        retrieved_time=retrieved_time,
        raw_message=str(properties.get("rawMessage") or ""),
        text_description=str(properties.get("textDescription") or ""),
        measurements=measurements,
        quality_flags=(WeatherQualityFlag.OBSERVATION_LATENCY_UNCERTAIN.value,),
    )


class NwsClient:
    """Link-following NWS client; `/points` remains the mapping authority."""

    def __init__(self, *, transport: JsonTransport | None = None) -> None:
        self.transport = transport or WeatherTransport()

    def lookup_point(
        self,
        latitude: float,
        longitude: float,
        *,
        retrieved_time: str,
        previous: NwsPointMapping | None = None,
        revalidate_after_days: int = 7,
    ) -> NwsPointMapping:
        url = f"{NWS_API_BASE}/points/{_coordinate(latitude)},{_coordinate(longitude)}"
        payload = self.transport.request_json(url)
        return parse_nws_point_mapping(
            payload,
            requested_latitude=latitude,
            requested_longitude=longitude,
            retrieved_time=retrieved_time,
            previous=previous,
            revalidate_after_days=revalidate_after_days,
        )

    def fetch_forecast(
        self,
        mapping: NwsPointMapping,
        *,
        retrieved_time: str,
        provider_first_observed_time: str = "",
    ) -> NwsForecastCapture:
        payload = self.transport.request_json(mapping.forecast_url)
        return parse_nws_forecast(
            payload,
            retrieved_time=retrieved_time,
            provider_first_observed_time=provider_first_observed_time,
            source_url=mapping.forecast_url,
        )

    def fetch_hourly_forecast(
        self,
        mapping: NwsPointMapping,
        *,
        retrieved_time: str,
        provider_first_observed_time: str = "",
    ) -> NwsForecastCapture:
        payload = self.transport.request_json(mapping.hourly_forecast_url)
        return parse_nws_forecast(
            payload,
            retrieved_time=retrieved_time,
            provider_first_observed_time=provider_first_observed_time,
            forecast_kind="HOURLY",
            source_url=mapping.hourly_forecast_url,
        )

    def fetch_grid_data(
        self,
        mapping: NwsPointMapping,
        *,
        retrieved_time: str,
        provider_first_observed_time: str = "",
    ) -> NwsGridCapture:
        payload = self.transport.request_json(mapping.grid_data_url)
        return parse_nws_grid(
            payload,
            retrieved_time=retrieved_time,
            provider_first_observed_time=provider_first_observed_time,
            source_url=mapping.grid_data_url,
        )

    def fetch_station_collection(self, mapping: NwsPointMapping) -> dict[str, Any]:
        return self.transport.request_json(mapping.observation_stations_url)

    def fetch_latest_observation(
        self,
        station_id: str,
        *,
        retrieved_time: str,
        provider_first_observed_time: str = "",
    ) -> NwsObservationCapture:
        station = station_id.strip().upper()
        if not station or "/" in station:
            raise ValueError("NWS_STATION_ID_INVALID")
        url = f"{NWS_API_BASE}/stations/{station}/observations/latest"
        payload = self.transport.request_json(url)
        return parse_nws_observation(
            payload,
            retrieved_time=retrieved_time,
            provider_first_observed_time=provider_first_observed_time,
            source_url=url,
        )


def _properties(payload: dict[str, Any]) -> dict[str, Any]:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("NWS_PROPERTIES_MISSING")
    return properties


def _parse_grid_value(raw: dict[str, Any]) -> NwsGridValue | None:
    raw_valid_time = str(raw.get("validTime") or "")
    if not raw_valid_time or "/" not in raw_valid_time:
        return None
    start_time, duration = raw_valid_time.split("/", 1)
    end = _parse_datetime(start_time) + _parse_duration(duration)
    return NwsGridValue(
        raw_valid_time=raw_valid_time,
        start_time=start_time,
        duration=duration,
        end_time=_format_datetime(end),
        value=raw.get("value"),
    )


_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def _parse_duration(value: str) -> timedelta:
    match = _DURATION_RE.fullmatch(value)
    if not match:
        raise ValueError("NWS_VALID_TIME_DURATION_UNSUPPORTED")
    groups = {key: int(raw or 0) for key, raw in match.groupdict().items()}
    return timedelta(
        days=groups["days"],
        hours=groups["hours"],
        minutes=groups["minutes"],
        seconds=groups["seconds"],
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_datetime(value: datetime) -> str:
    return value.isoformat()


def _chronological_extreme(values: list[str], *, minimum: bool) -> str:
    if not values:
        return ""
    operation = min if minimum else max
    return operation(values, key=_parse_datetime)


def _required_int(value: Any, error: str) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        raise ValueError(error)
    return parsed


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coordinate(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


__all__ = [
    "NwsClient",
    "NwsForecastCapture",
    "NwsForecastPeriod",
    "NwsGridCapture",
    "NwsGridElement",
    "NwsGridValue",
    "NwsMeasurement",
    "NwsObservationCapture",
    "NwsPointMapping",
    "mapping_needs_revalidation",
    "parse_nws_forecast",
    "parse_nws_grid",
    "parse_nws_observation",
    "parse_nws_point_mapping",
]
