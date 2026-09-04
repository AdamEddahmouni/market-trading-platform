"""Price observation extraction from normalized events (BUILD 15)."""

from __future__ import annotations

import math

from ..contracts.event import EventV1
from ..quality.models import QualityFindingCode
from ..quality.validators import validate_event_structure
from ..temporal.validation import event_sort_key
from .types import PriceObservationReceipt


def _normalize_event_type(event_type: str) -> str:
    return str(event_type).upper()


def extract_trade_price(event: EventV1) -> float | None:
    payload = event.payload
    raw = payload.get("price")
    if raw is None:
        raw = payload.get("px")
    if raw is None:
        raw = payload.get("last_price") or payload.get("last")
    if raw is None:
        return None
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0.0:
        return None
    return price


def event_observation_kind(event: EventV1) -> str:
    event_type = _normalize_event_type(event.event_type)
    if event_type in {"TICK"}:
        return "TICK"
    if event_type in {"TRADE"}:
        return "TRADE"
    if event_type in {"QUOTE", "L1"}:
        return "QUOTE"
    return event_type


def is_valid_settlement_observation(event: EventV1) -> bool:
    kind = event_observation_kind(event)
    if kind == "QUOTE":
        findings = validate_event_structure(event)
        if any(f.code in {QualityFindingCode.CROSSED_BOOK.value, QualityFindingCode.INVALID_QUOTE.value} for f in findings):
            return False
        bid = event.payload.get("bid") or event.payload.get("bid_price")
        ask = event.payload.get("ask") or event.payload.get("ask_price")
        if bid is None or ask is None:
            return False
        try:
            bid_f = float(bid)
            ask_f = float(ask)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(bid_f) or not math.isfinite(ask_f) or bid_f <= 0.0 or ask_f <= 0.0:
            return False
        return ask_f >= bid_f
    price = extract_trade_price(event)
    return price is not None


def observation_from_event(event: EventV1) -> PriceObservationReceipt | None:
    if not is_valid_settlement_observation(event):
        return None
    kind = event_observation_kind(event)
    if kind == "QUOTE":
        bid = float(event.payload.get("bid") or event.payload.get("bid_price"))
        ask = float(event.payload.get("ask") or event.payload.get("ask_price"))
        price = (bid + ask) / 2.0
    else:
        price = extract_trade_price(event)
        if price is None:
            return None
    return PriceObservationReceipt(
        event_id=event.event_id,
        price=price,
        event_time_ns=event.event_time_ns,
        available_time_ns=event.available_time_ns,
        observation_kind=kind,
        provider_id=event.source.provider_id,
        source_type=event.source.source_type,
    )


def event_to_tape_row(event: EventV1) -> dict[str, object] | None:
    receipt = observation_from_event(event)
    if receipt is None:
        return None
    return {
        "event_time_ns": receipt.event_time_ns,
        "available_time_ns": receipt.available_time_ns,
        "price": receipt.price,
        "trade_id": receipt.event_id,
        "event_id": receipt.event_id,
        "observation_kind": receipt.observation_kind,
    }


def terminal_sort_key(event: EventV1) -> tuple[int, int, int, str]:
    return event_sort_key(event)


__all__ = [
    "event_observation_kind",
    "event_to_tape_row",
    "extract_trade_price",
    "is_valid_settlement_observation",
    "observation_from_event",
    "terminal_sort_key",
]
