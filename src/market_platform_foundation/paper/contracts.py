"""Canonical paper execution and instrument contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal
import math
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

ASSET_CLASSES: tuple[str, ...] = (
    "EQUITY",
    "OPTION",
    "FUTURE",
    "CRYPTO",
    "PREDICTION_MARKET",
)

ORDER_SIDES: tuple[str, ...] = ("BUY", "SELL")
ORDER_TYPES: tuple[str, ...] = ("MARKET", "LIMIT")

ORDER_LIFECYCLE_STATES: tuple[str, ...] = (
    "CREATED",
    "RISK_ACCEPTED",
    "RISK_REJECTED",
    "SUBMITTED",
    "WORKING",
    "ACTIVATED",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCEL_PENDING",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
)

ORDER_LIFECYCLE_TERMINAL_STATES: tuple[str, ...] = (
    "FILLED",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
    "RISK_REJECTED",
)

VALID_ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "CREATED": ("RISK_ACCEPTED", "RISK_REJECTED", "REJECTED", "ACTIVATED", "SUBMITTED"),
    "RISK_ACCEPTED": ("SUBMITTED", "ACTIVATED", "WORKING"),
    "SUBMITTED": ("ACTIVATED", "WORKING", "REJECTED", "CANCEL_PENDING"),
    "WORKING": ("PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "REJECTED", "EXPIRED"),
    "ACTIVATED": ("PARTIALLY_FILLED", "FILLED", "REJECTED", "CANCEL_PENDING"),
    "PARTIALLY_FILLED": ("FILLED", "CANCEL_PENDING"),
    "CANCEL_PENDING": ("CANCELLED",),
}


def build_instrument_ref(
    *,
    instrument_id: str,
    asset_class: str = "EQUITY",
    venue: str = "US_EQUITY",
    symbol: str,
    currency: str = "USD",
    tick_size: str = "0.01",
    lot_size: int = 1,
    contract_multiplier: str = "1",
    expiration: str | None = None,
    strike: str | None = None,
    option_right: str | None = None,
    settlement_type: str | None = None,
    underlying: str | None = None,
) -> dict[str, Any]:
    if asset_class not in ASSET_CLASSES:
        raise ValueError("INSTRUMENT_ASSET_CLASS_INVALID")
    body: dict[str, Any] = {
        "asset_class": asset_class,
        "contract_multiplier": contract_multiplier,
        "currency": currency,
        "instrument_id": instrument_id,
        "lot_size": lot_size,
        "symbol": symbol,
        "tick_size": tick_size,
        "venue": venue,
    }
    for key, value in (
        ("expiration", expiration),
        ("option_right", option_right),
        ("settlement_type", settlement_type),
        ("strike", strike),
        ("underlying", underlying),
    ):
        if value is not None:
            body[key] = value
    return body


def direction_from_side(side: str) -> str:
    if side == "BUY":
        return "long"
    if side == "SELL":
        return "short"
    raise ValueError("ORDER_SIDE_INVALID")


RESEARCH_CANDIDATE_ID_PREFIX = "CAND-"


def _validate_research_candidate_id(research_candidate_id: str) -> None:
    """Fail closed: a provenance id must be a well-formed ``CAND-<uuid>``.

    Unrecognized / malformed ids are rejected at intent build rather than
    silently dropped, so provenance is never silently lost (``DEC-MAN-001``).
    """
    if not research_candidate_id.startswith(RESEARCH_CANDIDATE_ID_PREFIX):
        raise ValueError("RESEARCH_CANDIDATE_ID_INVALID")
    tail = research_candidate_id[len(RESEARCH_CANDIDATE_ID_PREFIX):]
    try:
        uuid.UUID(tail)
    except (ValueError, AttributeError):
        raise ValueError("RESEARCH_CANDIDATE_ID_INVALID") from None


def build_user_order_intent(
    *,
    instrument: dict[str, Any],
    side: str,
    quantity: int,
    observation_time: int,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    client_order_id: str,
    idempotency_key: str,
    correlation_id: str | None = None,
    research_candidate_id: str | None = None,
) -> dict[str, Any]:
    if side not in ORDER_SIDES:
        raise ValueError("ORDER_SIDE_INVALID")
    if order_type not in ORDER_TYPES:
        raise ValueError("ORDER_TYPE_INVALID")
    # Fail closed against adversarial numerics: NaN bypasses every ordering
    # comparison and a float/bool quantity would poison content-derived ids
    # and downstream int() coercions.
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity <= 0
    ):
        raise ValueError("ORDER_QUANTITY_INVALID")
    if limit_price_minor is not None and (
        not isinstance(limit_price_minor, int)
        or isinstance(limit_price_minor, bool)
        or not math.isfinite(limit_price_minor)
        or limit_price_minor < 0
    ):
        raise ValueError("ORDER_LIMIT_PRICE_INVALID")
    if not isinstance(observation_time, int) or isinstance(observation_time, bool):
        raise ValueError("ORDER_OBSERVATION_TIME_INVALID")
    if research_candidate_id is not None:
        _validate_research_candidate_id(research_candidate_id)
    direction = direction_from_side(side)
    body: dict[str, Any] = {
        "action": "OPEN",
        "client_order_id": client_order_id,
        "created_time": observation_time,
        "desired_quantity": quantity,
        "direction": direction,
        "idempotency_key": idempotency_key,
        "instrument": instrument,
        "instrument_id": instrument["instrument_id"],
        "order_type": order_type,
        "side": side,
        "source": "USER_ORDER_TICKET",
    }
    if limit_price_minor is not None:
        body["limit_price_minor"] = limit_price_minor
    if correlation_id:
        body["correlation_id"] = correlation_id
    if research_candidate_id:
        body["research_candidate_id"] = research_candidate_id
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }


def decimal_minor_to_display(minor: int, *, scale: int = 100) -> str:
    value = Decimal(minor) / Decimal(scale)
    return format(value, "f")


def normalize_execution_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Extract canonical execution fields for shared simulator/risk path."""
    body: dict[str, Any] = {
        "action": intent.get("action", "OPEN"),
        "created_time": intent["created_time"],
        "desired_quantity": int(intent["desired_quantity"]),
        "direction": intent["direction"],
        "instrument_id": intent["instrument_id"],
    }
    for key in (
        "research_candidate_id",
        "signal_prediction_cutoff",
        "strategy_identity_hash",
        "order_type",
        "limit_price_minor",
    ):
        if key in intent:
            body[key] = intent[key]
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }


def validate_order_transition(*, prior_state: str, next_state: str) -> None:
    if prior_state in ORDER_LIFECYCLE_TERMINAL_STATES:
        raise ValueError(f"ORDER_TRANSITION_FROM_TERMINAL: {prior_state}")
    allowed = VALID_ORDER_TRANSITIONS.get(prior_state, ())
    if next_state not in allowed and prior_state != next_state:
        if next_state in ORDER_LIFECYCLE_TERMINAL_STATES and prior_state in {"CREATED", "ACTIVATED"}:
            return
        raise ValueError(f"ORDER_TRANSITION_INVALID: {prior_state} -> {next_state}")


def next_event_sequence(events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    return max(int(event.get("sequence", 0)) for event in events) + 1
