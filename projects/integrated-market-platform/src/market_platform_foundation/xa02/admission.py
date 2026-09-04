"""XA-02 admission bridge from existing FRED macro observations."""

from __future__ import annotations

from market_platform_foundation.fred.availability import AvailabilityPrecision
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.quality import FredQualityFlag
from market_platform_foundation.fred.registry import lookup_canonical

from .catalog import is_admitted_indicator
from .contracts import AdmittedObservation, SourceProvenance
from .enums import AdmissionStatus, RevisionClassification, SourceProvider
from .identity import derive_observation_id_from_macro, vintage_identity_material


_SUPPORTED_UNITS = frozenset(
    {
        "percent",
        "basis points",
        "index",
        "index 1982-84=100",
        "index 2017=100",
        "index jan 2006=100",
        "currency amount",
        "level",
        "ratio",
        "number",
        "thousands of persons",
        "millions of dollars",
        "billions of dollars",
        "billions of chained 2017 dollars",
        "dollars per hour",
        "level in thousands",
        "percent of capacity",
        "thousands of units",
    }
)


def _normalize_unit_label(units: str) -> str:
    return units.strip().lower()


def validate_units(units: str) -> tuple[str, ...]:
    normalized = _normalize_unit_label(units)
    if not normalized:
        return (FredQualityFlag.SCHEMA_CHANGED.value,)
    if normalized in _SUPPORTED_UNITS or normalized.startswith("index"):
        return ()
    return (FredQualityFlag.SCHEMA_CHANGED.value,)


def classify_revision(obs: MacroObservation) -> RevisionClassification:
    if obs.api_version == "v2" or obs.availability_precision == AvailabilityPrecision.SNAPSHOT.value:
        return RevisionClassification.LATEST_ONLY
    if obs.realtime_start and (obs.knowledge_start_date or obs.vintage_date):
        if obs.revision_number > 0:
            return RevisionClassification.VINTAGE_IDENTIFIED
        return RevisionClassification.ORIGINAL_OR_AS_REPORTED
    if obs.realtime_start:
        return RevisionClassification.ORIGINAL_OR_AS_REPORTED
    if obs.series_last_updated:
        return RevisionClassification.LATEST_ONLY
    return RevisionClassification.REVISION_STATUS_UNKNOWN


def build_provenance(obs: MacroObservation) -> SourceProvenance:
    return SourceProvenance(
        provider=SourceProvider.FRED,
        series_id=obs.series_id,
        api_version=obs.api_version,
        provenance_ref=obs.provenance_ref,
        retrieved_time=obs.retrieved_time,
        observed_time=obs.observed_time,
        ingested_time=obs.ingested_time,
        source_publication_time=obs.source_publication_time,
        provider_first_observed_time=obs.provider_first_observed_time,
        realtime_start=obs.realtime_start,
        realtime_end=obs.realtime_end,
        vintage_date=obs.vintage_date,
        revision_number=obs.revision_number,
    )


def observation_event_time(obs: MacroObservation) -> str:
    return obs.observation_date


def observation_available_time(obs: MacroObservation) -> str:
    return obs.available_time or obs.knowledge_start_date or obs.realtime_start or ""


def eligible_at_decision_time(obs: AdmittedObservation, decision_time: str) -> bool:
    if not obs.available_time:
        return False
    return obs.available_time <= decision_time


def admit_macro_observation(obs: MacroObservation) -> AdmittedObservation:
    if not is_admitted_indicator(obs.canonical_indicator_id):
        from .errors import Xa02Error, Xa02ErrorCode

        raise Xa02Error(
            Xa02ErrorCode.NOT_ADMITTED_SERIES,
            "indicator is outside XA-02 admitted catalog",
            {"canonical_indicator_id": obs.canonical_indicator_id},
        )
    entry = lookup_canonical(obs.canonical_indicator_id)
    if entry is None:
        from .errors import Xa02Error, Xa02ErrorCode

        raise Xa02Error(
            Xa02ErrorCode.UNKNOWN_INDICATOR,
            "canonical indicator not found in FRED registry",
            {"canonical_indicator_id": obs.canonical_indicator_id},
        )
    if entry.fred_series_id != obs.series_id:
        from .errors import Xa02Error, Xa02ErrorCode

        raise Xa02Error(
            Xa02ErrorCode.OBSERVATION_CONFLICT,
            "provider series_id does not match canonical registry mapping",
            {
                "canonical_indicator_id": obs.canonical_indicator_id,
                "series_id": obs.series_id,
                "expected_series_id": entry.fred_series_id,
            },
        )
    unit_flags = validate_units(obs.units)
    quality_flags = tuple(dict.fromkeys((*obs.quality_flags, *unit_flags)))
    if unit_flags:
        from .errors import Xa02Error, Xa02ErrorCode

        raise Xa02Error(
            Xa02ErrorCode.UNSUPPORTED_UNIT,
            "unsupported observation unit",
            {"units": obs.units, "canonical_indicator_id": obs.canonical_indicator_id},
        )
    return AdmittedObservation(
        observation_id=derive_observation_id_from_macro(obs),
        canonical_indicator_id=obs.canonical_indicator_id,
        observation_date=obs.observation_date,
        raw_value=obs.raw_value,
        normalized_value=obs.normalized_value,
        units=obs.units,
        event_time=observation_event_time(obs),
        available_time=observation_available_time(obs),
        retrieval_time=obs.retrieved_time,
        revision_classification=classify_revision(obs),
        admission_status=AdmissionStatus.ADMITTED,
        provenance=build_provenance(obs),
        quality_flags=quality_flags,
    )


def observations_equivalent_for_identity(left: AdmittedObservation, right: AdmittedObservation) -> bool:
    return (
        left.observation_id == right.observation_id
        and left.canonical_indicator_id == right.canonical_indicator_id
        and left.observation_date == right.observation_date
        and left.raw_value == right.raw_value
        and left.normalized_value == right.normalized_value
        and left.units == right.units
        and left.available_time == right.available_time
        and left.revision_classification == right.revision_classification
    )
