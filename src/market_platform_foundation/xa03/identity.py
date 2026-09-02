"""Deterministic XA-03 positioning observation and relationship identity."""

from __future__ import annotations

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa02.enums import (
    POSITIONING_IDENTITY_PROFILE,
    RELATIONSHIP_PROFILE,
    CrossAssetReferenceType,
    SourceProvider,
)


def market_report_id(
    *,
    cftc_contract_market_code: str,
    report_family: str,
    position_scope: str,
) -> str:
    return f"CFTC_MARKET:{cftc_contract_market_code}:{report_family}:{position_scope}"


def revision_identity_material(*, content_hash: str, revision_number: int = 0) -> str:
    if content_hash:
        return f"hash:{content_hash}:{revision_number}"
    return f"unknown:{revision_number}"


def derive_positioning_observation_id(
    *,
    market_report_id_value: str,
    position_date: str,
    participant_category: str,
    revision_identity: str,
    source_provider: SourceProvider = SourceProvider.CFTC,
) -> str:
    material = {
        "profile": POSITIONING_IDENTITY_PROFILE,
        "market_report_id": market_report_id_value,
        "position_date": position_date[:10],
        "participant_category": participant_category,
        "revision_identity": revision_identity,
        "source_provider": source_provider.value,
    }
    digest = sha256_bytes(canonical_bytes(material))
    return f"XA03:OBS:{digest[:16]}"


def derive_market_relationship_id(
    *,
    market_report_id_value: str,
    relationship_type: CrossAssetReferenceType,
    target_xa_canonical_id: str,
    domain: AnalyticalDomain,
) -> str:
    material = {
        "profile": RELATIONSHIP_PROFILE,
        "subject_id": market_report_id_value,
        "relationship_type": relationship_type.value,
        "target_xa_canonical_id": target_xa_canonical_id,
        "domain": domain.value,
    }
    digest = sha256_bytes(canonical_bytes(material))
    return f"XA03:REL:{digest[:16]}"
