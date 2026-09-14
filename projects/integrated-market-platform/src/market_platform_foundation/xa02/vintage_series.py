"""Vintage-aware series structures and PIT selection for admitted XA-02 observations.

Does not persist. Reuses FRED knowledge-interval policy; does not wrap or replace
``fred.store``, ``runtime.bitemporal_store``, or XA-04 catalog persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from market_platform_foundation.fred.availability import (
    AvailabilityPrecision,
    is_date_only,
    knowledge_interval_contains,
    normalize_knowledge_end,
)
from market_platform_foundation.fred.quality import FredQualityFlag

from .contracts import AdmittedObservation, SourceProvenance
from .enums import AdmissionStatus, RevisionClassification, SourceProvider
from .identity import vintage_identity_from_admitted


class PitSelectionOutcome(StrEnum):
    SELECTED = "SELECTED"
    PIT_UNAVAILABLE = "PIT_UNAVAILABLE"
    SNAPSHOT_EXCLUDED = "SNAPSHOT_EXCLUDED"
    DATE_ONLY_INTRADAY = "DATE_ONLY_INTRADAY"


@dataclass(frozen=True, slots=True)
class SeriesIdentity:
    """One economic series at one valid-time observation date."""

    canonical_indicator_id: str
    provider_series_id: str
    observation_date: str
    source_provider: SourceProvider


@dataclass(frozen=True, slots=True)
class VintageRecord:
    """One ALFRED-style revision vintage of a series observation."""

    vintage_identity: str
    observation: AdmittedObservation
    knowledge_start: str
    knowledge_end: str
    availability_precision: str
    revision_classification: RevisionClassification


@dataclass(frozen=True, slots=True)
class VintageAwareSeries:
    """Ordered vintages for one series identity. Not a store."""

    identity: SeriesIdentity
    vintages: tuple[VintageRecord, ...]


@dataclass(frozen=True, slots=True)
class PointInTimeSelection:
    """Result of ``series_as_of`` — selected vintage plus provenance, or fail-closed."""

    series: SeriesIdentity
    decision_time: str
    outcome: PitSelectionOutcome
    selected: VintageRecord | None
    quality_flags: tuple[str, ...]
    provenance: SourceProvenance | None


def _knowledge_start(obs: AdmittedObservation) -> str:
    return (
        obs.provenance.realtime_start
        or obs.available_time
        or obs.provenance.vintage_date
        or ""
    ).strip()


def _knowledge_end(obs: AdmittedObservation) -> str:
    return normalize_knowledge_end(obs.provenance.realtime_end)


def _availability_precision(obs: AdmittedObservation, knowledge_start: str) -> str:
    if obs.revision_classification == RevisionClassification.LATEST_ONLY:
        return AvailabilityPrecision.SNAPSHOT.value
    if knowledge_start and is_date_only(knowledge_start):
        return AvailabilityPrecision.DATE_ONLY.value
    if knowledge_start:
        return AvailabilityPrecision.TIMESTAMP.value
    return AvailabilityPrecision.DATE_ONLY.value


def _vintage_record(obs: AdmittedObservation) -> VintageRecord:
    start = _knowledge_start(obs)
    return VintageRecord(
        vintage_identity=vintage_identity_from_admitted(obs),
        observation=obs,
        knowledge_start=start,
        knowledge_end=_knowledge_end(obs),
        availability_precision=_availability_precision(obs, start),
        revision_classification=obs.revision_classification,
    )


def _series_key(obs: AdmittedObservation) -> tuple[str, str, str, SourceProvider]:
    return (
        obs.canonical_indicator_id,
        obs.provenance.series_id,
        obs.observation_date,
        obs.provenance.provider,
    )


def build_vintage_series(
    observations: tuple[AdmittedObservation, ...] | list[AdmittedObservation],
) -> tuple[VintageAwareSeries, ...]:
    """Group admitted observations into vintage-aware series. No I/O."""

    buckets: dict[tuple[str, str, str, SourceProvider], list[VintageRecord]] = {}
    for obs in observations:
        if obs.admission_status != AdmissionStatus.ADMITTED:
            continue
        buckets.setdefault(_series_key(obs), []).append(_vintage_record(obs))

    series_list: list[VintageAwareSeries] = []
    for key, vintages in sorted(buckets.items(), key=lambda item: item[0][:3]):
        ordered = tuple(
            sorted(
                vintages,
                key=lambda item: (
                    item.knowledge_start,
                    item.observation.provenance.revision_number,
                    item.vintage_identity,
                ),
            )
        )
        series_list.append(
            VintageAwareSeries(
                identity=SeriesIdentity(
                    canonical_indicator_id=key[0],
                    provider_series_id=key[1],
                    observation_date=key[2],
                    source_provider=key[3],
                ),
                vintages=ordered,
            )
        )
    return tuple(series_list)


def series_as_of(series: VintageAwareSeries, decision_time: str) -> PointInTimeSelection:
    """Select the vintage whose knowledge interval contains ``decision_time``.

    V2 / ``LATEST_ONLY`` rows are excluded from historical PIT. Date-only
    knowledge intervals fail closed on same-calendar-day intraday queries.
    ``realtime_end`` is interval end only — never first availability.
    """

    identity = series.identity
    if not decision_time or not series.vintages:
        return PointInTimeSelection(
            series=identity,
            decision_time=decision_time,
            outcome=PitSelectionOutcome.PIT_UNAVAILABLE,
            selected=None,
            quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
            provenance=None,
        )

    snapshot_present = False
    uncertain_same_day = False
    candidates: list[VintageRecord] = []
    for vintage in series.vintages:
        if vintage.revision_classification == RevisionClassification.LATEST_ONLY:
            snapshot_present = True
            continue
        if vintage.availability_precision == AvailabilityPrecision.SNAPSHOT.value:
            snapshot_present = True
            continue
        contained, flags = knowledge_interval_contains(
            decision_time,
            knowledge_start=vintage.knowledge_start,
            knowledge_end=vintage.knowledge_end,
            availability_precision=vintage.availability_precision,
            available_time=vintage.observation.available_time,
        )
        if FredQualityFlag.PIT_UNCERTAIN.value in flags:
            uncertain_same_day = True
        if contained:
            candidates.append(vintage)

    if candidates:
        selected = max(
            candidates,
            key=lambda item: (
                item.knowledge_start,
                item.observation.provenance.revision_number,
            ),
        )
        return PointInTimeSelection(
            series=identity,
            decision_time=decision_time,
            outcome=PitSelectionOutcome.SELECTED,
            selected=selected,
            quality_flags=selected.observation.quality_flags,
            provenance=selected.observation.provenance,
        )

    if uncertain_same_day:
        return PointInTimeSelection(
            series=identity,
            decision_time=decision_time,
            outcome=PitSelectionOutcome.DATE_ONLY_INTRADAY,
            selected=None,
            quality_flags=(FredQualityFlag.PIT_UNCERTAIN.value,),
            provenance=None,
        )
    if snapshot_present:
        return PointInTimeSelection(
            series=identity,
            decision_time=decision_time,
            outcome=PitSelectionOutcome.SNAPSHOT_EXCLUDED,
            selected=None,
            quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
            provenance=None,
        )
    return PointInTimeSelection(
        series=identity,
        decision_time=decision_time,
        outcome=PitSelectionOutcome.PIT_UNAVAILABLE,
        selected=None,
        quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
        provenance=None,
    )


def select_series_as_of(
    observations: tuple[AdmittedObservation, ...] | list[AdmittedObservation],
    *,
    canonical_indicator_id: str,
    observation_date: str,
    decision_time: str,
) -> PointInTimeSelection:
    """Build the matching series (if any) and run PIT selection."""

    matches = [
        series
        for series in build_vintage_series(observations)
        if series.identity.canonical_indicator_id == canonical_indicator_id
        and series.identity.observation_date == observation_date
    ]
    if not matches:
        return PointInTimeSelection(
            series=SeriesIdentity(
                canonical_indicator_id=canonical_indicator_id,
                provider_series_id="",
                observation_date=observation_date,
                source_provider=SourceProvider.FRED,
            ),
            decision_time=decision_time,
            outcome=PitSelectionOutcome.PIT_UNAVAILABLE,
            selected=None,
            quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
            provenance=None,
        )
    return series_as_of(matches[0], decision_time)


__all__ = [
    "PitSelectionOutcome",
    "PointInTimeSelection",
    "SeriesIdentity",
    "VintageAwareSeries",
    "VintageRecord",
    "build_vintage_series",
    "select_series_as_of",
    "series_as_of",
]
