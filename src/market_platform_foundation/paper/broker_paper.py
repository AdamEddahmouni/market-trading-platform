"""Broker paper execution entry points (Platformization P4, sub-milestone 4A).

Dedicated broker-facing path, kept in its own module so that
``paper/execution.py`` (the INTERNAL_SIMULATION path) never references a
broker trade verb such as ``place_order`` (P3.1 live-safety guard, audit F3).
The ``submit_interactive_order`` INTERNAL_SIMULATION guard is not loosened
(P4-SAFE-003).
"""

from __future__ import annotations

from typing import Any

from ..operating_modes import PAPER_EXECUTION_AUTHORITIES
from ..providers.broker_execution import (
    BrokerOrderStatusEvent,
    build_broker_order,
    build_canonical_order_id,
    is_ambiguous_broker_status,
    map_broker_status,
    normalize_broker_fill,
)
from ..risk.decision import evaluate_risk
from .contracts import build_user_order_intent
from .ledger import PaperExecutionLedger


def _broker_lifecycle_path(target: str) -> list[str]:
    """Valid OrderStateChanged path from SUBMITTED to a broker-mapped target."""
    if target == "WORKING":
        return ["WORKING"]
    if target == "ACTIVATED":
        return ["ACTIVATED"]
    if target == "PARTIALLY_FILLED":
        return ["ACTIVATED", "PARTIALLY_FILLED"]
    if target == "FILLED":
        return ["ACTIVATED", "FILLED"]
    if target == "CANCELLED":
        return ["CANCEL_PENDING", "CANCELLED"]
    if target == "REJECTED":
        return ["REJECTED"]
    if target == "EXPIRED":
        return ["WORKING", "EXPIRED"]
    raise ValueError(f"BROKER_TARGET_STATE_UNREACHABLE: {target}")


