"""Bounded XA-02 admitted FRED rates vertical catalog and cross-asset references."""

from __future__ import annotations

from dataclasses import dataclass

from market_platform_foundation.fred.registry import lookup_canonical
from market_platform_foundation.xa01.compatibility import register_currency, register_future_family
from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa01.registry import InstrumentRegistry

from .contracts import CrossAssetReferenceRelationship
from .enums import CrossAssetReferenceType, ReferenceSubjectType, ReferenceTargetType
from .errors import Xa02Error, Xa02ErrorCode
from .identity import derive_relationship_id


@dataclass(frozen=True, slots=True)
class AdmittedSeriesDefinition:
    canonical_indicator_id: str
    target_key: str
    relationship_type: CrossAssetReferenceType
    domain: AnalyticalDomain
    provenance_ref: str = "xa02.catalog.rates_reference_vertical"


ADMITTED_RATES_SERIES: tuple[AdmittedSeriesDefinition, ...] = (
    AdmittedSeriesDefinition(
        canonical_indicator_id="US_10Y_TREASURY_YIELD",
        target_key="ZN",
        relationship_type=CrossAssetReferenceType.MACRO_REFERENCE_FOR,
        domain=AnalyticalDomain.RATES,
    ),
    AdmittedSeriesDefinition(
        canonical_indicator_id="US_2Y_TREASURY_YIELD",
        target_key="ZT",
        relationship_type=CrossAssetReferenceType.MACRO_REFERENCE_FOR,
        domain=AnalyticalDomain.RATES,
    ),
    AdmittedSeriesDefinition(
        canonical_indicator_id="US_5Y_TREASURY_YIELD",
        target_key="ZF",
        relationship_type=CrossAssetReferenceType.MACRO_REFERENCE_FOR,
        domain=AnalyticalDomain.RATES,
    ),
    AdmittedSeriesDefinition(
        canonical_indicator_id="US_30Y_TREASURY_YIELD",
        target_key="ZB",
        relationship_type=CrossAssetReferenceType.MACRO_REFERENCE_FOR,
        domain=AnalyticalDomain.RATES,
    ),
    AdmittedSeriesDefinition(
        canonical_indicator_id="US_EFFECTIVE_FED_FUNDS_RATE",
        target_key="USD",
        relationship_type=CrossAssetReferenceType.MACRO_REFERENCE_FOR,
        domain=AnalyticalDomain.MONETARY_RESERVE,
    ),
)

_ADMITTED_INDICATOR_IDS = frozenset(item.canonical_indicator_id for item in ADMITTED_RATES_SERIES)
_SUPPORTED_RELATIONSHIP_TYPES = frozenset(item.value for item in CrossAssetReferenceType)


def is_admitted_indicator(canonical_indicator_id: str) -> bool:
    return canonical_indicator_id in _ADMITTED_INDICATOR_IDS


def admitted_series_definitions() -> tuple[AdmittedSeriesDefinition, ...]:
    return ADMITTED_RATES_SERIES


def bootstrap_xa_targets(registry: InstrumentRegistry) -> dict[str, str]:
    targets: dict[str, str] = {}
    for family in ("ZN", "ZT", "ZF", "ZB"):
        targets[family] = register_future_family(family_root=family, registry=registry)
    targets["USD"] = register_currency(iso_code="USD", registry=registry)
    return targets


def build_catalog_relationships(
    *,
    xa_targets: dict[str, str],
) -> tuple[CrossAssetReferenceRelationship, ...]:
    relationships: list[CrossAssetReferenceRelationship] = []
    for definition in ADMITTED_RATES_SERIES:
        target_id = xa_targets.get(definition.target_key)
        if target_id is None:
            raise Xa02Error(
                Xa02ErrorCode.UNKNOWN_XA_TARGET,
                "missing XA target for admitted series definition",
                {"target_key": definition.target_key},
            )
        relationship_id = derive_relationship_id(
            canonical_indicator_id=definition.canonical_indicator_id,
            relationship_type=definition.relationship_type,
            target_xa_canonical_id=target_id,
            domain=definition.domain,
        )
        relationships.append(
            CrossAssetReferenceRelationship(
                relationship_id=relationship_id,
                subject_type=ReferenceSubjectType.CANONICAL_INDICATOR,
                subject_id=definition.canonical_indicator_id,
                relationship_type=definition.relationship_type,
                target_type=ReferenceTargetType.XA_INSTRUMENT,
                target_xa_canonical_id=target_id,
                domain=definition.domain,
                provenance_ref=definition.provenance_ref,
            )
        )
    return tuple(relationships)


def catalog_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for definition in ADMITTED_RATES_SERIES:
        entry = lookup_canonical(definition.canonical_indicator_id)
        rows.append(
            {
                "canonical_indicator_id": definition.canonical_indicator_id,
                "fred_series_id": entry.fred_series_id if entry else "",
                "title": entry.title if entry else "",
                "units": entry.units if entry else "",
                "target_key": definition.target_key,
                "relationship_type": definition.relationship_type.value,
                "domain": definition.domain.value,
            }
        )
    return rows
