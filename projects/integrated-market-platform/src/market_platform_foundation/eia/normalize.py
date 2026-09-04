"""Normalize EIA API v2 rows into canonical energy observations."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from .contracts import (
    EnergyCommodity,
    EnergyFundamentalObservation,
    EnergyHistoryClass,
    EnergyMetricClass,
    EnergyReleaseFamily,
)
from .quality import EiaQualityFlag
from .registry import FULL_REGISTRY, RegistryEntry, lookup_canonical
from .release_schedule import publication_time_utc, release_for_period_end


_WITHHELD_VALUES = {"W", "NA", "N/A", "-", "--", ""}


def parse_eia_value(raw: Any) -> tuple[str | None, float | None, tuple[str, ...]]:
    flags: list[str] = []
    if raw is None:
        flags.append(EiaQualityFlag.MISSING_VALUE.value)
        return None, None, tuple(flags)
    text = str(raw).strip()
    if text.upper() in _WITHHELD_VALUES:
        if text.upper() == "W":
            flags.append(EiaQualityFlag.WITHHELD.value)
        else:
            flags.append(EiaQualityFlag.MISSING_VALUE.value)
        return text, None, tuple(flags)
    try:
        return text, float(text), tuple(flags)
    except ValueError:
        flags.append(EiaQualityFlag.MISSING_VALUE.value)
        return text, None, tuple(flags)


def _content_hash(entry: RegistryEntry, period_end: str, raw_value: str | None) -> str:
    payload = {
        "canonical_indicator_id": entry.canonical_indicator_id,
        "series": entry.series,
        "period_end": period_end,
        "raw_value": raw_value,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:16]


def _resolve_entry(row: dict[str, Any]) -> RegistryEntry | None:
    series = str(row.get("series") or row.get("seriesId") or row.get("series-id") or "").strip()
    if not series:
        return None
    for entry in FULL_REGISTRY.values():
        if entry.series == series:
            return entry
    return None


def normalize_api_row(
    row: dict[str, Any],
    *,
    entry: RegistryEntry | None = None,
    observed_time: str,
    retrieved_time: str,
    api_first_observed_time: str = "",
    history_class: EnergyHistoryClass = EnergyHistoryClass.CURRENT_API_HISTORY,
    revision_status: str = "",
) -> EnergyFundamentalObservation | None:
    entry = entry or _resolve_entry(row)
    if entry is None:
        return None

    period_end = str(row.get("period") or row.get("date") or "")[:10]
    if not period_end:
        return None

    raw_value, normalized_value, value_flags = parse_eia_value(row.get("value"))
    flags = list(value_flags)
    release = release_for_period_end(
        date.fromisoformat(period_end),
        entry.release_family,
    )
    scheduled_release_time = publication_time_utc(release) if release else ""
    available_time = api_first_observed_time or scheduled_release_time or observed_time
    if not release:
        flags.append(EiaQualityFlag.PIT_UNCERTAIN.value)

    if entry.metric_class == EnergyMetricClass.STOCK and entry.unit.endswith("per Day"):
        flags.append(EiaQualityFlag.METRIC_CLASS_MISMATCH.value)
    if entry.metric_class == EnergyMetricClass.FLOW_RATE and entry.unit == "Thousand Barrels" and "per Day" not in entry.unit:
        flags.append(EiaQualityFlag.METRIC_CLASS_MISMATCH.value)

    return EnergyFundamentalObservation(
        canonical_indicator_id=entry.canonical_indicator_id,
        commodity=entry.commodity,
        metric_class=entry.metric_class,
        region=entry.region,
        product=entry.product,
        period_start=period_end,
        period_end=period_end,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=entry.unit,
        release_family=entry.release_family,
        source_route=entry.route,
        source_series=entry.series,
        source_facets={"series": entry.series},
        scheduled_release_time=scheduled_release_time,
        available_time=available_time,
        availability_precision="TIMESTAMP" if "T" in available_time else "DATE_ONLY",
        provider_first_observed_time=api_first_observed_time or available_time,
        retrieved_time=retrieved_time,
        ingested_time=observed_time,
        source_version=str(row.get("api_version") or "v2"),
        content_hash=_content_hash(entry, period_end, raw_value),
        estimate_status=entry.estimate_status,
        revision_status=revision_status,
        history_class=history_class,
        pit_confidence=entry.pit_confidence,
        quality_flags=tuple(dict.fromkeys(flags)),
        provenance_ref=f"eia:{entry.route}:{entry.series}",
        lifecycle="OBSERVED",
        predictive=False,
    )


def normalize_api_rows(
    rows: list[dict[str, Any]],
    *,
    entry: RegistryEntry | None = None,
    observed_time: str,
    retrieved_time: str,
    api_first_observed_time: str = "",
    history_class: EnergyHistoryClass = EnergyHistoryClass.CURRENT_API_HISTORY,
) -> list[EnergyFundamentalObservation]:
    observations: list[EnergyFundamentalObservation] = []
    for row in rows:
        obs = normalize_api_row(
            row,
            entry=entry,
            observed_time=observed_time,
            retrieved_time=retrieved_time,
            api_first_observed_time=api_first_observed_time,
            history_class=history_class,
        )
        if obs is not None:
            observations.append(obs)
    return observations


def assert_metric_class(entry: RegistryEntry, expected: EnergyMetricClass) -> bool:
    return entry.metric_class == expected


def assert_region_distinct(a: str, b: str) -> bool:
    return a != b


def assert_no_commercial_spr_mix(observations: list[EnergyFundamentalObservation]) -> bool:
    commercial = next((o for o in observations if o.canonical_indicator_id == "COMMERCIAL_CRUDE_STOCKS"), None)
    spr = next((o for o in observations if o.canonical_indicator_id == "SPR_CRUDE_STOCKS"), None)
    if commercial is None or spr is None:
        return True
    return commercial.region != spr.region or commercial.product != spr.product


__all__ = [
    "assert_metric_class",
    "assert_no_commercial_spr_mix",
    "assert_region_distinct",
    "lookup_canonical",
    "normalize_api_row",
    "normalize_api_rows",
    "parse_eia_value",
]
