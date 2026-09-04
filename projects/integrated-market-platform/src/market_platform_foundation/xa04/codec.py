"""Canonical XA catalog record codec (IMP-XA-04)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from market_platform_foundation.xa01.contracts import (
    CanonicalInstrumentIdentity,
    DenominationMetadata,
    DomainParticipation,
    ExternalIdentifier,
    InstrumentDescriptor,
    InstrumentRecord,
    InstrumentRelationship,
    record_to_dict,
)
from market_platform_foundation.xa01.enums import (
    AnalyticalDomain,
    ExternalIdentifierType,
    InstrumentKind,
    PriceUnitKind,
    RelationshipType,
    XaAssetClass,
)
from market_platform_foundation.xa02.contracts import (
    AdmittedObservation,
    AdmissionEnvelope,
    CrossAssetReferenceRelationship,
    envelope_to_dict,
    observation_to_dict,
    relationship_to_dict,
)
from market_platform_foundation.xa02.enums import (
    AdmissionStatus,
    CrossAssetReferenceType,
    ObservationPayloadKind,
    ReferenceSubjectType,
    ReferenceTargetType,
    RevisionClassification,
    SourceProvider,
)
from market_platform_foundation.xa02.contracts import SourceProvenance, ScalarMacroPayload, PositioningPayload

from .errors import RepositorySerializationError, RepositoryValidationError

PERSISTENCE_METADATA_FIELDS = frozenset({"_id"})
MONGO_SCHEMA_PLAN_VERSION = 1


class CatalogRecordKind(StrEnum):
    INSTRUMENT = "instrument"
    SCALAR_OBSERVATION = "scalar_observation"
    ADMISSION_ENVELOPE = "admission_envelope"
    CROSS_ASSET_RELATIONSHIP = "cross_asset_relationship"


CatalogRecordT = InstrumentRecord | AdmittedObservation | AdmissionEnvelope | CrossAssetReferenceRelationship


@dataclass(frozen=True, slots=True)
class CatalogRecordCodec:
    kind: CatalogRecordKind
    collection_name: str
    id_field: str
    to_dict: Callable[[Any], dict[str, Any]]
    from_dict: Callable[[dict[str, Any]], Any]


def _provenance_from_dict(body: dict[str, Any]) -> SourceProvenance:
    return SourceProvenance(
        provider=SourceProvider(str(body["provider"])),
        series_id=str(body.get("series_id", "")),
        api_version=str(body.get("api_version", "")),
        provenance_ref=str(body.get("provenance_ref", "")),
        retrieved_time=str(body.get("retrieved_time", "")),
        observed_time=str(body.get("observed_time", "")),
        ingested_time=str(body.get("ingested_time", "")),
        source_publication_time=str(body.get("source_publication_time", "")),
        provider_first_observed_time=str(body.get("provider_first_observed_time", "")),
        realtime_start=str(body.get("realtime_start", "")),
        realtime_end=str(body.get("realtime_end", "")),
        vintage_date=str(body.get("vintage_date", "")),
        revision_number=int(body.get("revision_number", 0)),
    )


def instrument_record_from_dict(body: dict[str, Any]) -> InstrumentRecord:
    identity = CanonicalInstrumentIdentity(
        canonical_id=str(body["canonical_id"]),
        instrument_kind=InstrumentKind(str(body["instrument_kind"])),
        asset_class=XaAssetClass(str(body["asset_class"])),
        identity_profile=str(body["identity_profile"]),
        identity_key={str(k): str(v) for k, v in dict(body.get("identity_key", {})).items()},
    )
    denomination_body = dict(body.get("denomination", {}))
    descriptor = InstrumentDescriptor(
        identity=identity,
        display_name=str(body.get("display_name", "")),
        venue_id=str(body.get("venue_id", "")),
        exchange=str(body.get("exchange", "")),
        denomination=DenominationMetadata(
            currency=str(denomination_body.get("currency", "USD")),
            price_unit_kind=PriceUnitKind(str(denomination_body.get("price_unit_kind", PriceUnitKind.CURRENCY_PER_SHARE.value))),
            contract_multiplier=str(denomination_body.get("contract_multiplier", "1")),
            tick_size=str(denomination_body.get("tick_size", "")),
            quantity_unit=str(denomination_body.get("quantity_unit", "")),
        ),
        sovereign_issuer=str(body.get("sovereign_issuer", "")),
        security_type=str(body.get("security_type", "")),
        issue_date=str(body.get("issue_date", "")),
        maturity_date=str(body.get("maturity_date", "")),
        coupon=str(body.get("coupon", "")),
        commodity_code=str(body.get("commodity_code", "")),
        contract_month=str(body.get("contract_month", "")),
        expiration=str(body.get("expiration", "")),
        strike=str(body.get("strike", "")),
        call_put=str(body.get("call_put", "")),
        base_currency=str(body.get("base_currency", "")),
        quote_currency=str(body.get("quote_currency", "")),
        schema_version=int(body.get("schema_version", 1)),
    )
    domains = tuple(
        DomainParticipation(
            domain=AnalyticalDomain(str(item["domain"])),
            valid_from=str(item.get("valid_from", "")),
            valid_to=str(item.get("valid_to", "")),
        )
        for item in body.get("analytical_domains", [])
    )
    aliases = tuple(
        ExternalIdentifier(
            identifier_type=ExternalIdentifierType(str(item["identifier_type"])),
            alias_value=str(item["alias_value"]),
            provider_id=str(item.get("provider_id", "")),
            venue_id=str(item.get("venue_id", "")),
            valid_from=str(item.get("valid_from", "")),
            valid_to=str(item.get("valid_to", "")),
        )
        for item in body.get("aliases", [])
    )
    relationships = tuple(
        InstrumentRelationship(
            relationship_type=RelationshipType(str(item["relationship_type"])),
            from_canonical_id=str(item["from_canonical_id"]),
            to_canonical_id=str(item["to_canonical_id"]),
            schema_version=int(item.get("schema_version", 1)),
        )
        for item in body.get("relationships", [])
    )
    return InstrumentRecord(
        descriptor=descriptor,
        analytical_domains=domains,
        aliases=aliases,
        relationships=relationships,
    )


def admitted_observation_from_dict(body: dict[str, Any]) -> AdmittedObservation:
    provenance = _provenance_from_dict(dict(body.get("provenance", {})))
    return AdmittedObservation(
        observation_id=str(body["observation_id"]),
        canonical_indicator_id=str(body["canonical_indicator_id"]),
        observation_date=str(body["observation_date"]),
        raw_value=body.get("raw_value"),
        normalized_value=body.get("normalized_value"),
        units=str(body.get("units", "")),
        event_time=str(body.get("event_time", "")),
        available_time=str(body.get("available_time", "")),
        retrieval_time=str(body.get("retrieval_time", "")),
        revision_classification=RevisionClassification(str(body["revision_classification"])),
        admission_status=AdmissionStatus(str(body["admission_status"])),
        provenance=provenance,
        quality_flags=tuple(str(item) for item in body.get("quality_flags", [])),
        schema_version=int(body.get("schema_version", 1)),
    )


def admission_envelope_from_dict(body: dict[str, Any]) -> AdmissionEnvelope:
    payload_kind = ObservationPayloadKind(str(body["payload_kind"]))
    payload = dict(body.get("payload", {}))
    scalar_payload: ScalarMacroPayload | None = None
    positioning_payload: PositioningPayload | None = None
    if payload_kind == ObservationPayloadKind.SCALAR_MACRO:
        scalar_payload = ScalarMacroPayload(
            canonical_indicator_id=str(payload["canonical_indicator_id"]),
            observation_date=str(payload["observation_date"]),
            raw_value=payload.get("raw_value"),
            normalized_value=payload.get("normalized_value"),
            units=str(payload.get("units", "")),
        )
    elif payload_kind == ObservationPayloadKind.POSITIONING_STRUCTURED:
        positioning_payload = PositioningPayload(
            market_report_id=str(payload["market_report_id"]),
            provider_market_id=str(payload.get("provider_market_id", "")),
            cftc_contract_market_code=str(payload.get("cftc_contract_market_code", "")),
            cftc_commodity_code=str(payload.get("cftc_commodity_code", "")),
            market_and_exchange_names=str(payload.get("market_and_exchange_names", "")),
            report_family=str(payload.get("report_family", "")),
            position_scope=str(payload.get("position_scope", "")),
            participant_category=str(payload.get("participant_category", "")),
            position_date=str(payload.get("position_date", "")),
            open_interest=payload.get("open_interest"),
            long_positions=payload.get("long_positions"),
            short_positions=payload.get("short_positions"),
            spreading_positions=payload.get("spreading_positions"),
            position_unit=str(payload.get("position_unit", "")),
            open_interest_unit=str(payload.get("open_interest_unit", "")),
            source_dataset=str(payload.get("source_dataset", "")),
            source_row_id=str(payload.get("source_row_id", "")),
            content_hash=str(payload.get("content_hash", "")),
        )
    else:
        raise RepositoryValidationError(
            "UNSUPPORTED_PAYLOAD_KIND",
            details={"payload_kind": payload_kind.value},
        )
    return AdmissionEnvelope(
        observation_id=str(body["observation_id"]),
        source_provider=SourceProvider(str(body["source_provider"])),
        source_subject_id=str(body["source_subject_id"]),
        subject_type=ReferenceSubjectType(str(body["subject_type"])),
        event_time=str(body.get("event_time", "")),
        available_time=str(body.get("available_time", "")),
        retrieval_time=str(body.get("retrieval_time", "")),
        revision_classification=RevisionClassification(str(body["revision_classification"])),
        admission_status=AdmissionStatus(str(body["admission_status"])),
        provenance=_provenance_from_dict(dict(body.get("provenance", {}))),
        payload_kind=payload_kind,
        scalar_payload=scalar_payload,
        positioning_payload=positioning_payload,
        quality_flags=tuple(str(item) for item in body.get("quality_flags", [])),
        schema_version=int(body.get("schema_version", 1)),
    )


def cross_asset_relationship_from_dict(body: dict[str, Any]) -> CrossAssetReferenceRelationship:
    return CrossAssetReferenceRelationship(
        relationship_id=str(body["relationship_id"]),
        subject_type=ReferenceSubjectType(str(body["subject_type"])),
        subject_id=str(body["subject_id"]),
        relationship_type=CrossAssetReferenceType(str(body["relationship_type"])),
        target_type=ReferenceTargetType(str(body["target_type"])),
        target_xa_canonical_id=str(body["target_xa_canonical_id"]),
        domain=AnalyticalDomain(str(body["domain"])),
        provenance_ref=str(body.get("provenance_ref", "")),
        valid_from=str(body.get("valid_from", "")),
        valid_to=str(body.get("valid_to", "")),
        schema_version=int(body.get("schema_version", 1)),
    )


CATALOG_RECORD_CODECS: tuple[CatalogRecordCodec, ...] = (
    CatalogRecordCodec(
        CatalogRecordKind.INSTRUMENT,
        "xa_instruments",
        "canonical_id",
        record_to_dict,
        instrument_record_from_dict,
    ),
    CatalogRecordCodec(
        CatalogRecordKind.SCALAR_OBSERVATION,
        "xa_scalar_observations",
        "observation_id",
        observation_to_dict,
        admitted_observation_from_dict,
    ),
    CatalogRecordCodec(
        CatalogRecordKind.ADMISSION_ENVELOPE,
        "xa_admission_envelopes",
        "observation_id",
        envelope_to_dict,
        admission_envelope_from_dict,
    ),
    CatalogRecordCodec(
        CatalogRecordKind.CROSS_ASSET_RELATIONSHIP,
        "xa_cross_asset_relationships",
        "relationship_id",
        relationship_to_dict,
        cross_asset_relationship_from_dict,
    ),
)

_CODEC_BY_KIND = {codec.kind: codec for codec in CATALOG_RECORD_CODECS}
_CODEC_BY_COLLECTION = {codec.collection_name: codec for codec in CATALOG_RECORD_CODECS}
_CODEC_BY_TYPE = {
    InstrumentRecord: _CODEC_BY_KIND[CatalogRecordKind.INSTRUMENT],
    AdmittedObservation: _CODEC_BY_KIND[CatalogRecordKind.SCALAR_OBSERVATION],
    AdmissionEnvelope: _CODEC_BY_KIND[CatalogRecordKind.ADMISSION_ENVELOPE],
    CrossAssetReferenceRelationship: _CODEC_BY_KIND[CatalogRecordKind.CROSS_ASSET_RELATIONSHIP],
}
def codec_for_record(record: CatalogRecordT) -> CatalogRecordCodec:
    codec = _CODEC_BY_TYPE.get(type(record))
    if codec is None:
        raise RepositorySerializationError(
            "UNSUPPORTED_RECORD_TYPE",
            details={"record_type": type(record).__name__},
        )
    return codec


def canonical_semantic_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_clean = {k: v for k, v in left.items() if k not in PERSISTENCE_METADATA_FIELDS}
    right_clean = {k: v for k, v in right.items() if k not in PERSISTENCE_METADATA_FIELDS}
    return json.dumps(left_clean, sort_keys=True, separators=(",", ":")) == json.dumps(
        right_clean, sort_keys=True, separators=(",", ":")
    )


def encode_document(record: CatalogRecordT) -> dict[str, Any]:
    codec = codec_for_record(record)
    body = codec.to_dict(record)
    document = dict(body)
    document["_id"] = body[codec.id_field]
    return document


def decode_document(document: dict[str, Any], codec: CatalogRecordCodec) -> CatalogRecordT:
    body = {k: v for k, v in document.items() if k not in PERSISTENCE_METADATA_FIELDS}
    try:
        return codec.from_dict(body)
    except (KeyError, TypeError, ValueError) as exc:
        raise RepositoryValidationError(
            f"DOMAIN_DESERIALIZATION_FAILED:{codec.kind.value}",
            details={"reason": str(exc)},
        ) from exc
