"""Deterministic broker payload translation (BUILD 28 dry-run)."""

from __future__ import annotations

from typing import Any

from ...providers.broker_execution import build_broker_order_request
from .identity import derive_payload_hash
from .types import BrokerOrderIntentV1


def intent_to_canonical_intent_dict(intent: BrokerOrderIntentV1, *, decision_time_ns: int) -> dict[str, Any]:
    """Map BrokerOrderIntentV1 to the canonical intent dict used by P4 adapters."""
    body: dict[str, Any] = {
        "client_order_id": intent.client_order_id,
        "idempotency_key": intent.client_order_id,
        "instrument_id": intent.instrument_id,
        "intent_id": intent.broker_order_intent_id,
        "order_type": intent.order_type,
        "desired_quantity": intent.quantity,
        "created_time": decision_time_ns,
        "side": intent.side,
        "direction": "LONG" if intent.side == "BUY" else "SHORT",
    }
    if intent.limit_price_minor is not None:
        body["limit_price_minor"] = intent.limit_price_minor
    return body


def translate_tradier_payload(
    intent: BrokerOrderIntentV1,
    *,
    broker_symbol: str,
    decision_time_ns: int,
) -> dict[str, Any]:
    canonical = intent_to_canonical_intent_dict(intent, decision_time_ns=decision_time_ns)
    request = build_broker_order_request(canonical, broker_symbol=broker_symbol)
    payload = {
        "provider": "tradier.paper",
        "endpoint": "sandbox",
        "class": request.order_type.lower(),
        "symbol": request.broker_symbol,
        "side": request.side.lower(),
        "quantity": request.quantity,
        "type": request.order_type,
        "duration": intent.time_in_force.lower(),
        "client_order_id": request.client_order_id,
        "preview": False,
    }
    if request.limit_price_minor is not None:
        payload["price"] = request.limit_price_minor / 100.0
    return payload


def translate_moomoo_payload(
    intent: BrokerOrderIntentV1,
    *,
    broker_symbol: str,
    decision_time_ns: int,
) -> dict[str, Any]:
    canonical = intent_to_canonical_intent_dict(intent, decision_time_ns=decision_time_ns)
    request = build_broker_order_request(canonical, broker_symbol=broker_symbol)
    action = "BUY" if request.side == "BUY" else "SELL"
    payload = {
        "provider": "moomoo.paper",
        "trade_env": "SIMULATE",
        "code": request.broker_symbol,
        "qty": request.quantity,
        "price": request.limit_price_minor / 100.0 if request.limit_price_minor else 0.0,
        "order_type": request.order_type,
        "trd_side": action,
        "client_order_id": request.client_order_id,
    }
    return payload


def translate_broker_payload(
    intent: BrokerOrderIntentV1,
    *,
    broker_symbol: str,
    decision_time_ns: int,
) -> tuple[dict[str, Any], str]:
    """Return (provider_payload, payload_hash) deterministically."""
    if intent.broker_target.startswith("tradier"):
        payload = translate_tradier_payload(intent, broker_symbol=broker_symbol, decision_time_ns=decision_time_ns)
    elif intent.broker_target.startswith("moomoo"):
        payload = translate_moomoo_payload(intent, broker_symbol=broker_symbol, decision_time_ns=decision_time_ns)
    else:
        canonical = intent_to_canonical_intent_dict(intent, decision_time_ns=decision_time_ns)
        request = build_broker_order_request(canonical, broker_symbol=broker_symbol)
        payload = request.to_dict()
        payload["provider"] = intent.broker_target
    return payload, derive_payload_hash(payload)


def validate_tick_lot(
    *,
    quantity: int,
    limit_price_minor: int | None,
    tick_size_minor: int = 1,
    lot_size: int = 1,
    fractional_supported: bool = False,
) -> None:
    if quantity <= 0:
        raise ValueError("QUANTITY_INVALID")
    if not fractional_supported and quantity % lot_size != 0:
        raise ValueError("LOT_SIZE_VIOLATION")
    if limit_price_minor is not None and limit_price_minor % tick_size_minor != 0:
        raise ValueError("TICK_SIZE_VIOLATION")
