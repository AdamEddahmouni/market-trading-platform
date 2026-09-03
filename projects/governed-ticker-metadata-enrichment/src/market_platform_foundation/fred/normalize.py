"""Normalization of FRED V1/V2 payloads into canonical macro observations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .availability import derive_v1_availability, derive_v2_snapshot_availability
from .contracts import MacroObservation
from .quality import FredQualityFlag
from .registry import MacroRegistryEntry, lookup_series


def parse_fred_value(raw: str | None) -> tuple[str | None, float | None, tuple[str, ...]]:
    if raw is None or raw == "" or raw == ".":
        return None, None, (FredQualityFlag.MISSING_VALUE.value,)
    text = str(raw)
    try:
        return text, float(Decimal(text)), ()
    except (InvalidOperation, ValueError):
        return text, None, (FredQualityFlag.SCHEMA_CHANGED.value,)


def normalize_v1_observation_row(
    row: dict[str, Any],
    *,
    entry: MacroRegistryEntry,
    retrieved_time: str,
    observed_time: str,
    ingested_time: str = "",
    api_version: str = "v1",
    copyright_id: str = "",
    source_publication_time: str = "",
) -> MacroObservation:
    raw_value, normalized_value, value_flags = parse_fred_value(str(row.get("value", ".")))
    realtime_start = str(row.get("realtime_start", ""))
    realtime_end = str(row.get("realtime_end", ""))
    vintage_date = str(row.get("vintage_date", row.get("date", "")))
    observation_date = str(row.get("date", ""))
    (
        available_time,
        availability_precision,
        knowledge_start_date,
        knowledge_end_date,
        provider_first_observed_time,
        availability_flags,
    ) = derive_v1_availability(
        realtime_start=realtime_start,
        realtime_end=realtime_end,
        observed_time=observed_time,
        source_publication_time=source_publication_time,
    )
    flags = tuple(dict.fromkeys((*value_flags, *availability_flags)))
    return MacroObservation(
        canonical_indicator_id=entry.canonical_indicator_id,
        series_id=entry.fred_series_id,
        observation_date=observation_date,
        raw_value=raw_value,
        normalized_value=normalized_value,
        frequency=entry.frequency,
        units=entry.units,
        seasonal_adjustment=entry.seasonal_adjustment,
        source_agency=entry.original_source,
        fred_release_id=entry.fred_release_id,
        realtime_start=realtime_start,
        realtime_end=realtime_end,
        vintage_date=vintage_date,
        knowledge_start_date=knowledge_start_date,
        knowledge_end_date=knowledge_end_date,
        source_publication_time=source_publication_time,
        provider_first_observed_time=provider_first_observed_time,
        available_time=available_time,
        availability_precision=availability_precision,
        observed_time=observed_time or provider_first_observed_time,
        retrieved_time=retrieved_time,
        ingested_time=ingested_time or retrieved_time,
        provider="FRED",
        api_version=api_version,
        copyright_id=copyright_id or entry.copyright_id,
        usage_rights=entry.usage_rights,
        quality_flags=flags,
        provenance_ref=f"fred.v1:{entry.fred_series_id}",
        lifecycle="OBSERVED",
        predictive=False,
    )


def normalize_v2_observation_row(
    row: dict[str, Any],
    *,
    retrieved_time: str,
    observed_time: str,
) -> MacroObservation | None:
    series_id = str(row.get("series_id", ""))
    entry = lookup_series(series_id)
    if entry is None:
        return None
    raw_value, normalized_value, value_flags = parse_fred_value(str(row.get("value", ".")))
    observation_date = str(row.get("date", ""))
    last_updated = str(row.get("last_updated", ""))
    copyright_id = str(row.get("copyright_id", entry.copyright_id))
    (
        available_time,
        availability_precision,
        series_last_updated,
        snapshot_observed_time,
        snapshot_flags,
    ) = derive_v2_snapshot_availability(
        last_updated=last_updated,
        observed_time=observed_time,
        retrieved_time=retrieved_time,
    )
    flags = tuple(dict.fromkeys((*value_flags, *snapshot_flags)))
    return MacroObservation(
        canonical_indicator_id=entry.canonical_indicator_id,
        series_id=series_id,
        observation_date=observation_date,
        raw_value=raw_value,
        normalized_value=normalized_value,
        frequency=entry.frequency,
        units=entry.units,
        seasonal_adjustment=entry.seasonal_adjustment,
        source_agency=entry.original_source,
        fred_release_id=entry.fred_release_id,
        realtime_start="",
        realtime_end="",
        vintage_date="",
        series_last_updated=series_last_updated,
        snapshot_observed_time=snapshot_observed_time,
        available_time=available_time,
        availability_precision=availability_precision,
        observed_time=snapshot_observed_time,
        retrieved_time=retrieved_time,
        ingested_time=retrieved_time,
        provider="FRED",
        api_version="v2",
        copyright_id=copyright_id,
        usage_rights=entry.usage_rights,
        quality_flags=flags,
        provenance_ref=f"fred.v2:{series_id}",
        lifecycle="OBSERVED",
        predictive=False,
    )


__all__ = [
    "normalize_v1_observation_row",
    "normalize_v2_observation_row",
    "parse_fred_value",
]
