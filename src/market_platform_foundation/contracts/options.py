"""Canonical normalized option contract model (O1 foundation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal


CallPut = Literal["call", "put"]
ExerciseStyle = Literal["american", "european", "bermudan", "unknown"]
SettlementStyle = Literal["physical", "cash", "unknown"]


@dataclass(frozen=True, slots=True)
class DeliverableSpec:
    """Deliverable for adjusted or standard option contracts."""

    shares_per_contract: Decimal
    cash_component: Decimal = Decimal("0")
    description: str = ""


@dataclass(frozen=True, slots=True)
class OptionContract:
    """Normalized option contract — platform ingestion target for O1+."""

    underlying_id: str
    option_id: str
    call_put: CallPut
    strike: Decimal
    expiration: str  # ISO date until dedicated date type is wired
    dte: int
    exercise_style: ExerciseStyle = "american"
    settlement_style: SettlementStyle = "physical"
    multiplier: Decimal = Decimal("100")
    deliverable: DeliverableSpec | None = None

    bid: Decimal | None = None
    ask: Decimal | None = None
    mid: Decimal | None = None
    last: Decimal | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    volume: int | None = None
    open_interest: int | None = None

    intrinsic_value: Decimal | None = None
    extrinsic_value: Decimal | None = None

    provider: str = ""
    exchange: str | None = None
    event_time: str = ""
    available_time: str = ""

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


def option_contract_to_dict(contract: OptionContract) -> dict[str, Any]:
    """Serialize for API envelopes and replay fixtures."""
    deliverable: dict[str, Any] | None = None
    if contract.deliverable is not None:
        deliverable = {
            "shares_per_contract": str(contract.deliverable.shares_per_contract),
            "cash_component": str(contract.deliverable.cash_component),
            "description": contract.deliverable.description,
        }
    return {
        "underlying_id": contract.underlying_id,
        "option_id": contract.option_id,
        "call_put": contract.call_put,
        "strike": str(contract.strike),
        "expiration": contract.expiration,
        "dte": contract.dte,
        "exercise_style": contract.exercise_style,
        "settlement_style": contract.settlement_style,
        "multiplier": str(contract.multiplier),
        "deliverable": deliverable,
        "bid": str(contract.bid) if contract.bid is not None else None,
        "ask": str(contract.ask) if contract.ask is not None else None,
        "mid": str(contract.mid) if contract.mid is not None else None,
        "last": str(contract.last) if contract.last is not None else None,
        "bid_size": contract.bid_size,
        "ask_size": contract.ask_size,
        "volume": contract.volume,
        "open_interest": contract.open_interest,
        "intrinsic_value": (
            str(contract.intrinsic_value) if contract.intrinsic_value is not None else None
        ),
        "extrinsic_value": (
            str(contract.extrinsic_value) if contract.extrinsic_value is not None else None
        ),
        "provider": contract.provider,
        "exchange": contract.exchange,
        "event_time": contract.event_time,
        "available_time": contract.available_time,
        "quality_flags": list(contract.quality_flags),
        "provenance_ref": contract.provenance_ref,
    }
