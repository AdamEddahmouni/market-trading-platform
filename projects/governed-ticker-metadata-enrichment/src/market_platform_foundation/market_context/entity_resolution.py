"""MC2 entity resolution — deterministic symbol linkage with fail-closed ambiguity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    EntityClaim,
    EntityResolution,
    InformationOriginClass,
    InformationSource,
    InformationSourceType,
    RawDocument,
    TimingClass,
    VerificationStatus,
    entity_id_from_symbol,
)
from ..providers.contracts import SymbolMapping

_CONFLICT_FIELDS = ("symbol", "issuer_name", "exchange", "security_type")
PRODUCER_VERSION = "market_context_entity_resolution_v1"


@dataclass(frozen=True, slots=True)
class ContextDocumentRecord:
    """Resolved raw document plus clustering metadata from fixture rows."""

    document: RawDocument
    canonical_event_type: str
    entity_resolution: EntityResolution


def resolve_entity_from_claims(
    claims: tuple[EntityClaim, ...],
    *,
    symbol_mappings: dict[str, SymbolMapping] | None = None,
) -> EntityResolution:
    """Resolve entity identity from one or more claims; fail closed on conflict."""
    if not claims:
        return EntityResolution(
            entity_id=None,
            quality_flags=(ContextQualityFlag.ENTITY_RESOLUTION_FAILED.value,),
        )

    conflicts: list[str] = []
    for field_name in _CONFLICT_FIELDS:
        values = {
            getattr(claim, field_name)
            for claim in claims
            if getattr(claim, field_name) is not None
        }
        if len(values) > 1:
            conflicts.append(field_name)

    symbols = sorted(
        {
            claim.symbol.strip().upper()
            for claim in claims
            if claim.symbol is not None and claim.symbol.strip()
        }
    )
    if not symbols:
        return EntityResolution(
            entity_id=None,
            quality_flags=(ContextQualityFlag.ENTITY_RESOLUTION_FAILED.value,),
        )

    candidate_entity_ids = tuple(entity_id_from_symbol(symbol) for symbol in symbols)
    if conflicts:
        return EntityResolution(
            entity_id=None,
            ambiguous=True,
            candidate_entity_ids=candidate_entity_ids,
            quality_flags=(ContextQualityFlag.ENTITY_AMBIGUOUS.value,),
        )

    primary_symbol = symbols[0]
    entity_id = entity_id_from_symbol(primary_symbol)
    instrument_ids: list[str] = []
    if symbol_mappings and primary_symbol in symbol_mappings:
        instrument_ids.append(symbol_mappings[primary_symbol].instrument_id)
    else:
        instrument_ids.append(primary_symbol)

    return EntityResolution(
        entity_id=entity_id,
        instrument_ids=tuple(instrument_ids),
        resolution_confidence=1.0,
        candidate_entity_ids=candidate_entity_ids,
    )


def resolve_document_entities(
    document: RawDocument,
    *,
    claims: tuple[EntityClaim, ...] | None = None,
    symbol_mappings: dict[str, SymbolMapping] | None = None,
) -> tuple[RawDocument, EntityResolution]:
    """Populate associated entity fields on a raw document."""
    resolved_claims = claims
    if resolved_claims is None:
        resolved_claims = tuple(
            EntityClaim(symbol=symbol, source_record_id=document.document_id)
            for symbol in document.associated_symbols
        )

    resolution = resolve_entity_from_claims(resolved_claims, symbol_mappings=symbol_mappings)
    quality_flags = list(document.quality_flags)
    quality_flags.extend(flag for flag in resolution.quality_flags if flag not in quality_flags)

    associated_symbols = tuple(document.associated_symbols)
    associated_entity_ids: tuple[str, ...] = ()
    if resolution.entity_id is not None:
        associated_entity_ids = (resolution.entity_id,)

    updated = RawDocument(
        document_id=document.document_id,
        source=document.source,
        title=document.title,
        body=document.body,
        url=document.url,
        revision_id=document.revision_id,
        revision_of_document_id=document.revision_of_document_id,
        origin_class=document.origin_class,
        timing_class=document.timing_class,
        associated_entity_ids=associated_entity_ids,
        associated_symbols=associated_symbols,
        event_time=document.event_time,
        available_time=document.available_time,
        ingested_time=document.ingested_time,
        provenance_ref=document.provenance_ref,
        quality_flags=tuple(quality_flags),
    )
    return updated, resolution


def _parse_source(row: dict[str, Any]) -> InformationSource:
    source = row["source"]
    return InformationSource(
        source_id=str(source["source_id"]),
        source_type=InformationSourceType(str(source["source_type"])),
        publisher=source.get("publisher"),
        author=source.get("author"),
        domain=source.get("domain"),
        primary_or_secondary=source.get("primary_or_secondary"),
        official=bool(source.get("official", False)),
        first_party=bool(source.get("first_party", False)),
        source_tier=source.get("source_tier"),
        source_origin_id=source.get("source_origin_id"),
        syndication_parent_id=source.get("syndication_parent_id"),
        provider=str(source.get("provider", "fixture_synthetic")),
        event_time=str(source.get("event_time", row["event_time"])),
        available_time=str(source.get("available_time", row["available_time"])),
        verification_state=VerificationStatus.UNVERIFIED,
        provenance_ref=str(source.get("source_id", "")),
    )


def _claims_from_row(row: dict[str, Any]) -> tuple[EntityClaim, ...]:
    issuer_claims = row.get("issuer_claims")
    if isinstance(issuer_claims, list) and issuer_claims:
        return tuple(
            EntityClaim(
                symbol=claim.get("symbol"),
                issuer_name=claim.get("issuer_name"),
                exchange=claim.get("exchange"),
                security_type=claim.get("security_type"),
                source_record_id=str(row.get("document_id", "")),
            )
            for claim in issuer_claims
        )
    symbols = row.get("associated_symbols", [])
    if not isinstance(symbols, list):
        symbols = []
    return tuple(
        EntityClaim(symbol=str(symbol), source_record_id=str(row.get("document_id", "")))
        for symbol in symbols
    )


def raw_document_from_fixture_row(row: dict[str, Any]) -> RawDocument:
    source = _parse_source(row)
    symbols = tuple(str(symbol).upper() for symbol in row.get("associated_symbols", []))
    return RawDocument(
        document_id=str(row["document_id"]),
        source=source,
        title=row.get("title"),
        body=row.get("body"),
        url=row.get("url"),
        revision_id=row.get("revision_id"),
        revision_of_document_id=row.get("revision_of_document_id"),
        origin_class=InformationOriginClass.PRIMARY_INFORMATION,
        timing_class=TimingClass.CONTEMPORANEOUS_INFORMATION,
        associated_symbols=symbols,
        event_time=str(row["event_time"]),
        available_time=str(row["available_time"]),
        provenance_ref=str(row.get("document_id", "")),
    )


def load_context_document_records(
    fixture_path: Path,
    *,
    symbol_mappings: dict[str, SymbolMapping] | None = None,
) -> list[ContextDocumentRecord]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("MC_FIXTURE_INVALID_DOCUMENTS")

    records: list[ContextDocumentRecord] = []
    for row in documents:
        if not isinstance(row, dict):
            continue
        document = raw_document_from_fixture_row(row)
        claims = _claims_from_row(row)
        resolved_document, resolution = resolve_document_entities(
            document,
            claims=claims,
            symbol_mappings=symbol_mappings,
        )
        records.append(
            ContextDocumentRecord(
                document=resolved_document,
                canonical_event_type=str(row.get("canonical_event_type", "")),
                entity_resolution=resolution,
            )
        )
    return records


def build_symbol_mapping_registry(symbol: str) -> dict[str, SymbolMapping]:
    normalized = symbol.strip().upper()
    return {normalized: SymbolMapping(provider_symbol=normalized, instrument_id=normalized)}
