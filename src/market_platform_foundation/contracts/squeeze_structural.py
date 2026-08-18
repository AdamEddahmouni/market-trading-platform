"""SS P2 structural vulnerability contracts — lending, velocity, attention, catalyst."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class PublicationState(StrEnum):
    PUBLISHED = "PUBLISHED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SecuritiesLendingSnapshot:
    """Point-in-time securities lending utilization snapshot."""

    symbol: str
    utilization_rate: Decimal | None
    shares_on_loan: int | None
    shares_available: int | None
    fee_rate: Decimal | None
    observation_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.PUBLISHED
    provider: str = ""
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class VelocityAccelerationMetric:
    """Velocity/acceleration metric with explicit PIT publication semantics."""

    symbol: str
    metric_id: str
    velocity: float | None
    acceleration: float | None
    horizon: str
    observation_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.PUBLISHED
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AttentionFeature:
    """Attention velocity interface — measured interest, not raw mention count."""

    symbol: str
    attention_score: float | None
    attention_velocity: float | None
    attention_acceleration: float | None
    observation_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CatalystStrength:
    """Catalyst strength for squeeze ignition context."""

    symbol: str
    catalyst_id: str
    strength: float | None
    catalyst_type: str
    observation_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ShortThesisInvalidation:
    """Explicit short thesis invalidation signal — not generic news age."""

    symbol: str
    invalidation_score: float | None
    mechanism: str
    observation_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def lending_snapshot_to_dict(snapshot: SecuritiesLendingSnapshot) -> dict[str, Any]:
    return {
        "symbol": snapshot.symbol,
        "utilization_rate": str(snapshot.utilization_rate) if snapshot.utilization_rate is not None else None,
        "shares_on_loan": snapshot.shares_on_loan,
        "shares_available": snapshot.shares_available,
        "fee_rate": str(snapshot.fee_rate) if snapshot.fee_rate is not None else None,
        "observation_time": snapshot.observation_time,
        "available_time": snapshot.available_time,
        "publication_state": snapshot.publication_state.value,
        "provider": snapshot.provider,
        "provenance_ref": snapshot.provenance_ref,
        "quality_flags": list(snapshot.quality_flags),
    }


def attention_feature_to_dict(feature: AttentionFeature) -> dict[str, Any]:
    return {
        "symbol": feature.symbol,
        "attention_score": feature.attention_score,
        "attention_velocity": feature.attention_velocity,
        "attention_acceleration": feature.attention_acceleration,
        "observation_time": feature.observation_time,
        "available_time": feature.available_time,
        "publication_state": feature.publication_state.value,
        "provenance_ref": feature.provenance_ref,
        "quality_flags": list(feature.quality_flags),
    }


__all__ = [
    "AttentionFeature",
    "CatalystStrength",
    "PublicationState",
    "SecuritiesLendingSnapshot",
    "ShortThesisInvalidation",
    "VelocityAccelerationMetric",
    "attention_feature_to_dict",
    "lending_snapshot_to_dict",
]
