"""Build canonical OptionContract records from fixture activities (O1 wiring)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ...contracts.options import DeliverableSpec, OptionContract, option_contract_to_dict
from ...contracts.options_quality import OptionQualityFlag
from ...donor_patterns.options_lane import liquidity_gate
from ...options.spec_registry import resolve_option_spec


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _days_to_expiration(event_time: str, expiration: str) -> int:
    event_date = _parse_iso_date(event_time)
    expiry_date = _parse_iso_date(expiration)
    return max((expiry_date - event_date).days, 0)


def _option_id(symbol: str, expiration: str, option_type: str, strike: float) -> str:
    exp = expiration.replace("-", "")
    cp = "C" if option_type.lower() == "call" else "P"
    strike_int = int(round(strike * 1000))
    return f"{symbol.upper()}{exp}{cp}{strike_int:08d}"


def _resolve_deliverable(
    activity: dict[str, Any],
    *,
    symbol: str,
    event_time: str,
    quality_flags: list[str],
) -> tuple[DeliverableSpec | None, Decimal, str, str]:
    as_of = _parse_iso_date(event_time) if event_time else date.today()
    product_spec = resolve_option_spec(symbol, as_of)
    multiplier = product_spec.multiplier if product_spec else Decimal("100")
    exercise_style = product_spec.exercise_style if product_spec else "american"
    settlement_style = product_spec.settlement_style if product_spec else "physical"

    if activity.get("corporate_action_adjusted") is True:
        quality_flags.append(OptionQualityFlag.CORPORATE_ACTION_ADJUSTED.value)
        if activity.get("deliverable_unknown") is True:
            quality_flags.append(OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value)
            return None, multiplier, exercise_style, settlement_style
        deliverable_shares = activity.get("deliverable_shares")
        if deliverable_shares is not None:
            return (
                DeliverableSpec(
                    shares_per_contract=Decimal(str(deliverable_shares)),
                    description="corporate_action_adjusted",
                ),
                multiplier,
                exercise_style,
                settlement_style,
            )
        quality_flags.append(OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value)
        return None, multiplier, exercise_style, settlement_style

    if product_spec is None:
        quality_flags.append(OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value)
        return None, multiplier, exercise_style, settlement_style

    return product_spec.deliverable(), multiplier, exercise_style, settlement_style


def activity_to_option_contract(
    activity: dict[str, Any],
    *,
    symbol: str,
    fixture_id: str,
    provider_id: str,
) -> OptionContract:
    event_time = str(activity.get("event_time", ""))
    expiry = str(activity.get("expiry", ""))
    option_type = str(activity.get("option_type", "call")).lower()
    strike_raw = activity.get("adjusted_strike", activity.get("strike", 0))
    strike = Decimal(str(strike_raw))
    bid = float(activity.get("bid", 0.0))
    ask = float(activity.get("ask", 0.0))
    open_interest = int(activity.get("open_interest", 0))
    liquidity_ok, _liquidity_reasons = liquidity_gate(bid=bid, ask=ask, open_interest=open_interest)
    quality_flags: list[str] = []
    if str(activity.get("direction_label", "ambiguous")) in {"ambiguous", "neutral"}:
        quality_flags.append(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value)
    if bid <= 0 or ask <= 0:
        quality_flags.append(OptionQualityFlag.NO_TWO_SIDED_MARKET.value)
    if not liquidity_ok:
        quality_flags.append(OptionQualityFlag.WIDE_OPTION_SPREAD.value)

    deliverable, multiplier, exercise_style, settlement_style = _resolve_deliverable(
        activity,
        symbol=symbol,
        event_time=event_time,
        quality_flags=quality_flags,
    )

    mid: Decimal | None = None
    if bid > 0 and ask > 0:
        mid = Decimal(str(round((bid + ask) / 2, 4)))
    bid_size_raw = activity.get("bid_size")
    ask_size_raw = activity.get("ask_size")
    bid_size = int(bid_size_raw) if isinstance(bid_size_raw, int) else None
    ask_size = int(ask_size_raw) if isinstance(ask_size_raw, int) else None
    return OptionContract(
        underlying_id=symbol.upper(),
        option_id=_option_id(symbol, expiry, option_type, float(strike)),
        call_put="call" if option_type == "call" else "put",
        strike=strike,
        expiration=expiry,
        dte=_days_to_expiration(event_time, expiry) if event_time and expiry else 0,
        exercise_style=exercise_style,
        settlement_style=settlement_style,
        multiplier=multiplier,
        deliverable=deliverable,
        bid=Decimal(str(bid)) if bid > 0 else None,
        ask=Decimal(str(ask)) if ask > 0 else None,
        mid=mid,
        bid_size=bid_size,
        ask_size=ask_size,
        volume=int(activity.get("volume", 0) or 0),
        open_interest=open_interest,
        provider=provider_id,
        event_time=event_time,
        available_time=event_time,
        quality_flags=tuple(quality_flags),
        provenance_ref=f"{fixture_id}:{event_time}:{strike}:{expiry}:{option_type}",
    )


def activities_to_chain_dicts(
    activities: list[dict[str, Any]],
    *,
    symbol: str,
    fixture_id: str,
    provider_id: str,
) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        contract = activity_to_option_contract(
            activity,
            symbol=symbol,
            fixture_id=fixture_id,
            provider_id=provider_id,
        )
        contract_dict = option_contract_to_dict(contract)
        underlying_price = activity.get("underlying_price")
        if isinstance(underlying_price, (int, float)) and underlying_price > 0:
            contract_dict["underlying_price"] = underlying_price
        contracts.append(contract_dict)
    return contracts


__all__ = [
    "activity_to_option_contract",
    "activities_to_chain_dicts",
]
