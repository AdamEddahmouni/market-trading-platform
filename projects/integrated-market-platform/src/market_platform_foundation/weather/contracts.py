"""Provider-neutral weather-demand evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WeatherVariable(StrEnum):
    TEMPERATURE = "TEMPERATURE"
    DEW_POINT = "DEW_POINT"
    HDD65 = "HDD65"
    CDD65 = "CDD65"
    WIND_SPEED = "WIND_SPEED"
    PROBABILITY_OF_PRECIPITATION = "PROBABILITY_OF_PRECIPITATION"
    QUANTITATIVE_PRECIPITATION = "QUANTITATIVE_PRECIPITATION"
    WEATHER_CONDITION = "WEATHER_CONDITION"
    TEMPERATURE_OUTLOOK = "TEMPERATURE_OUTLOOK"


class WeatherRegionType(StrEnum):
    STATE = "STATE"
    CENSUS_DIVISION = "CENSUS_DIVISION"
    CLIMATE_DIVISION = "CLIMATE_DIVISION"
    CONUS = "CONUS"
    NWS_POINT = "NWS_POINT"
    NWS_GRID = "NWS_GRID"


class WeatherWeightingMethod(StrEnum):
    NONE = "NONE"
    POPULATION = "POPULATION"
    UTILITY_GAS_CUSTOMERS = "UTILITY_GAS_CUSTOMERS"
    BOTTLED_TANK_LP_GAS = "BOTTLED_TANK_LP_GAS"
    COAL_COKE = "COAL_COKE"
    ELECTRICITY = "ELECTRICITY"
    FUEL_OIL_KEROSENE = "FUEL_OIL_KEROSENE"
    NO_FUEL_USED = "NO_FUEL_USED"
    OTHER_FUEL = "OTHER_FUEL"
    SOLAR_ENERGY = "SOLAR_ENERGY"
    WOOD = "WOOD"


class WeatherAvailabilityPrecision(StrEnum):
    TIMESTAMP = "TIMESTAMP"
    FIRST_OBSERVED = "FIRST_OBSERVED"
    HTTP_LAST_MODIFIED_PROXY = "HTTP_LAST_MODIFIED_PROXY"
    DATE_ONLY = "DATE_ONLY"
    UNKNOWN = "UNKNOWN"


class WeatherHistoryClass(StrEnum):
    ARCHIVED_FORECAST_VINTAGE = "ARCHIVED_FORECAST_VINTAGE"
    PROSPECTIVE_CAPTURED_FORECAST = "PROSPECTIVE_CAPTURED_FORECAST"
    ARCHIVE_AVAILABILITY_INFERRED = "ARCHIVE_AVAILABILITY_INFERRED"
    ISSUE_KNOWN_AVAILABILITY_UNKNOWN = "ISSUE_KNOWN_AVAILABILITY_UNKNOWN"
    CURRENT_API_FORECAST = "CURRENT_API_FORECAST"
    CURRENT_REALIZATION_ARCHIVE = "CURRENT_REALIZATION_ARCHIVE"


class WeatherReferenceType(StrEnum):
    CLIMATOLOGY = "CLIMATOLOGY"
    REGION_CROSSWALK = "REGION_CROSSWALK"
    WEIGHTING = "WEIGHTING"
    NWS_GRID_MAPPING = "NWS_GRID_MAPPING"


class WeatherFeatureLayer(StrEnum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"
    PREDICTIVE_NOT_VALIDATED = "PREDICTIVE_NOT_VALIDATED"


@dataclass(frozen=True, slots=True)
class WeatherForecastObservation:
    canonical_weather_indicator: str
    source: str
    source_product: str
    source_product_version: str
    region_type: WeatherRegionType
    region_id: str
    weighting_method: WeatherWeightingMethod
    variable: WeatherVariable
    forecast_issue_time: str
    forecast_available_time: str
    availability_precision: WeatherAvailabilityPrecision
    target_start: str
    target_end: str
    value: float | None
    unit: str
    region_name: str = ""
    source_region_id: str = ""
    weighting_version: str = ""
    lead_hours: int | None = None
    lead_days: int | None = None
    raw_value: str | None = None
    source_file_id: str = ""
    source_file_last_modified: str = ""
    archive_file_time: str = ""
    provider_first_observed_time: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""
    content_hash: str = ""
    history_class: WeatherHistoryClass = WeatherHistoryClass.ARCHIVED_FORECAST_VINTAGE
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherRealizationObservation:
    canonical_weather_indicator: str
    source: str
    source_product: str
    source_product_version: str
    region_type: WeatherRegionType
    region_id: str
    weighting_method: WeatherWeightingMethod
    variable: WeatherVariable
    period_start: str
    period_end: str
    available_time: str
    availability_precision: WeatherAvailabilityPrecision
    value: float | None
    unit: str
    region_name: str = ""
    source_region_id: str = ""
    weighting_version: str = ""
    observation_time: str = ""
    raw_value: str | None = None
    provider_first_observed_time: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""
    content_hash: str = ""
    history_class: WeatherHistoryClass = WeatherHistoryClass.CURRENT_REALIZATION_ARCHIVE
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherReferenceObservation:
    reference_type: WeatherReferenceType
    reference_id: str
    reference_version: str
    available_from: str
    source: str
    source_product: str
    payload: dict[str, Any]
    normal_period: str = ""
    weighting_method: WeatherWeightingMethod = WeatherWeightingMethod.NONE
    weighting_version: str = ""
    region_type: WeatherRegionType | None = None
    region_id: str = ""
    content_hash: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherForecastRevision:
    target_start: str
    target_end: str
    latest_issue_time: str
    previous_issue_time: str
    latest_available_time: str
    latest_value: float | None
    previous_value: float | None
    delta: float | None
    unit: str
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherForecastError:
    forecast_issue_time: str
    target_start: str
    target_end: str
    forecast_value: float
    realized_value: float
    signed_error: float
    absolute_error: float
    available_time: str
    unit: str
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherDegreeDayAnomaly:
    canonical_weather_indicator: str
    target_start: str
    forecast_value: float
    normal_value: float
    value: float
    unit: str
    normal_period: str
    normal_version: str
    weighting_version: str
    available_time: str
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class WeatherDemandState:
    decision_time: str
    forecast_hdd_1_7d: tuple[WeatherForecastObservation, ...] = field(default_factory=tuple)
    forecast_cdd_1_7d: tuple[WeatherForecastObservation, ...] = field(default_factory=tuple)
    realized_hdd: tuple[WeatherRealizationObservation, ...] = field(default_factory=tuple)
    realized_cdd: tuple[WeatherRealizationObservation, ...] = field(default_factory=tuple)
    next_3d_hdd: float | None = None
    next_7d_hdd: float | None = None
    next_3d_cdd: float | None = None
    next_7d_cdd: float | None = None
    utility_gas_hdd_7d: float | None = None
    population_hdd_7d: float | None = None
    population_cdd_7d: float | None = None
    forecast_revision_hdd: WeatherForecastRevision | None = None
    forecast_revision_cdd: WeatherForecastRevision | None = None
    forecast_vs_normal: dict[str, float | None] = field(default_factory=dict)
    latest_forecast_available_time: str = ""
    source_age: dict[str, str | None] = field(default_factory=dict)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    predictive: bool = False


def forecast_observation_to_dict(obs: WeatherForecastObservation) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    for name in ("region_type", "weighting_method", "variable", "availability_precision", "history_class"):
        data[name] = data[name].value
    data["quality_flags"] = list(obs.quality_flags)
    return data


def realization_observation_to_dict(obs: WeatherRealizationObservation) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    for name in ("region_type", "weighting_method", "variable", "availability_precision", "history_class"):
        data[name] = data[name].value
    data["quality_flags"] = list(obs.quality_flags)
    return data


def reference_observation_to_dict(obs: WeatherReferenceObservation) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    data["reference_type"] = obs.reference_type.value
    data["weighting_method"] = obs.weighting_method.value
    data["region_type"] = obs.region_type.value if obs.region_type else None
    data["quality_flags"] = list(obs.quality_flags)
    return data


__all__ = [
    "WeatherAvailabilityPrecision",
    "WeatherDemandState",
    "WeatherDegreeDayAnomaly",
    "WeatherFeatureLayer",
    "WeatherForecastError",
    "WeatherForecastObservation",
    "WeatherForecastRevision",
    "WeatherHistoryClass",
    "WeatherRealizationObservation",
    "WeatherReferenceObservation",
    "WeatherReferenceType",
    "WeatherRegionType",
    "WeatherVariable",
    "WeatherWeightingMethod",
    "forecast_observation_to_dict",
    "reference_observation_to_dict",
    "realization_observation_to_dict",
]
