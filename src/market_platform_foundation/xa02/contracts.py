"""XA-02 admitted source observation and cross-asset reference contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from market_platform_foundation.xa01.enums import AnalyticalDomain

from .enums import (
    SCHEMA_VERSION,
    AdmissionStatus,
    CrossAssetReferenceType,
    ObservationPayloadKind,
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
class ScalarMacroPayload:
    """Typed FRED scalar macro observation payload."""

    canonical_indicator_id: str
    observation_date: str
    raw_value: str | None
    normalized_value: float | None
    units: str


@dataclass(frozen=True, slots=True)
class PositioningPayload:
    """Typed CFTC positioning observation payload — reported quantities only."""

    market_report_id: str
    provider_market_id: str
    cftc_contract_market_code: str
    cftc_commodity_code: str
    market_and_exchange_names: str
    report_family: str
    position_scope: str
    participant_category: str
    position_date: str
    open_interest: int | None
    long_positions: int | None
    short_positions: int | None
    spreading_positions: int | None
    position_unit: str
    open_interest_unit: str
    source_dataset: str = ""
    source_row_id: str = ""
    content_hash: str = ""


@dataclass(frozen=True, slots=True)
class AdmissionEnvelope:
    """Source-neutral admitted observation envelope with typed payload."""

    observation_id: str
    source_provider: SourceProvider
    source_subject_id: str
    subject_type: ReferenceSubjectType
    event_time: str
    available_time: str
    retrieval_time: str
    revision_classification: RevisionClassification
    admission_status: AdmissionStatus
    provenance: SourceProvenance
    payload_kind: ObservationPayloadKind
    scalar_payload: ScalarMacroPayload | None = None
    positioning_payload: PositioningPayload | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = SCHEMA_VERSION


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


def envelope_to_dict(envelope: AdmissionEnvelope) -> dict[str, Any]:
    payload: dict[str, Any]
    if envelope.payload_kind == ObservationPayloadKind.SCALAR_MACRO:
        assert envelope.scalar_payload is not None
        payload = {
            "canonical_indicator_id": envelope.scalar_payload.canonical_indicator_id,
            "observation_date": envelope.scalar_payload.observation_date,
            "raw_value": envelope.scalar_payload.raw_value,
            "normalized_value": envelope.scalar_payload.normalized_value,
            "units": envelope.scalar_payload.units,
        }
    else:
        assert envelope.positioning_payload is not None
        pos = envelope.positioning_payload
        payload = {
            "market_report_id": pos.market_report_id,
            "provider_market_id": pos.provider_market_id,
            "cftc_contract_market_code": pos.cftc_contract_market_code,
            "cftc_commodity_code": pos.cftc_commodity_code,
            "market_and_exchange_names": pos.market_and_exchange_names,
            "report_family": pos.report_family,
            "position_scope": pos.position_scope,
            "participant_category": pos.participant_category,
            "position_date": pos.position_date,
            "open_interest": pos.open_interest,
            "long_positions": pos.long_positions,
            "short_positions": pos.short_positions,
            "spreading_positions": pos.spreading_positions,
            "position_unit": pos.position_unit,
            "open_interest_unit": pos.open_interest_unit,
            "source_dataset": pos.source_dataset,
            "source_row_id": pos.source_row_id,
            "content_hash": pos.content_hash,
        }
    return {
        "schema_version": envelope.schema_version,
        "observation_id": envelope.observation_id,
        "source_provider": envelope.source_provider.value,
        "source_subject_id": envelope.source_subject_id,
        "subject_type": envelope.subject_type.value,
        "event_time": envelope.event_time,
        "available_time": envelope.available_time,
        "retrieval_time": envelope.retrieval_time,
        "revision_classification": envelope.revision_classification.value,
        "admission_status": envelope.admission_status.value,
        "payload_kind": envelope.payload_kind.value,
        "payload": payload,
        "quality_flags": list(envelope.quality_flags),
        "provenance": {
            "provider": envelope.provenance.provider.value,
            "series_id": envelope.provenance.series_id,
            "api_version": envelope.provenance.api_version,
            "provenance_ref": envelope.provenance.provenance_ref,
            "retrieved_time": envelope.provenance.retrieved_time,
            "observed_time": envelope.provenance.observed_time,
            "ingested_time": envelope.provenance.ingested_time,
            "source_publication_time": envelope.provenance.source_publication_time,
            "provider_first_observed_time": envelope.provenance.provider_first_observed_time,
            "realtime_start": envelope.provenance.realtime_start,
            "realtime_end": envelope.provenance.realtime_end,
            "vintage_date": envelope.provenance.vintage_date,
            "revision_number": envelope.provenance.revision_number,
        },
    }


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
