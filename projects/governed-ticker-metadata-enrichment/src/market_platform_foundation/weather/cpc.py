"""Parsers for CPC pipe-delimited degree-day evidence.

The parsers deliberately require callers to supply source availability.  CPC's
forecast issue embedded in a file is not evidence of when that file became
publicly observable.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .contracts import (
    WeatherAvailabilityPrecision,
    WeatherForecastObservation,
    WeatherHistoryClass,
    WeatherRealizationObservation,
    WeatherReferenceObservation,
    WeatherReferenceType,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
)
from .quality import WeatherQualityFlag


_ISSUED_RE = re.compile(r"\bIssued:?\s*(\d{4})\s*UTC\s*(\d{8})\b", re.IGNORECASE)
_MISSING_VALUES = frozenset({"", "M", "NA", "N/A", "NULL", "-999"})

_WEIGHTINGS = {
    "population": WeatherWeightingMethod.POPULATION,
    "utility gas": WeatherWeightingMethod.UTILITY_GAS_CUSTOMERS,
    "bottled/tank lp gas": WeatherWeightingMethod.BOTTLED_TANK_LP_GAS,
    "coal or coke": WeatherWeightingMethod.COAL_COKE,
    "electricity": WeatherWeightingMethod.ELECTRICITY,
    "fuel oil, kerosene, etc.": WeatherWeightingMethod.FUEL_OIL_KEROSENE,
    "no fuel used": WeatherWeightingMethod.NO_FUEL_USED,
    "other fuel": WeatherWeightingMethod.OTHER_FUEL,
    "solar energy": WeatherWeightingMethod.SOLAR_ENERGY,
    "wood": WeatherWeightingMethod.WOOD,
}


def _metadata_and_table(text: str) -> tuple[dict[str, str], list[str], list[list[str]]]:
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines() if line.strip()]
    metadata: dict[str, str] = {}
    header: list[str] | None = None
    rows: list[list[str]] = []
    for line in lines:
        if header is None and "|" not in line:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip().lower()] = value.strip()
            elif line.lower().startswith("issued"):
                metadata["issued"] = line
            continue
        columns = [cell.strip() for cell in line.split("|")]
        if header is None:
            if not columns or columns[0].lower() != "region":
                raise ValueError("CPC table must begin with a Region column")
            header = columns
        else:
            if len(columns) != len(header):
                raise ValueError("CPC data row does not match its header")
            rows.append(columns)
    if header is None:
        raise ValueError("CPC payload has no pipe-delimited table")
    for required in ("product", "regions", "weights"):
        if required not in metadata:
            raise ValueError(f"CPC payload is missing {required!r} metadata")
    return metadata, header, rows


def _variable(product: str) -> WeatherVariable:
    lowered = product.lower()
    if "heating degree days" in lowered:
        return WeatherVariable.HDD65
    if "cooling degree days" in lowered:
        return WeatherVariable.CDD65
    raise ValueError(f"Unsupported CPC degree-day product: {product!r}")


def _weighting(raw: str) -> WeatherWeightingMethod:
    try:
        return _WEIGHTINGS[" ".join(raw.lower().split())]
    except KeyError as exc:
        raise ValueError(f"Unsupported CPC weighting: {raw!r}") from exc


def _base_region_type(raw: str) -> WeatherRegionType:
    terminal = raw.split("::")[-1].strip().lower()
    if terminal == "censusdivisions":
        return WeatherRegionType.CENSUS_DIVISION
    if terminal == "statesconus":
        return WeatherRegionType.STATE
    if terminal == "climatedivisions":
        return WeatherRegionType.CLIMATE_DIVISION
    raise ValueError(f"Unsupported CPC region family: {raw!r}")


def _region_type(base: WeatherRegionType, region_id: str) -> WeatherRegionType:
    return WeatherRegionType.CONUS if region_id.upper() == "CONUS" else base


def _number(raw: str) -> tuple[float | None, tuple[str, ...]]:
    if raw.strip().upper() in _MISSING_VALUES:
        return None, (WeatherQualityFlag.MISSING_VALUE.value,)
    try:
        return float(raw), ()
    except ValueError as exc:
        raise ValueError(f"Invalid CPC degree-day value: {raw!r}") from exc


def _daily_period(raw: str) -> tuple[str, str]:
    start = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


def _issue_time(product: str, separately_declared: str = "") -> str:
    match = _ISSUED_RE.search(f"{product} {separately_declared}")
    if match is None:
        raise ValueError("CPC forecast payload has no declared issue cycle")
    cycle, raw_date = match.groups()
    issued = datetime.strptime(f"{raw_date}{cycle}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    return issued.isoformat().replace("+00:00", "Z")


def _source_product(variable: WeatherVariable, *, forecast: bool) -> str:
    suffix = "NDFD_7DAY_FORECAST" if forecast else "DAILY_REALIZED"
    return f"CPC_{variable.value}_{suffix}"


def _indicator(
    variable: WeatherVariable,
    region_type: WeatherRegionType,
    weighting: WeatherWeightingMethod,
) -> str:
    return f"CPC_{variable.value}_{region_type.value}_{weighting.value}"


def _iter_values(
    header: list[str],
    rows: Iterable[list[str]],
) -> Iterable[tuple[str, str, str]]:
    for row in rows:
        region_id = row[0]
        for column, raw_value in zip(header[1:], row[1:]):
            if column.strip().lower() == "total":
                continue
            yield region_id, column, raw_value


def parse_cpc_forecast(
    text: str,
    *,
    forecast_available_time: str,
    source_file_id: str = "",
    source_file_last_modified: str = "",
    provider_first_observed_time: str = "",
    retrieved_time: str = "",
    ingested_time: str = "",
    content_hash: str = "",
    provenance_ref: str = "",
    availability_precision: WeatherAvailabilityPrecision = (
        WeatherAvailabilityPrecision.HTTP_LAST_MODIFIED_PROXY
    ),
    history_class: WeatherHistoryClass = WeatherHistoryClass.ARCHIVED_FORECAST_VINTAGE,
    weighting_version: str = "2010",
) -> tuple[WeatherForecastObservation, ...]:
    """Parse one immutable CPC seven-day forecast file.

    The source's ``Total`` column is intentionally skipped because it is an
    aggregate of the seven target cells, not an eighth target observation.
    """

    metadata, header, rows = _metadata_and_table(text)
    product = metadata["product"]
    if "forecast" not in product.lower():
        raise ValueError("CPC forecast parser received a non-forecast product")
    variable = _variable(product)
    weighting = _weighting(metadata["weights"])
    base_region_type = _base_region_type(metadata["regions"])
    issue_time = _issue_time(product, metadata.get("issued", ""))
    issue_dt = datetime.fromisoformat(issue_time.replace("Z", "+00:00"))
    observations: list[WeatherForecastObservation] = []
    for region_id, raw_target, raw_value in _iter_values(header, rows):
        target_start, target_end = _daily_period(raw_target)
        target_dt = datetime.strptime(raw_target, "%Y%m%d").replace(tzinfo=timezone.utc)
        region_type = _region_type(base_region_type, region_id)
        value, flags = _number(raw_value)
        lead_hours = int((target_dt - issue_dt).total_seconds() // 3600)
        observations.append(
            WeatherForecastObservation(
                canonical_weather_indicator=_indicator(variable, region_type, weighting),
                source="cpc",
                source_product=_source_product(variable, forecast=True),
                source_product_version=issue_time,
                region_type=region_type,
                region_id=region_id,
                source_region_id=region_id,
                weighting_method=weighting,
                weighting_version=weighting_version,
                variable=variable,
                forecast_issue_time=issue_time,
                forecast_available_time=forecast_available_time,
                availability_precision=availability_precision,
                target_start=target_start,
                target_end=target_end,
                lead_hours=lead_hours,
                lead_days=lead_hours // 24,
                value=value,
                raw_value=raw_value,
                unit="degree_days",
                source_file_id=source_file_id,
                source_file_last_modified=source_file_last_modified,
                archive_file_time=source_file_last_modified,
                provider_first_observed_time=provider_first_observed_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                content_hash=content_hash,
                history_class=history_class,
                quality_flags=flags,
                provenance_ref=provenance_ref,
                predictive=False,
            )
        )
    return tuple(observations)


def parse_cpc_realized(
    text: str,
    *,
    available_time: str,
    provider_first_observed_time: str = "",
    retrieved_time: str = "",
    ingested_time: str = "",
    content_hash: str = "",
    source_file_id: str = "",
    provenance_ref: str = "",
    availability_precision: WeatherAvailabilityPrecision = (
        WeatherAvailabilityPrecision.HTTP_LAST_MODIFIED_PROXY
    ),
    weighting_version: str = "2010",
) -> tuple[WeatherRealizationObservation, ...]:
    """Parse a CPC current-history realized degree-day file."""

    metadata, header, rows = _metadata_and_table(text)
    product = metadata["product"]
    if "forecast" in product.lower():
        raise ValueError("CPC realization parser received a forecast product")
    variable = _variable(product)
    weighting = _weighting(metadata["weights"])
    base_region_type = _base_region_type(metadata["regions"])
    observations: list[WeatherRealizationObservation] = []
    for region_id, raw_period, raw_value in _iter_values(header, rows):
        period_start, period_end = _daily_period(raw_period)
        region_type = _region_type(base_region_type, region_id)
        value, flags = _number(raw_value)
        observations.append(
            WeatherRealizationObservation(
                canonical_weather_indicator=_indicator(variable, region_type, weighting),
                source="cpc",
                source_product=_source_product(variable, forecast=False),
                source_product_version=source_file_id,
                region_type=region_type,
                region_id=region_id,
                source_region_id=region_id,
                weighting_method=weighting,
                weighting_version=weighting_version,
                variable=variable,
                period_start=period_start,
                period_end=period_end,
                available_time=available_time,
                availability_precision=availability_precision,
                value=value,
                raw_value=raw_value,
                unit="degree_days",
                provider_first_observed_time=provider_first_observed_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                content_hash=content_hash,
                history_class=WeatherHistoryClass.CURRENT_REALIZATION_ARCHIVE,
                quality_flags=flags,
                provenance_ref=provenance_ref or (f"cpc:{source_file_id}" if source_file_id else ""),
                predictive=False,
            )
        )
    return tuple(observations)


def parse_cpc_climatology(
    text: str,
    *,
    normal_period: str,
    normal_version: str,
    weight_vintage: str,
    available_time: str,
    source_file_id: str = "",
    content_hash: str = "",
    retrieved_time: str = "",
    ingested_time: str = "",
    provenance_ref: str = "",
) -> tuple[WeatherReferenceObservation, ...]:
    """Parse CPC MMDD climatology without treating it as a timeless constant."""

    metadata, header, rows = _metadata_and_table(text)
    variable = _variable(metadata["product"])
    weighting = _weighting(metadata["weights"])
    base_region_type = _base_region_type(metadata["regions"])
    references: list[WeatherReferenceObservation] = []
    for region_id, calendar_day, raw_value in _iter_values(header, rows):
        if not re.fullmatch(r"\d{4}", calendar_day):
            raise ValueError(f"Invalid CPC climatology calendar day: {calendar_day!r}")
        region_type = _region_type(base_region_type, region_id)
        value, flags = _number(raw_value)
        reference_id = ":".join(
            (
                "CPC_CLIMATOLOGY",
                variable.value,
                region_type.value,
                region_id,
                weighting.value,
                calendar_day,
            )
        )
        references.append(
            WeatherReferenceObservation(
                reference_type=WeatherReferenceType.CLIMATOLOGY,
                reference_id=reference_id,
                reference_version=normal_version,
                available_from=available_time,
                source="cpc",
                source_product="CPC_DAILY_DEGREE_DAY_CLIMATOLOGY",
                payload={
                    "calendar_day": calendar_day,
                    "variable": variable.value,
                    "value": value,
                    "raw_value": raw_value,
                    "unit": "degree_days",
                    "source_file_id": source_file_id,
                },
                normal_period=normal_period,
                weighting_method=weighting,
                weighting_version=weight_vintage,
                region_type=region_type,
                region_id=region_id,
                content_hash=content_hash,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                quality_flags=flags,
                provenance_ref=provenance_ref or (f"cpc:{source_file_id}" if source_file_id else ""),
                predictive=False,
            )
        )
    return tuple(references)


__all__ = ["parse_cpc_climatology", "parse_cpc_forecast", "parse_cpc_realized"]
