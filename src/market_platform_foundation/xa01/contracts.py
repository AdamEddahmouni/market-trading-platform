"""XA-01 canonical instrument contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .enums import (
    SCHEMA_VERSION,
    AliasResolutionStatus,
    AnalyticalDomain,
    ExternalIdentifierType,
    InstrumentKind,
    PriceUnitKind,
    RelationshipType,
    XaAssetClass,
)


@dataclass(frozen=True, slots=True)
class CanonicalInstrumentIdentity:
    canonical_id: str
    instrument_kind: InstrumentKind
    asset_class: XaAssetClass
    identity_profile: str
    identity_key: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class DenominationMetadata:
    currency: str = "USD"
    price_unit_kind: PriceUnitKind = PriceUnitKind.CURRENCY_PER_SHARE
    contract_multiplier: str = "1"
    tick_size: str = ""
    quantity_unit: str = ""


@dataclass(frozen=True, slots=True)
class InstrumentDescriptor:
    identity: CanonicalInstrumentIdentity
    display_name: str = ""
    venue_id: str = ""
    exchange: str = ""
    denomination: DenominationMetadata = field(default_factory=DenominationMetadata)
    sovereign_issuer: str = ""
    security_type: str = ""
    issue_date: str = ""
    maturity_date: str = ""
    coupon: str = ""
    commodity_code: str = ""
    contract_month: str = ""
    expiration: str = ""
    strike: str = ""
    call_put: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ExternalIdentifier:
    identifier_type: ExternalIdentifierType
    alias_value: str
    provider_id: str = ""
    venue_id: str = ""
    valid_from: str = ""
    valid_to: str = ""


@dataclass(frozen=True, slots=True)
class DomainParticipation:
    domain: AnalyticalDomain
    valid_from: str = ""
    valid_to: str = ""


@dataclass(frozen=True, slots=True)
class InstrumentRelationship:
    relationship_type: RelationshipType
    from_canonical_id: str
    to_canonical_id: str
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class InstrumentRecord:
    descriptor: InstrumentDescriptor
    analytical_domains: tuple[DomainParticipation, ...] = ()
    aliases: tuple[ExternalIdentifier, ...] = ()
    relationships: tuple[InstrumentRelationship, ...] = ()


@dataclass(frozen=True, slots=True)
class AliasResolution:
    status: AliasResolutionStatus
    provider_id: str
    alias_value: str
    canonical_id: str = ""
    instrument_kind: InstrumentKind | None = None
    asset_class: XaAssetClass | None = None
    candidates: tuple[str, ...] = ()
    quality_flags: tuple[str, ...] = ()


def record_to_dict(record: InstrumentRecord) -> dict[str, Any]:
    desc = record.descriptor
    identity = desc.identity
    return {
        "schema_version": desc.schema_version,
        "canonical_id": identity.canonical_id,
        "instrument_kind": identity.instrument_kind.value,
        "asset_class": identity.asset_class.value,
        "identity_profile": identity.identity_profile,
        "identity_key": dict(identity.identity_key),
        "display_name": desc.display_name,
        "venue_id": desc.venue_id,
        "exchange": desc.exchange,
        "denomination": {
            "currency": desc.denomination.currency,
            "price_unit_kind": desc.denomination.price_unit_kind.value,
            "contract_multiplier": desc.denomination.contract_multiplier,
            "tick_size": desc.denomination.tick_size,
            "quantity_unit": desc.denomination.quantity_unit,
        },
        "sovereign_issuer": desc.sovereign_issuer,
        "security_type": desc.security_type,
        "issue_date": desc.issue_date,
        "maturity_date": desc.maturity_date,
        "coupon": desc.coupon,
        "commodity_code": desc.commodity_code,
        "contract_month": desc.contract_month,
        "expiration": desc.expiration,
        "strike": desc.strike,
        "call_put": desc.call_put,
        "base_currency": desc.base_currency,
        "quote_currency": desc.quote_currency,
        "analytical_domains": [
            {
                "domain": item.domain.value,
                "valid_from": item.valid_from,
                "valid_to": item.valid_to,
            }
            for item in record.analytical_domains
        ],
        "aliases": [
            {
                "identifier_type": alias.identifier_type.value,
                "alias_value": alias.alias_value,
                "provider_id": alias.provider_id,
                "venue_id": alias.venue_id,
                "valid_from": alias.valid_from,
                "valid_to": alias.valid_to,
            }
            for alias in record.aliases
        ],
        "relationships": [
            {
                "relationship_type": rel.relationship_type.value,
                "from_canonical_id": rel.from_canonical_id,
                "to_canonical_id": rel.to_canonical_id,
                "schema_version": rel.schema_version,
            }
            for rel in record.relationships
        ],
    }
