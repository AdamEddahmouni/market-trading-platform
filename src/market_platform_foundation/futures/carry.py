"""Futures carry engine (F3) — family-specific roll economics, not directional forecast."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from ..contracts.futures import FuturesCurveSnapshot
from ..contracts.futures_quality import quality_blocks_curve_analytics


CARRY_VERSION = "futures_carry_v1"


@dataclass(frozen=True, slots=True)
class CarryObservation:
    """Carry observation with explicit formula tag and assumptions."""

    instrument_family: str
    formula_tag: str
    annualized_carry: float
    front_contract_id: str
    back_contract_id: str
    days_between: int
    fair_value_context: bool = True
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = "futures:carry_engine_v1"


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return date.fromisoformat(value)
    except ValueError:
        return None


def _days_between(exp_front: str, exp_back: str) -> int | None:
    front = _parse_date(exp_front)
    back = _parse_date(exp_back)
    if front is None or back is None:
        return None
    delta = (back - front).days
    return delta if delta > 0 else None


def carry_observation_to_dict(observation: CarryObservation) -> dict[str, Any]:
    return {
        "instrument_family": observation.instrument_family,
        "formula_tag": observation.formula_tag,
        "annualized_carry": round(observation.annualized_carry, 8),
        "front_contract_id": observation.front_contract_id,
        "back_contract_id": observation.back_contract_id,
        "days_between": observation.days_between,
        "fair_value_context": observation.fair_value_context,
        "assumptions": list(observation.assumptions),
        "quality_flags": list(observation.quality_flags),
        "provenance_ref": observation.provenance_ref,
        "carry_version": CARRY_VERSION,
    }


def calendar_implied_carry(
    snapshot: FuturesCurveSnapshot,
) -> CarryObservation | None:
    """EQUITY_INDEX v1: implied_carry = ((F_back/F_front) - 1) / days * 365."""
    if quality_blocks_curve_analytics(snapshot.quality_flags):
        return None
    if len(snapshot.prices) < 2 or len(snapshot.expirations) < 2:
        return None
    front_price = float(snapshot.prices[0])
    back_price = float(snapshot.prices[-1])
    if front_price <= 0:
        return None
    days = _days_between(snapshot.expirations[0], snapshot.expirations[-1])
    if days is None:
        return None
    ratio_return = (back_price / front_price) - 1.0
    annualized = ratio_return / days * 365.0
    return CarryObservation(
        instrument_family=snapshot.instrument_family,
        formula_tag="CALENDAR_SPREAD_IMPLIED",
        annualized_carry=annualized,
        front_contract_id=snapshot.contract_ids[0],
        back_contract_id=snapshot.contract_ids[-1],
        days_between=days,
        assumptions=(
            "EQUITY_INDEX calendar spread implied carry",
            "Not assumed predictive of underlying return",
        ),
        quality_flags=tuple(snapshot.quality_flags),
    )


def cost_of_carry_from_spot(
    snapshot: FuturesCurveSnapshot,
    spot_reference: Decimal | float,
    *,
    risk_free_rate: float = 0.05,
) -> CarryObservation | None:
    """Alternative: ln(F_front / spot) / days_to_expiry * 365."""
    if quality_blocks_curve_analytics(snapshot.quality_flags):
        return None
    if not snapshot.prices or not snapshot.expirations:
        return None
    front_price = float(snapshot.prices[0])
    spot = float(spot_reference)
    if front_price <= 0 or spot <= 0:
        return None
    days = _days_between(snapshot.observation_time[:10], snapshot.expirations[0])
    if days is None:
        days = _days_between("2025-01-01", snapshot.expirations[0])
    if days is None or days <= 0:
        return None
    annualized = math.log(front_price / spot) / days * 365.0
    return CarryObservation(
        instrument_family=snapshot.instrument_family,
        formula_tag="COST_OF_CARRY_FROM_SPOT",
        annualized_carry=annualized,
        front_contract_id=snapshot.contract_ids[0] if snapshot.contract_ids else "",
        back_contract_id="",
        days_between=days,
        assumptions=(
            f"Cost-of-carry implied from spot; risk_free_rate={risk_free_rate}",
            "Fair-value context only — not directional forecast",
        ),
        quality_flags=tuple(snapshot.quality_flags),
    )


def carry_from_curve(
    snapshot: FuturesCurveSnapshot,
    *,
    spot_reference: Decimal | float | None = None,
    risk_free_rate: float = 0.05,
) -> CarryObservation | None:
    """Prefer calendar-spread implied carry; spot path when reference supplied."""
    calendar = calendar_implied_carry(snapshot)
    if calendar is not None:
        return calendar
    if spot_reference is not None:
        return cost_of_carry_from_spot(
            snapshot,
            spot_reference,
            risk_free_rate=risk_free_rate,
        )
    return None


def carry_payload(
    snapshot: FuturesCurveSnapshot,
    *,
    spot_reference: Decimal | float | None = None,
    risk_free_rate: float = 0.05,
) -> dict[str, Any]:
    """Workspace payload for carry observation."""
    observation = carry_from_curve(
        snapshot,
        spot_reference=spot_reference,
        risk_free_rate=risk_free_rate,
    )
    if observation is None:
        return {"available": False, "reason": "CARRY_OBSERVATION_UNAVAILABLE"}
    payload = carry_observation_to_dict(observation)
    payload["available"] = True
    return payload


__all__ = [
    "CARRY_VERSION",
    "CarryObservation",
    "calendar_implied_carry",
    "carry_from_curve",
    "carry_observation_to_dict",
    "carry_payload",
    "cost_of_carry_from_spot",
]
