"""XA-02 admitted source observation and cross-asset reference contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from market_platform_foundation.xa01.enums import AnalyticalDomain

from .enums import (
    SCHEMA_VERSION,
    AdmissionStatus,
    CrossAssetReferenceType,
    ReferenceSubjectType,
    ReferenceTargetType,
    RevisionClassification,
    SourceProvider,
)


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    provider: SourceProvider
    series_id: str
    api_version: str
    provenance_ref: str
    retrieved_time: str
    observed_time: str
    ingested_time: str
    source_publication_time: str = ""
    provider_first_observed_time: str = ""
    realtime_start: str = ""
    realtime_end: str = ""
    vintage_date: str = ""
    revision_number: int = 0


@dataclass(frozen=True, slots=True)
class AdmittedObservation:
    observation_id: str
    canonical_indicator_id: str
    observation_date: str
    raw_value: str | None
    normalized_value: float | None
    units: str
    event_time: str
    available_time: str
    retrieval_time: str
    revision_classification: RevisionClassification
    admission_status: AdmissionStatus
    provenance: SourceProvenance
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class CrossAssetReferenceRelationship:
    relationship_id: str
    subject_type: ReferenceSubjectType
    subject_id: str
    relationship_type: CrossAssetReferenceType
    target_type: ReferenceTargetType
    target_xa_canonical_id: str
    domain: AnalyticalDomain
    provenance_ref: str = ""
    valid_from: str = ""
    valid_to: str = ""
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class IndicatorAdmissionSummary:
    canonical_indicator_id: str
    provider_series_id: str
    title: str
    units: str
    observation_count: int
    relationship_count: int
    revision_classifications: tuple[RevisionClassification, ...]


def observation_to_dict(obs: AdmittedObservation) -> dict[str, Any]:
    return {
        "schema_version": obs.schema_version,
        "observation_id": obs.observation_id,
        "canonical_indicator_id": obs.canonical_indicator_id,
        "observation_date": obs.observation_date,
        "raw_value": obs.raw_value,
        "normalized_value": obs.normalized_value,
        "units": obs.units,
        "event_time": obs.event_time,
        "available_time": obs.available_time,
        "retrieval_time": obs.retrieval_time,
        "revision_classification": obs.revision_classification.value,
        "admission_status": obs.admission_status.value,
        "quality_flags": list(obs.quality_flags),
        "provenance": {
            "provider": obs.provenance.provider.value,
            "series_id": obs.provenance.series_id,
            "api_version": obs.provenance.api_version,
            "provenance_ref": obs.provenance.provenance_ref,
            "retrieved_time": obs.provenance.retrieved_time,
            "observed_time": obs.provenance.observed_time,
            "ingested_time": obs.provenance.ingested_time,
            "source_publication_time": obs.provenance.source_publication_time,
            "provider_first_observed_time": obs.provenance.provider_first_observed_time,
            "realtime_start": obs.provenance.realtime_start,
            "realtime_end": obs.provenance.realtime_end,
            "vintage_date": obs.provenance.vintage_date,
            "revision_number": obs.provenance.revision_number,
        },
    }


def relationship_to_dict(rel: CrossAssetReferenceRelationship) -> dict[str, Any]:
    return {
        "schema_version": rel.schema_version,
        "relationship_id": rel.relationship_id,
        "subject_type": rel.subject_type.value,
        "subject_id": rel.subject_id,
        "relationship_type": rel.relationship_type.value,
        "target_type": rel.target_type.value,
        "target_xa_canonical_id": rel.target_xa_canonical_id,
        "domain": rel.domain.value,
        "provenance_ref": rel.provenance_ref,
        "valid_from": rel.valid_from,
        "valid_to": rel.valid_to,
    }
