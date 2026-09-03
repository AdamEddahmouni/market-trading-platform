"""Provider-neutral macro observation contracts for FRED / ALFRED evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MacroDomain(StrEnum):
    RATES = "RATES"
    YIELD_CURVE = "YIELD_CURVE"
    INFLATION = "INFLATION"
    LABOR = "LABOR"
    GROWTH = "GROWTH"
    LIQUIDITY = "LIQUIDITY"
    CREDIT = "CREDIT"
    FINANCIAL_CONDITIONS = "FINANCIAL_CONDITIONS"
    USD = "USD"


class MacroFeatureLayer(StrEnum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"
    PREDICTIVE_NOT_VALIDATED = "PREDICTIVE_NOT_VALIDATED"


@dataclass(frozen=True, slots=True)
class MacroObservation:
    canonical_indicator_id: str
    series_id: str

    observation_date: str
    raw_value: str | None
    normalized_value: float | None

    frequency: str
    units: str
    seasonal_adjustment: str

    source_agency: str
    fred_release_id: int | None

    realtime_start: str
    realtime_end: str
    vintage_date: str

    knowledge_start_date: str = ""
    knowledge_end_date: str = ""

    initial_release_value: str | None = None
    revision_number: int = 0

    source_publication_time: str = ""
    provider_first_observed_time: str = ""
    series_last_updated: str = ""
    snapshot_observed_time: str = ""

    available_time: str = ""
    availability_precision: str = ""
    observed_time: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""

    provider: str = "FRED"
    api_version: str = "v1"

    copyright_id: str = ""
    usage_rights: str = "internal_research"

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    schema_version: str = "macro_observation.v1"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class MacroReleaseEvent:
    release_id: int
    release_name: str
    scheduled_date: str
    first_observed_availability: str
    affected_series: tuple[str, ...]
    release_state: str
    source: str = "FRED"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class MacroIndicatorValue:
    canonical_indicator_id: str
    value: float | None
    raw_value: str | None
    observation_date: str
    available_time: str
    knowledge_age_days: int | None
    observation_age_days: int | None
    revision_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class MacroRegimeState:
    """Provider-neutral macro blocks — no composite score."""

    rates: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    yield_curve: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    inflation: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    labor: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    growth: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    liquidity: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    credit: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    financial_conditions: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    usd: dict[str, MacroIndicatorValue | None] = field(default_factory=dict)
    decision_time: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class CrossAssetRegimeContext:
    """Macro + CFTC positioning at independent source clocks."""

    macro_state: MacroRegimeState
    institutional_positioning_state: Any | None
    decision_time: str
    macro_available_time: str
    positioning_available_time: str
    staleness: dict[str, str | None] = field(default_factory=dict)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


def observation_to_dict(obs: MacroObservation) -> dict[str, Any]:
    return {
        "canonical_indicator_id": obs.canonical_indicator_id,
        "series_id": obs.series_id,
        "observation_date": obs.observation_date,
        "raw_value": obs.raw_value,
        "normalized_value": obs.normalized_value,
        "frequency": obs.frequency,
        "units": obs.units,
        "seasonal_adjustment": obs.seasonal_adjustment,
        "source_agency": obs.source_agency,
        "fred_release_id": obs.fred_release_id,
        "realtime_start": obs.realtime_start,
        "realtime_end": obs.realtime_end,
        "vintage_date": obs.vintage_date,
        "knowledge_start_date": obs.knowledge_start_date,
        "knowledge_end_date": obs.knowledge_end_date,
        "initial_release_value": obs.initial_release_value,
        "revision_number": obs.revision_number,
        "source_publication_time": obs.source_publication_time,
        "provider_first_observed_time": obs.provider_first_observed_time,
        "series_last_updated": obs.series_last_updated,
        "snapshot_observed_time": obs.snapshot_observed_time,
        "available_time": obs.available_time,
        "availability_precision": obs.availability_precision,
        "observed_time": obs.observed_time,
        "retrieved_time": obs.retrieved_time,
        "ingested_time": obs.ingested_time,
        "provider": obs.provider,
        "api_version": obs.api_version,
        "copyright_id": obs.copyright_id,
        "usage_rights": obs.usage_rights,
        "quality_flags": list(obs.quality_flags),
        "provenance_ref": obs.provenance_ref,
        "lifecycle": obs.lifecycle,
        "schema_version": obs.schema_version,
        "predictive": obs.predictive,
    }


__all__ = [
    "CrossAssetRegimeContext",
    "MacroDomain",
    "MacroFeatureLayer",
    "MacroIndicatorValue",
    "MacroObservation",
    "MacroRegimeState",
    "MacroReleaseEvent",
    "observation_to_dict",
]
