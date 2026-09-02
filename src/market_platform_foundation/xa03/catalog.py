"""Bounded XA-03 admitted CFTC positioning vertical catalog."""

from __future__ import annotations

from dataclasses import dataclass

from market_platform_foundation.cftc.contracts import CotPositionScope, CotReportFamily
from market_platform_foundation.xa01.compatibility import register_future_family
from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa01.registry import InstrumentRegistry
from market_platform_foundation.xa02.contracts import CrossAssetReferenceRelationship
from market_platform_foundation.xa02.enums import CrossAssetReferenceType, ReferenceSubjectType, ReferenceTargetType

from .errors import Xa03Error, Xa03ErrorCode
from .identity import derive_market_relationship_id, market_report_id


@dataclass(frozen=True, slots=True)
class AdmittedMarketDefinition:
    cftc_contract_market_code: str
    report_family: CotReportFamily
    position_scope: CotPositionScope
    target_key: str
    relationship_type: CrossAssetReferenceType
    domain: AnalyticalDomain
    fixture_file: str
    provenance_ref: str = "xa03.catalog.positioning_reference_vertical"

    @property
    def market_report_id(self) -> str:
        return market_report_id(
            cftc_contract_market_code=self.cftc_contract_market_code,
            report_family=self.report_family.value,
            position_scope=self.position_scope.value,
        )


ADMITTED_POSITIONING_MARKETS: tuple[AdmittedMarketDefinition, ...] = (
    AdmittedMarketDefinition(
        cftc_contract_market_code="13874+",
        report_family=CotReportFamily.TFF,
        position_scope=CotPositionScope.FUTURES_ONLY,
        target_key="ES",
        relationship_type=CrossAssetReferenceType.REFERENCE_RELEVANT_TO,
        domain=AnalyticalDomain.EQUITY,
        fixture_file="tff_futures_only_es.json",
    ),
    AdmittedMarketDefinition(
        cftc_contract_market_code="067651",
        report_family=CotReportFamily.DISAGGREGATED,
        position_scope=CotPositionScope.FUTURES_ONLY,
        target_key="CL",
        relationship_type=CrossAssetReferenceType.REFERENCE_RELEVANT_TO,
        domain=AnalyticalDomain.COMMODITY,
        fixture_file="disaggregated_futures_only_cl.json",
    ),
    AdmittedMarketDefinition(
        cftc_contract_market_code="088691",
        report_family=CotReportFamily.LEGACY,
        position_scope=CotPositionScope.FUTURES_ONLY,
        target_key="GC",
        relationship_type=CrossAssetReferenceType.REFERENCE_RELEVANT_TO,
        domain=AnalyticalDomain.COMMODITY,
        fixture_file="legacy_futures_only_gc.json",
    ),
    AdmittedMarketDefinition(
        cftc_contract_market_code="020601",
        report_family=CotReportFamily.TFF,
        position_scope=CotPositionScope.FUTURES_ONLY,
        target_key="ZN",
        relationship_type=CrossAssetReferenceType.REFERENCE_RELEVANT_TO,
        domain=AnalyticalDomain.RATES,
        fixture_file="positioning_reference_vertical.json",
    ),
    AdmittedMarketDefinition(
        cftc_contract_market_code="023651",
        report_family=CotReportFamily.DISAGGREGATED,
        position_scope=CotPositionScope.FUTURES_ONLY,
        target_key="NG",
        relationship_type=CrossAssetReferenceType.REFERENCE_RELEVANT_TO,
        domain=AnalyticalDomain.COMMODITY,
        fixture_file="positioning_reference_vertical.json",
    ),
)

_ADMITTED_MARKET_IDS = frozenset(item.market_report_id for item in ADMITTED_POSITIONING_MARKETS)
_ADMITTED_BY_CODE: dict[str, AdmittedMarketDefinition] = {
    item.cftc_contract_market_code: item for item in ADMITTED_POSITIONING_MARKETS
}


def is_admitted_market(market_report_id_value: str) -> bool:
    return market_report_id_value in _ADMITTED_MARKET_IDS


def lookup_admitted_market_by_code(cftc_contract_market_code: str) -> AdmittedMarketDefinition | None:
    return _ADMITTED_BY_CODE.get(cftc_contract_market_code)


def admitted_market_definitions() -> tuple[AdmittedMarketDefinition, ...]:
    return ADMITTED_POSITIONING_MARKETS


def bootstrap_xa_targets(registry: InstrumentRegistry) -> dict[str, str]:
    targets: dict[str, str] = {}
    for key in ("ES", "CL", "GC", "ZN", "NG"):
        targets[key] = register_future_family(family_root=key, registry=registry)
    return targets


def build_catalog_relationships(
    *,
    xa_targets: dict[str, str],
) -> tuple[CrossAssetReferenceRelationship, ...]:
    relationships: list[CrossAssetReferenceRelationship] = []
    for definition in ADMITTED_POSITIONING_MARKETS:
        target_id = xa_targets.get(definition.target_key)
        if target_id is None:
            raise Xa03Error(
                Xa03ErrorCode.UNKNOWN_XA_TARGET,
                "missing XA target for admitted market definition",
                {"target_key": definition.target_key},
            )
        relationship_id = derive_market_relationship_id(
            market_report_id_value=definition.market_report_id,
            relationship_type=definition.relationship_type,
            target_xa_canonical_id=target_id,
            domain=definition.domain,
        )
        relationships.append(
            CrossAssetReferenceRelationship(
                relationship_id=relationship_id,
                subject_type=ReferenceSubjectType.CFTC_MARKET_REPORT,
                subject_id=definition.market_report_id,
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
    for definition in ADMITTED_POSITIONING_MARKETS:
        rows.append(
            {
                "market_report_id": definition.market_report_id,
                "cftc_contract_market_code": definition.cftc_contract_market_code,
                "report_family": definition.report_family.value,
                "position_scope": definition.position_scope.value,
                "target_key": definition.target_key,
                "relationship_type": definition.relationship_type.value,
                "domain": definition.domain.value,
                "fixture_file": definition.fixture_file,
            }
        )
    return rows


def validate_catalog_relationships(relationships: tuple[CrossAssetReferenceRelationship, ...]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected = {item.market_report_id for item in ADMITTED_POSITIONING_MARKETS}
    registered = {item.subject_id for item in relationships}
    for market_id in sorted(expected - registered):
        findings.append({"code": "MISSING_CATALOG_RELATIONSHIP", "market_report_id": market_id})
    for relationship in relationships:
        if relationship.subject_id not in expected:
            findings.append({"code": "UNADMITTED_RELATIONSHIP_SUBJECT", "subject_id": relationship.subject_id})
        if relationship.relationship_type == CrossAssetReferenceType.MACRO_REFERENCE_FOR:
            findings.append(
                {
                    "code": "UNSUPPORTED_RELATIONSHIP_FOR_POSITIONING",
                    "relationship_id": relationship.relationship_id,
                }
            )
    return findings
