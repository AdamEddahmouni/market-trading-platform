"""Build canonical OptionContract records from fixture activities (O1 wiring)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from ...contracts.options import DeliverableSpec, OptionContract, option_contract_to_dict
from ...contracts.options_quality import OptionQualityFlag
from ...donor_patterns.options_lane import liquidity_gate


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
    strike = Decimal(str(activity.get("strike", 0)))
    bid = float(activity.get("bid", 0.0))
    ask = float(activity.get("ask", 0.0))
    open_interest = int(activity.get("open_interest", 0))
    liquidity_ok, liquidity_reasons = liquidity_gate(bid=bid, ask=ask, open_interest=open_interest)
    quality_flags: list[str] = []
    if str(activity.get("direction_label", "ambiguous")) in {"ambiguous", "neutral"}:
        quality_flags.append(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value)
    if bid <= 0 or ask <= 0:
        quality_flags.append(OptionQualityFlag.NO_TWO_SIDED_MARKET.value)
    if not liquidity_ok:
        quality_flags.append(OptionQualityFlag.WIDE_OPTION_SPREAD.value)
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
        multiplier=Decimal("100"),
        deliverable=DeliverableSpec(shares_per_contract=Decimal("100")),
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
        contracts.append(option_contract_to_dict(contract))
    return contracts


__all__ = [
    "activity_to_option_contract",
    "activities_to_chain_dicts",
]
