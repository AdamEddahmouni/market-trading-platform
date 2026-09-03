"""Provider-neutral physical energy fundamentals contracts for EIA evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EnergyCommodity(StrEnum):
    PETROLEUM = "PETROLEUM"
    NATURAL_GAS = "NATURAL_GAS"


class EnergyMetricClass(StrEnum):
    STOCK = "STOCK"
    FLOW_RATE = "FLOW_RATE"
    UTILIZATION = "UTILIZATION"
    RATIO = "RATIO"
    BALANCE_CHANGE = "BALANCE_CHANGE"


class EnergyReleaseFamily(StrEnum):
    WPSR = "WPSR"
    WNGSR = "WNGSR"


class EnergyHistoryClass(StrEnum):
    CURRENT_API_HISTORY = "CURRENT_API_HISTORY"
    LIVE_RELEASE_CAPTURE = "LIVE_RELEASE_CAPTURE"
    ARCHIVED_RELEASE_SNAPSHOT = "ARCHIVED_RELEASE_SNAPSHOT"


class EnergyPitConfidence(StrEnum):
    PROSPECTIVE_VERSIONED_PIT = "PROSPECTIVE_VERSIONED_PIT"
    ARCHIVE_RECONSTRUCTABLE_PIT = "ARCHIVE_RECONSTRUCTABLE_PIT"
    CURRENT_HISTORY_ONLY = "CURRENT_HISTORY_ONLY"
    HISTORICAL_PIT_UNCERTAIN = "HISTORICAL_PIT_UNCERTAIN"


class EnergyFeatureLayer(StrEnum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"
    PREDICTIVE_NOT_VALIDATED = "PREDICTIVE_NOT_VALIDATED"


@dataclass(frozen=True, slots=True)
class EnergyReleaseEvent:
    release_family: EnergyReleaseFamily
    reference_period_end: str
    scheduled_release_time: str
    official_release_time: str = ""
    provider_first_observed_time: str = ""
    api_first_observed_time: str = ""
    artifact_first_observed_time: str = ""
    available_time: str = ""
    availability_precision: str = ""
    source: str = "eia"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class EnergyFundamentalObservation:
    canonical_indicator_id: str
    commodity: EnergyCommodity
    metric_class: EnergyMetricClass
    region: str
    product: str

    period_start: str
    period_end: str

    raw_value: str | None
    normalized_value: float | None
    unit: str

    release_family: EnergyReleaseFamily
    source_route: str
    source_series: str
    source_facets: dict[str, str] = field(default_factory=dict)

    scheduled_release_time: str = ""
    available_time: str = ""
    availability_precision: str = ""
    provider_first_observed_time: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""

    source_version: str = ""
    content_hash: str = ""
    estimate_status: str = ""
    revision_status: str = ""
    history_class: EnergyHistoryClass = EnergyHistoryClass.CURRENT_API_HISTORY
    pit_confidence: EnergyPitConfidence = EnergyPitConfidence.CURRENT_HISTORY_ONLY

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class EnergyIndicatorValue:
    canonical_indicator_id: str
    value: float | None
    raw_value: str | None
    unit: str
    metric_class: EnergyMetricClass
    period_end: str
    available_time: str
    knowledge_age_days: int | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class PetroleumFundamentalsBlock:
    commercial_crude: EnergyIndicatorValue | None = None
    cushing: EnergyIndicatorValue | None = None
    spr: EnergyIndicatorValue | None = None
    gasoline: EnergyIndicatorValue | None = None
    distillate: EnergyIndicatorValue | None = None
    propane: EnergyIndicatorValue | None = None
    production: EnergyIndicatorValue | None = None
    refinery_inputs: EnergyIndicatorValue | None = None
    refinery_utilization: EnergyIndicatorValue | None = None
    crude_imports: EnergyIndicatorValue | None = None
    crude_exports: EnergyIndicatorValue | None = None
    petroleum_exports: EnergyIndicatorValue | None = None
    product_supplied: EnergyIndicatorValue | None = None
    gasoline_product_supplied: EnergyIndicatorValue | None = None
    distillate_product_supplied: EnergyIndicatorValue | None = None
    crude_days_of_supply: EnergyIndicatorValue | None = None
    regional: dict[str, EnergyIndicatorValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NaturalGasFundamentalsBlock:
    lower48_storage: EnergyIndicatorValue | None = None
    regional_storage: dict[str, EnergyIndicatorValue] = field(default_factory=dict)
    storage_change: EnergyIndicatorValue | None = None
    regional_storage_change: dict[str, EnergyIndicatorValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EnergyFundamentalsState:
    petroleum: PetroleumFundamentalsBlock = field(default_factory=PetroleumFundamentalsBlock)
    natural_gas: NaturalGasFundamentalsBlock = field(default_factory=NaturalGasFundamentalsBlock)
    decision_time: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class EnergyMarketContext:
    macro_state: Any
    institutional_positioning_state: Any | None
    physical_fundamentals_state: EnergyFundamentalsState
    decision_time: str
    macro_available_time: str
    positioning_available_time: str
    physical_available_time: str
    staleness: dict[str, str | None] = field(default_factory=dict)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    weather_demand_state: Any | None = None
    weather_available_time: str = ""


def observation_to_dict(obs: EnergyFundamentalObservation) -> dict[str, Any]:
    return {
        "canonical_indicator_id": obs.canonical_indicator_id,
        "commodity": obs.commodity.value,
        "metric_class": obs.metric_class.value,
        "region": obs.region,
        "product": obs.product,
        "period_start": obs.period_start,
        "period_end": obs.period_end,
        "raw_value": obs.raw_value,
        "normalized_value": obs.normalized_value,
        "unit": obs.unit,
        "release_family": obs.release_family.value,
        "source_route": obs.source_route,
        "source_series": obs.source_series,
        "source_facets": dict(obs.source_facets),
        "scheduled_release_time": obs.scheduled_release_time,
        "available_time": obs.available_time,
        "availability_precision": obs.availability_precision,
        "provider_first_observed_time": obs.provider_first_observed_time,
        "retrieved_time": obs.retrieved_time,
        "ingested_time": obs.ingested_time,
        "source_version": obs.source_version,
        "content_hash": obs.content_hash,
        "estimate_status": obs.estimate_status,
        "revision_status": obs.revision_status,
        "history_class": obs.history_class.value,
        "pit_confidence": obs.pit_confidence.value,
        "quality_flags": list(obs.quality_flags),
        "provenance_ref": obs.provenance_ref,
        "lifecycle": obs.lifecycle,
        "predictive": obs.predictive,
    }


__all__ = [
    "EnergyCommodity",
    "EnergyFeatureLayer",
    "EnergyFundamentalObservation",
    "EnergyFundamentalsState",
    "EnergyHistoryClass",
    "EnergyIndicatorValue",
    "EnergyMarketContext",
    "EnergyMetricClass",
    "EnergyPitConfidence",
    "EnergyReleaseEvent",
    "EnergyReleaseFamily",
    "NaturalGasFundamentalsBlock",
    "PetroleumFundamentalsBlock",
    "observation_to_dict",
]
