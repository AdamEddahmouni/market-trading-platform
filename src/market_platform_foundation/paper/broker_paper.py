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
    ensure_broker_fill_ids,
    is_ambiguous_broker_status,
    map_broker_status,
    normalize_broker_fill,
)
from ..risk.decision import evaluate_risk
from ..market_data.live_config import execution_freshness_threshold_ms
from ..portfolio.ledger import apply_fill
from .contracts import ORDER_LIFECYCLE_TERMINAL_STATES, build_user_order_intent, validate_order_transition
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
    decision_source_snapshot: dict[str, Any] | None = None,
    mark_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Broker paper execution (Platformization P4) — dedicated entry point.

    Idempotent submission with an ``OrderSubmitted``-class record written to the
    ledger **before** any broker network call (P4-IDEM-001 / P4-AMB-001).
    """
    if ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_BROKER_MODE_INVALID")
    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")

    with ledger.admission_lock:
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
            decision_source_snapshot=decision_source_snapshot,
        )
        instrument_id = str(intent["instrument_id"]).upper()
        risk_price, price_source, price_as_of, price_quality, price_error = _broker_risk_price(
            ledger=ledger,
            intent=intent,
            mark_snapshot=mark_snapshot,
            observation_time=observation_time,
        )
        projection = ledger._project_ledger()
        position = dict(projection.get("positions_by_instrument") or {}).get(instrument_id, {})
        reservations = ledger.project_reservations()
        instrument_reservations = dict(reservations.get("by_instrument") or {}).get(instrument_id, {})
        decision = evaluate_risk(
            intent=intent,
            policy=ledger.policy,
            kill_switch=ledger.kill_switch,
            current_position_shares=int(position.get("position_shares", 0)),
            current_cash_minor=int(projection["cash_minor"]),
            reserved_cash_minor=int(reservations.get("reserved_cash_minor", 0)),
            reserved_sell_shares=int(instrument_reservations.get("reserved_sell_shares", 0)),
            risk_price_minor=risk_price,
            risk_price_source=price_source,
            risk_price_as_of_ns=price_as_of,
            risk_price_quality=price_quality,
            risk_price_error=price_error,
            open_order_count=ledger.open_order_count,
        )
        order_id = build_canonical_order_id(intent=intent, decision=decision)

        if decision["decision"] not in {"APPROVE", "RESIZE"}:
            rejected = build_broker_order(
                intent=intent,
                decision=decision,
                state="REJECTED",
                order_id=order_id,
                reason_codes=["BROKER_RISK_NOT_APPROVED"],
            )
            with ledger.atomic_append():
                ledger.append_intent(intent)
                ledger.append_risk_decision(decision)
                ledger.append_order(rejected, intent=intent)
                ledger.record_idempotent_order(
                    idempotency_key=idempotency_key,
                    order_id=order_id,
                )
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

        # Submission record and its reservation are persisted together before
        # any broker network call.
        submitted = build_broker_order(
            intent=intent,
            decision=decision,
            state="SUBMITTED",
            order_id=order_id,
        )
        with ledger.atomic_append():
            ledger.append_intent(intent)
            ledger.append_risk_decision(decision)
            ledger.append_order(submitted, intent=intent)
            ledger.record_idempotent_order(
                idempotency_key=idempotency_key,
                order_id=order_id,
            )
        provider_intent = {**intent, "desired_quantity": int(decision["approved_quantity"])}

    result = provider.place_order(provider_intent)
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

    normalized_fills: list[dict[str, Any]] = []
    for fill_event in status_event.fills:
        normalized_fills.append(
            normalize_broker_fill(
                fill_event,
                order_id=order_id,
                instrument_id=instrument_id,
                direction=str(intent["direction"]),
            )
        )
    ledger.validate_fill_batch(
        order=ledger.lookup_order(order_id) or submitted,
        fills=normalized_fills,
    )

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
    for fill in normalized_fills:
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


def _broker_risk_price(
    *,
    ledger: PaperExecutionLedger,
    intent: dict[str, Any],
    mark_snapshot: dict[str, Any] | None,
    observation_time: int,
) -> tuple[int | None, str | None, int | None, str, str | None]:
    if str(intent.get("order_type", "MARKET")) == "LIMIT":
        price = int(intent.get("limit_price_minor") or 0)
        return price or None, "BROKER_LIMIT_PRICE", observation_time, "PASS", None

    mark = mark_snapshot or ledger._mark_for_instrument(str(intent["instrument_id"]))
    if not isinstance(mark, dict):
        return None, None, None, "UNAVAILABLE", "RISK_PRICE_UNAVAILABLE"
    if str(mark.get("instrument_id", intent["instrument_id"])).upper() != str(intent["instrument_id"]).upper():
        return None, None, None, "UNAVAILABLE", "RISK_PRICE_INSTRUMENT_MISMATCH"
    quality = str(mark.get("mark_quality", "UNAVAILABLE")).upper()
    if quality not in {"PASS", "HEALTHY"}:
        return None, None, None, quality, "RISK_PRICE_UNAVAILABLE"
    as_of = int(mark.get("mark_as_of_ns", 0))
    age_ns = int(observation_time) - as_of
    if age_ns < 0:
        return None, None, as_of, quality, "RISK_PRICE_FUTURE"
    if age_ns > execution_freshness_threshold_ms() * 1_000_000:
        return None, None, as_of, quality, "RISK_PRICE_STALE"
    raw_price = int(mark.get("mark_minor", 0))
    if raw_price <= 0:
        return None, None, as_of, quality, "RISK_PRICE_UNAVAILABLE"
    buffer_bps = int(ledger.policy["broker_market_reserve_buffer_bps"])
    buffered = (raw_price * (10_000 + buffer_bps) + 9_999) // 10_000
    return buffered, "BROKER_MARK_PLUS_BUFFER", as_of, quality, None


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


# Coarse forward-rank over the IMP order ladder, used only to drop lifecycle
# states a polled order has already passed. Equal ranks (WORKING/ACTIVATED,
# terminal states) are considered "not behind" so same-state re-polls stay
# representable.
_LIFECYCLE_RANK: dict[str, int] = {
    "SUBMITTED": 0,
    "WORKING": 1,
    "ACTIVATED": 1,
    "PARTIALLY_FILLED": 2,
    "CANCEL_PENDING": 3,
    "FILLED": 4,
    "CANCELLED": 4,
    "REJECTED": 4,
    "EXPIRED": 4,
}


def _pending_lifecycle_states(current_state: str, target_path: list[str]) -> list[str]:
    """Suffix of ``target_path`` the order in ``current_state`` has not reached.

    Polls return cumulative broker state: an order already PARTIALLY_FILLED
    re-mapped through ``ACTIVATED`` must not replay ``ACTIVATED``, and a
    re-observed current state is idempotent (no duplicate transition event).
    """
    ceiling = len(_LIFECYCLE_RANK)
    rank = _LIFECYCLE_RANK.get(current_state, ceiling)
    # WORKING and ACTIVATED are equivalent admission-stage ranks.  A poll
    # mapped through the other state must not attempt an invalid lateral
    # transition (for example WORKING -> ACTIVATED).
    return [s for s in target_path if _LIFECYCLE_RANK.get(s, ceiling) > rank]


def apply_broker_status_event(
    *,
    ledger: PaperExecutionLedger,
    provider: Any,
    order_id: str,
) -> dict[str, Any]:
    """Poll the broker once and apply the observed ORDER_STATUS to a live order.

    Nothing consumed ``fetch_order`` after submission (E1b), so an order that
    reached the broker as partially_filled and only completed later froze in
    PARTIALLY_FILLED forever. This orchestrator closes that loop:

    - the polled canonical status is mapped through ``_broker_lifecycle_path``
      and applied via ``append_order_state``, skipping states already recorded;
    - fills are deduped on ``broker_fill_id`` (brokers replay cumulative fill
      lists on every poll), so each fill is applied exactly once;
    - it fails closed: malformed payloads, unmapped statuses, or invalid fills
      raise ValueError with the ledger untouched (all validation happens
      before the first append).
    """
    if ledger.execution_mode != "BROKER_PAPER":
        raise ValueError("PAPER_EXECUTION_BROKER_MODE_INVALID")
    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")

    order = ledger.lookup_order(order_id)
    if order is None:
        raise ValueError("PAPER_ORDER_NOT_FOUND")
    state = str(order.get("state", ""))
    if state in ORDER_LIFECYCLE_TERMINAL_STATES:
        return {
            "advanced": False,
            "order": order,
            "order_id": order_id,
            "previous_state": state,
            "state": state,
            "terminal": True,
        }

    broker_order_id = str(order.get("broker_order_id") or "")
    if not broker_order_id:
        raise ValueError("BROKER_ORDER_ID_UNKNOWN")

    result = provider.fetch_order(broker_order_id)
    status = str(getattr(result, "status", "error"))
    reason_code = getattr(result, "reason_code", None)
    if status == "ambiguous":
        # No blind advance; the next successful poll resolves the drift.
        return {
            "advanced": False,
            "ambiguous": True,
            "order_id": order_id,
            "previous_state": state,
            "reason_code": reason_code or "BROKER_AMBIGUOUS_OUTCOME",
        }
    if status != "ok":
        # Transport outage / provider error: no mutation, safe to re-poll.
        return {
            "advanced": False,
            "order_id": order_id,
            "previous_state": state,
            "provider_status": status,
            "reason_code": reason_code,
        }

    payload = _first_broker_status_payload(result)
    if payload is None:
        raise ValueError("BROKER_NO_STATUS")

    try:
        status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(payload))
        target = map_broker_status(status_event.status)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"BROKER_STATUS_EVENT_INVALID: {exc}") from exc

    # Pre-validate the whole transition chain before touching the ledger.
    pending_states = _pending_lifecycle_states(state, _broker_lifecycle_path(target))
    prior = state
    for next_state in pending_states:
        validate_order_transition(prior_state=prior, next_state=next_state)
        prior = next_state

    # Normalize + validate every new fill before any mutation.
    known_fill_ids = {
        str(existing["broker_fill_id"])
        for existing in ledger.project_fills()
        if existing.get("broker_fill_id")
    }
    new_fills: list[dict[str, Any]] = []
    seen_in_event: set[str] = set()
    for fill_event in status_event.fills:
        broker_fill_id = str(fill_event.broker_fill_id)
        if not broker_fill_id or broker_fill_id in known_fill_ids or broker_fill_id in seen_in_event:
            continue
        seen_in_event.add(broker_fill_id)
        if int(fill_event.quantity) <= 0:
            raise ValueError(f"BROKER_FILL_QUANTITY_INVALID: {broker_fill_id}")
        if int(fill_event.price_minor) < 0:
            raise ValueError(f"BROKER_FILL_PRICE_INVALID: {broker_fill_id}")
        if int(fill_event.event_time_ns) > int(fill_event.receive_time_ns):
            # Bitemporal sanity: a broker-side execution cannot be observed
            # before it happened (event_time <= receive_time, E1b gap mining).
            raise ValueError(f"BROKER_FILL_TIME_INVERSION: {broker_fill_id}")
        new_fills.append(
            normalize_broker_fill(
                fill_event,
                order_id=order_id,
                instrument_id=str(order.get("instrument_id", "")),
                direction=str(order.get("direction", "")),
            )
        )

    ledger.validate_fill_batch(order=order, fills=new_fills)

    prior = state
    for next_state in pending_states:
        ledger.append_order_state(
            order_id=order_id,
            state=next_state,
            prior_state=prior,
            broker_order_id=broker_order_id,
        )
        prior = next_state
    for fill in new_fills:
        ledger.append_fill(fill, order=ledger.lookup_order(order_id))

    final_order = ledger.lookup_order(order_id)
    final_state = str((final_order or {}).get("state", prior))
    return {
        "advanced": bool(pending_states or new_fills),
        "applied_states": pending_states,
        "broker_status": status_event.status,
        "fills": new_fills,
        "order": final_order,
        "order_id": order_id,
        "previous_state": state,
        "state": final_state,
    }


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
    # CREATED is deliberately absent (E11): paper/contracts.py
    # VALID_ORDER_TRANSITIONS defines no CREATED -> CANCEL_PENDING edge, so a
    # cancel here would raise ORDER_TRANSITION_INVALID inside ledger.cancel_order
    # only *after* the provider.cancel_order call had already hit the broker.
    # Fail closed before any provider call, consistently with the INTERNAL path.
    if state not in {"ACTIVATED", "WORKING", "SUBMITTED"}:
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
    "apply_broker_status_event",
    "cancel_broker_paper_order",
    "submit_broker_paper_order",
]
