"""Futures basis engine (F3) — explicit BasisDefinition semantics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..contracts.futures import (
    BasisDefinition,
    BasisObservation,
    FuturesCurveSnapshot,
    basis_observation_to_dict,
)
from ..contracts.futures_quality import FuturesQualityFlag, quality_blocks_curve_analytics


def build_basis_observation(
    snapshot: FuturesCurveSnapshot,
    spot_reference: Decimal | float,
    *,
    definition: BasisDefinition = BasisDefinition.FUTURES_MINUS_SPOT,
    spot_reference_id: str = "",
    event_time: str = "",
) -> BasisObservation | None:
    """Build BasisObservation from curve front contract and spot reference."""
    if quality_blocks_curve_analytics(snapshot.quality_flags):
        return None
    if not snapshot.prices:
        return None
    front_price = snapshot.prices[0]
    spot = Decimal(str(spot_reference))
    if definition == BasisDefinition.FUTURES_MINUS_SPOT:
        basis_value = front_price - spot
    else:
        basis_value = spot - front_price
    quality_flags: list[str] = []
    if snapshot.quality_flags:
        quality_flags.extend(snapshot.quality_flags)
    return BasisObservation(
        instrument_family=snapshot.instrument_family,
        contract_id=snapshot.contract_ids[0] if snapshot.contract_ids else "",
        basis_value=basis_value,
        basis_definition=definition,
        spot_reference_id=spot_reference_id,
        event_time=event_time or snapshot.observation_time,
        available_time=snapshot.available_time or snapshot.observation_time,
        quality_flags=tuple(quality_flags),
    )


def basis_payload(
    snapshot: FuturesCurveSnapshot,
    spot_reference: Decimal | float | None,
    *,
    spot_reference_id: str = "",
) -> dict[str, Any]:
    """Workspace payload for basis observation — fail-closed without spot."""
    if spot_reference is None:
        return {"available": False, "reason": "BASIS_REFERENCE_MISSING"}
    observation = build_basis_observation(
        snapshot,
        spot_reference,
        spot_reference_id=spot_reference_id,
    )
    if observation is None:
        return {"available": False, "reason": "BASIS_OBSERVATION_UNAVAILABLE"}
    payload = basis_observation_to_dict(observation)
    payload["available"] = True
    return payload


def basis_observation_from_curve(
    snapshot: FuturesCurveSnapshot,
    *,
    spot_reference: Decimal | None = None,
) -> dict[str, Any]:
    """Legacy compat — dict return for callers expecting stub shape."""
    if spot_reference is None:
        return {"available": False, "reason": "BASIS_REFERENCE_MISSING"}
    observation = build_basis_observation(snapshot, spot_reference)
    if observation is None:
        return {"available": False, "reason": "BASIS_OBSERVATION_UNAVAILABLE"}
    payload = basis_observation_to_dict(observation)
    payload["available"] = True
    return payload


__all__ = [
    "basis_observation_from_curve",
    "basis_payload",
    "build_basis_observation",
]
