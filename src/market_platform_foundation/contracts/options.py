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


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class OptionChainSnapshot:
    """Point-in-time option chain slice for O1 chain-level QA."""

    underlying_id: str
    as_of_time: str
    contracts: tuple[dict[str, Any], ...]
    chain_quality: str
    provider_id: str
    available: bool
    reason: str | None = None


def option_chain_snapshot_to_dict(snapshot: OptionChainSnapshot) -> dict[str, Any]:
    return {
        "underlying_id": snapshot.underlying_id,
        "as_of_time": snapshot.as_of_time,
        "contracts": list(snapshot.contracts),
        "contract_count": len(snapshot.contracts),
        "chain_quality": snapshot.chain_quality,
        "provider_id": snapshot.provider_id,
        "available": snapshot.available,
        "reason": snapshot.reason,
    }


def option_contract_from_dict(payload: dict[str, Any]) -> OptionContract:
    """Deserialize OptionContract — fail-closed on missing required fields."""
    required = ("underlying_id", "option_id", "call_put", "strike", "expiration", "dte")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"OPTION_CONTRACT_MISSING_FIELDS:{','.join(missing)}")
    deliverable_raw = payload.get("deliverable")
    deliverable: DeliverableSpec | None = None
    if isinstance(deliverable_raw, dict):
        deliverable = DeliverableSpec(
            shares_per_contract=Decimal(str(deliverable_raw.get("shares_per_contract", "100"))),
            cash_component=Decimal(str(deliverable_raw.get("cash_component", "0"))),
            description=str(deliverable_raw.get("description", "")),
        )
    quality = payload.get("quality_flags", [])
    quality_flags = tuple(str(flag) for flag in quality) if isinstance(quality, list) else ()
    return OptionContract(
        underlying_id=str(payload["underlying_id"]),
        option_id=str(payload["option_id"]),
        call_put=str(payload["call_put"]),
        strike=Decimal(str(payload["strike"])),
        expiration=str(payload["expiration"]),
        dte=int(payload["dte"]),
        exercise_style=str(payload.get("exercise_style", "american")),
        settlement_style=str(payload.get("settlement_style", "physical")),
        multiplier=Decimal(str(payload.get("multiplier", "100"))),
        deliverable=deliverable,
        bid=_optional_decimal(payload.get("bid")),
        ask=_optional_decimal(payload.get("ask")),
        mid=_optional_decimal(payload.get("mid")),
        last=_optional_decimal(payload.get("last")),
        bid_size=int(payload["bid_size"]) if payload.get("bid_size") is not None else None,
        ask_size=int(payload["ask_size"]) if payload.get("ask_size") is not None else None,
        volume=int(payload["volume"]) if payload.get("volume") is not None else None,
        open_interest=int(payload["open_interest"]) if payload.get("open_interest") is not None else None,
        intrinsic_value=_optional_decimal(payload.get("intrinsic_value")),
        extrinsic_value=_optional_decimal(payload.get("extrinsic_value")),
        provider=str(payload.get("provider", "")),
        exchange=str(payload.get("exchange")) if payload.get("exchange") else None,
        event_time=str(payload.get("event_time", "")),
        available_time=str(payload.get("available_time", "")),
        quality_flags=quality_flags,
        provenance_ref=str(payload.get("provenance_ref", "")),
    )


__all__ = [
    "CallPut",
    "DeliverableSpec",
    "ExerciseStyle",
    "OptionChainSnapshot",
    "OptionContract",
    "SettlementStyle",
    "option_chain_snapshot_to_dict",
    "option_contract_from_dict",
    "option_contract_to_dict",
]
