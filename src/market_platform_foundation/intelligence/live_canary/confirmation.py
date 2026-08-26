"""Per-order human confirmation (BUILD 29)."""

from __future__ import annotations

from ..live_execution_safety.types import BrokerOrderIntentV1
from .identity import derive_order_confirmation_id
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    DEFAULT_ORDER_CONFIRMATION_EXPIRY_NS,
    HumanApprovalSource,
    LiveOrderConfirmationV1,
)


class ConfirmationError(ValueError):
    pass


def build_order_confirmation_preview(
    *,
    authorization_ref: str,
    order_intent: BrokerOrderIntentV1,
    risk_decision_ref: str,
    reference_price_minor: int,
    confirmation_time_ns: int,
    confirmed_by: str = "PENDING",
    confirmation_source: HumanApprovalSource = HumanApprovalSource.OPERATOR_CONSOLE,
    expiry_ns: int | None = None,
) -> LiveOrderConfirmationV1:
    """Create confirmation binding exact order semantics — requires human approval to use."""
    expires = expiry_ns or (confirmation_time_ns + DEFAULT_ORDER_CONFIRMATION_EXPIRY_NS)
    estimated_notional = order_intent.quantity * reference_price_minor
    confirmation = LiveOrderConfirmationV1(
        confirmation_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        authorization_ref=authorization_ref,
        broker_order_intent_ref=order_intent.broker_order_intent_id,
        risk_decision_ref=risk_decision_ref,
        instrument_id=order_intent.instrument_id,
        side=order_intent.side,
        quantity=order_intent.quantity,
        order_type=order_intent.order_type,
        limit_price_minor=order_intent.limit_price_minor,
        estimated_max_notional_minor=estimated_notional,
        confirmation_time_ns=confirmation_time_ns,
        expires_at_ns=expires,
        confirmed_by=confirmed_by,
        confirmation_source=confirmation_source,
    )
    object.__setattr__(confirmation, "confirmation_id", derive_order_confirmation_id(confirmation))
    return confirmation


def confirm_order(
    preview: LiveOrderConfirmationV1,
    *,
    confirmed_by: str,
    confirmation_source: HumanApprovalSource,
    confirmation_time_ns: int,
) -> LiveOrderConfirmationV1:
    """Record explicit human per-order confirmation."""
    confirmed = LiveOrderConfirmationV1(
        confirmation_id=preview.confirmation_id,
        schema_version=preview.schema_version,
        authorization_ref=preview.authorization_ref,
        broker_order_intent_ref=preview.broker_order_intent_ref,
        risk_decision_ref=preview.risk_decision_ref,
        instrument_id=preview.instrument_id,
        side=preview.side,
        quantity=preview.quantity,
        order_type=preview.order_type,
        limit_price_minor=preview.limit_price_minor,
        estimated_max_notional_minor=preview.estimated_max_notional_minor,
        confirmation_time_ns=confirmation_time_ns,
        expires_at_ns=preview.expires_at_ns,
        confirmed_by=confirmed_by,
        confirmation_source=confirmation_source,
        lineage={"confirmed": True},
    )
    return confirmed


def validate_confirmation_for_intent(
    confirmation: LiveOrderConfirmationV1 | None,
    *,
    order_intent: BrokerOrderIntentV1,
    authorization_ref: str,
    decision_time_ns: int,
) -> tuple[bool, str | None]:
    if confirmation is None:
        return False, "MISSING"
    if confirmation.authorization_ref != authorization_ref:
        return False, "AUTHORIZATION_MISMATCH"
    if confirmation.broker_order_intent_ref != order_intent.broker_order_intent_id:
        return False, "INTENT_MISMATCH"
    if confirmation.instrument_id != order_intent.instrument_id:
        return False, "SYMBOL_CHANGED"
    if confirmation.side != order_intent.side:
        return False, "SIDE_CHANGED"
    if confirmation.quantity != order_intent.quantity:
        return False, "QUANTITY_CHANGED"
    if confirmation.order_type != order_intent.order_type:
        return False, "ORDER_TYPE_CHANGED"
    if confirmation.limit_price_minor != order_intent.limit_price_minor:
        return False, "PRICE_CHANGED"
    if decision_time_ns >= confirmation.expires_at_ns:
        return False, "EXPIRED"
    if not confirmation.lineage.get("confirmed"):
        return False, "NOT_CONFIRMED"
    return True, None