def submit_broker_paper_order(
    *,
    ledger: PaperExecutionLedger,
    provider: Any,
    instrument: dict[str, Any],
    side: str,
    quantity: int,
    observation_time: int,
    client_order_id: str,
    idempotency_key: str,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Broker paper execution (Platformization P4) — dedicated entry point.

    Idempotent submission with an ``OrderSubmitted``-class record written to the
    ledger **before** any broker network call (P4-IDEM-001 / P4-AMB-001).
    """
    if ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_BROKER_MODE_INVALID")
    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")

    existing_order_id = ledger.lookup_idempotent_order(idempotency_key)
    if existing_order_id:
        for order in ledger.project_orders():
            if order.get("order_id") == existing_order_id:
                return {
                    "duplicate": True,
                    "idempotency_key": idempotency_key,
                    "order": order,
                    "order_id": existing_order_id,
                }
        return {
            "duplicate": True,
            "idempotency_key": idempotency_key,
            "order_id": existing_order_id,
        }

    intent = build_user_order_intent(
        instrument=instrument,
        side=side,
        quantity=quantity,
        observation_time=observation_time,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id or client_order_id,
    )
    ledger.append_intent(intent)

    projection = ledger._project_ledger()
    decision = evaluate_risk(
        intent=intent,
        policy=ledger.policy,
        kill_switch=ledger.kill_switch,
        current_position_shares=int(projection["position_shares"]),
        open_order_count=ledger.open_order_count,
    )
    ledger.append_risk_decision(decision)
    order_id = build_canonical_order_id(intent=intent, decision=decision)
    instrument_id = str(intent["instrument_id"])

    if decision["decision"] not in {"APPROVE", "RESIZE"}:
        rejected = build_broker_order(
            intent=intent,
            decision=decision,
            state="REJECTED",
            order_id=order_id,
            reason_codes=["BROKER_RISK_NOT_APPROVED"],
        )
        ledger.append_order(rejected, intent=intent)
        ledger.record_idempotent_order(idempotency_key=idempotency_key, order_id=order_id)
        return {
            "decision": decision["decision"],
            "duplicate": False,
            "execution_attempt_id": order_id,
            "idempotency_key": idempotency_key,
            "intent_id": intent["intent_id"],
            "order": rejected,
            "order_id": order_id,
            "rejected": True,
            "reason_codes": decision.get("reason_codes", []),
            "risk_decision_id": decision.get("intent_id"),
        }

    # Submission record BEFORE any broker network call.
    submitted = build_broker_order(
        intent=intent,
        decision=decision,
        state="SUBMITTED",
        order_id=order_id,
    )
    ledger.append_order(submitted, intent=intent)
    ledger.record_idempotent_order(idempotency_key=idempotency_key, order_id=order_id)

    result = provider.place_order(intent)
    status = str(getattr(result, "status", "error"))
    reason_code = getattr(result, "reason_code", None)

    if status == "ambiguous" or (status == "ok" and _broker_events_ambiguous(result)):
        # Ambiguous outcome: no blind retry; resolve via fetch / reconciliation.
        ledger.append_order_state(
            order_id=order_id,
            state="SUBMITTED",
            prior_state="SUBMITTED",
            reason_codes=["BROKER_AMBIGUOUS_OUTCOME"],
        )
        return {
            "ambiguous": True,
            "correlation_id": intent.get("correlation_id"),
            "idempotency_key": idempotency_key,
            "intent_id": intent["intent_id"],
            "order": ledger.lookup_order(order_id),
            "order_id": order_id,
            "reason_code": reason_code or "BROKER_AMBIGUOUS_OUTCOME",
            "risk_decision_id": decision.get("intent_id"),
        }

    if status != "ok":
        reason = reason_code or "BROKER_REJECTED"
        ledger.append_order_state(
            order_id=order_id,
            state="REJECTED",
            prior_state="SUBMITTED",
            reason_codes=[reason],
        )
        return {
            "decision": decision["decision"],
            "duplicate": False,
            "execution_attempt_id": order_id,
            "idempotency_key": idempotency_key,
            "intent_id": intent["intent_id"],
            "order": ledger.lookup_order(order_id),
            "order_id": order_id,
            "rejected": True,
            "reason_codes": [reason],
            "risk_decision_id": decision.get("intent_id"),
        }

    broker_event = _first_broker_status_payload(result)
    if broker_event is None:
        ledger.append_order_state(
            order_id=order_id,
            state="REJECTED",
            prior_state="SUBMITTED",
            reason_codes=[reason_code or "BROKER_NO_STATUS"],
        )
        return {
            "rejected": True,
            "idempotency_key": idempotency_key,
            "order_id": order_id,
            "reason_codes": [reason_code or "BROKER_NO_STATUS"],
        }

    try:
        status_event = BrokerOrderStatusEvent.from_record(broker_event)
        target = map_broker_status(status_event.status)
    except (KeyError, ValueError, TypeError):
        ledger.append_order_state(
            order_id=order_id,
            state="REJECTED",
            prior_state="SUBMITTED",
            reason_codes=["BROKER_STATUS_UNMAPPED"],
        )
        return {
            "rejected": True,
            "idempotency_key": idempotency_key,
            "order_id": order_id,
            "reason_codes": ["BROKER_STATUS_UNMAPPED"],
        }

    broker_order_id = str(status_event.broker_order_id or "")
    if not broker_order_id:
        ledger.append_order_state(
            order_id=order_id,
            state="REJECTED",
            prior_state="SUBMITTED",
            reason_codes=["BROKER_NO_ORDER_ID"],
        )
        return {
            "rejected": True,
            "idempotency_key": idempotency_key,
            "order_id": order_id,
            "reason_codes": ["BROKER_NO_ORDER_ID"],
        }

    prior = "SUBMITTED"
    for state in _broker_lifecycle_path(target):
        ledger.append_order_state(
            order_id=order_id,
            state=state,
            prior_state=prior,
            broker_order_id=broker_order_id,
        )
        prior = state

    fills: list[dict[str, Any]] = []
    for fill_event in status_event.fills:
        fill = normalize_broker_fill(
            fill_event,
            order_id=order_id,
            instrument_id=instrument_id,
            direction=str(intent["direction"]),
        )
        ledger.append_fill(fill, order=ledger.lookup_order(order_id))
        fills.append(fill)

    order = ledger.lookup_order(order_id)
    return {
        "broker_order_id": broker_order_id,
        "broker_status": status_event.status,
        "correlation_id": intent.get("correlation_id"),
        "decision": decision["decision"],
        "duplicate": False,
        "execution_attempt_id": order_id,
        "fill": fills[-1] if fills else None,
        "fill_id": fills[-1].get("fill_id") if fills else None,
        "fills": fills,
        "idempotency_key": idempotency_key,
        "intent_id": intent["intent_id"],
        "order": order,
        "order_id": order_id,
        "risk_decision_id": decision.get("intent_id"),
    }


def _first_broker_status_payload(result: Any) -> dict[str, Any] | None:
    for event in getattr(result, "events", ()) or ():
        if isinstance(event, dict) and event.get("broker_event_type") == "ORDER_STATUS":
            payload = event.get("payload")
            if isinstance(payload, dict):
                return payload
    return None


def _broker_events_ambiguous(result: Any) -> bool:
    payload = _first_broker_status_payload(result)
    if payload is None:
        return False
    return is_ambiguous_broker_status(str(payload.get("status", "")))


def cancel_broker_paper_order(
    *,
    ledger: PaperExecutionLedger,
    provider: Any,
    order_id: str,
) -> dict[str, Any]:
    """Cancel a broker paper order (dedicated entry point, P4-SAFE-003)."""
    if ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_BROKER_MODE_INVALID")
    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")

    order = ledger.lookup_order(order_id)
    if order is None:
        raise ValueError("PAPER_ORDER_NOT_FOUND")

    state = str(order.get("state", ""))
    if state in {"CANCELLED", "CANCEL_PENDING"}:
        return {
            "duplicate": True,
            "order": order,
            "order_id": order_id,
            "state": state,
        }
    if state in {"FILLED", "PARTIALLY_FILLED"}:
        raise ValueError("PAPER_ORDER_CANCEL_NOT_SUPPORTED: order already filled")
    if state in {"REJECTED", "EXPIRED"}:
        return {
            "duplicate": False,
            "order": order,
            "order_id": order_id,
            "state": state,
            "terminal": True,
        }
    if state not in {"CREATED", "ACTIVATED", "WORKING", "SUBMITTED"}:
        raise ValueError(f"PAPER_ORDER_CANCEL_INVALID_STATE: {state}")

    if not hasattr(provider, "cancel_order"):
        raise ValueError("BROKER_CANCEL_UNSUPPORTED")

    result = provider.cancel_order(
        client_order_id=order.get("client_order_id"),
        broker_order_id=order.get("broker_order_id"),
    )
    status = str(getattr(result, "status", "error"))
    if status == "ambiguous":
        ledger.append_order_state(
            order_id=order_id,
            state="CANCEL_PENDING",
            prior_state=state,
            reason_codes=["BROKER_CANCEL_AMBIGUOUS_OUTCOME"],
            broker_order_id=order.get("broker_order_id"),
        )
        return {
            "ambiguous": True,
            "order": ledger.lookup_order(order_id),
            "order_id": order_id,
            "state": "CANCEL_PENDING",
        }
    if status != "ok":
        raise ValueError(f"BROKER_CANCEL_REJECTED: {getattr(result, 'reason_code', 'UNKNOWN')}")

    cancelled = ledger.cancel_order(order_id=order_id, prior_state=state)
    return {
        "duplicate": False,
        "order": cancelled,
        "order_id": order_id,
        "state": "CANCELLED",
    }


__all__ = [
    "cancel_broker_paper_order",
    "submit_broker_paper_order",
]
