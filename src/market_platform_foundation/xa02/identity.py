"""Deterministic XA-02 observation and relationship identity."""

from __future__ import annotations

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.fred.contracts import MacroObservation

from .enums import (
    IDENTITY_PROFILE,
    RELATIONSHIP_PROFILE,
    CrossAssetReferenceType,
    SourceProvider,
)
from market_platform_foundation.xa01.enums import AnalyticalDomain


def vintage_identity_material(obs: MacroObservation) -> str:
    if obs.realtime_start:
        return f"{obs.realtime_start}:{obs.revision_number}"
    if obs.vintage_date:
        return f"{obs.vintage_date}:{obs.revision_number}"
    if obs.series_last_updated:
        return f"snapshot:{obs.series_last_updated}:{obs.revision_number}"
    return f"unknown:{obs.revision_number}"


def derive_observation_id(
    *,
    canonical_indicator_id: str,
    observation_date: str,
    vintage_identity: str,
    source_provider: SourceProvider = SourceProvider.FRED,
) -> str:
    material = {
        "profile": IDENTITY_PROFILE,
        "canonical_indicator_id": canonical_indicator_id,
        "observation_date": observation_date,
        "vintage_identity": vintage_identity,
        "source_provider": source_provider.value,
    }
    digest = sha256_bytes(canonical_bytes(material))
    return f"XA02:OBS:{digest[:16]}"


def derive_observation_id_from_macro(obs: MacroObservation) -> str:
    return derive_observation_id(
        canonical_indicator_id=obs.canonical_indicator_id,
        observation_date=obs.observation_date,
        vintage_identity=vintage_identity_material(obs),
        source_provider=SourceProvider.FRED,
    )


def derive_relationship_id(
    *,
    canonical_indicator_id: str,
    relationship_type: CrossAssetReferenceType,
    target_xa_canonical_id: str,
    domain: AnalyticalDomain,
) -> str:
    material = {
        "profile": RELATIONSHIP_PROFILE,
        "subject_id": canonical_indicator_id,
        "relationship_type": relationship_type.value,
        "target_xa_canonical_id": target_xa_canonical_id,
        "domain": domain.value,
    }
    digest = sha256_bytes(canonical_bytes(material))
    return f"XA02:REL:{digest[:16]}"
