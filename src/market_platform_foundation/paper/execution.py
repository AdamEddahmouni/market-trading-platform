"""Interactive paper order execution through deterministic simulator."""

from __future__ import annotations

from typing import Any

from ..execution.simulator import SIMULATOR_VERSION, BarConservativeSimulator
from ..operating_modes import PAPER_EXECUTION_AUTHORITIES
from ..risk.decision import evaluate_risk
from .contracts import (
    ORDER_LIFECYCLE_TERMINAL_STATES,
    build_instrument_ref,
    build_user_order_intent,
    normalize_execution_intent,
)
from .ledger import PaperExecutionLedger

TERMINAL_ORDER_STATES = ORDER_LIFECYCLE_TERMINAL_STATES


def _ledger_simulator(ledger: PaperExecutionLedger) -> BarConservativeSimulator:
    """One ``BarConservativeSimulator`` per ledger session (E9).

    Participation-cap allocations live in the simulator instance
    (``_bar_allocations``, keyed by bar fill time). Constructing a fresh
    simulator per call let every submission on the same bar re-consume the
    full cap; holding one per ledger keeps INTERNAL_SIMULATION accounting
    cumulative across submissions, exactly like the ledger itself.
    """
    existing = getattr(ledger, "_bar_simulator", None)
    if isinstance(existing, BarConservativeSimulator):
        return existing
    simulator = BarConservativeSimulator(policy=ledger.policy)
    ledger._bar_simulator = simulator  # noqa: SLF001 — same-package session cache
    return simulator


def execute_order_intent(
    *,
    intent: dict[str, Any],
    ledger: PaperExecutionLedger,
    bars: list[dict[str, Any]],
    squeeze_context: dict[str, Any] | None = None,
    simulator: BarConservativeSimulator | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Canonical risk + simulator path shared by preview and submit.

    Submissions share one per-ledger simulator so participation-cap
    allocations accumulate across orders filling on the same bar (E9).
    ``simulator`` overrides that cache for dry-run callers (preview) whose
    fills are never recorded and therefore must not consume bar capacity.
    """
    projection = ledger._project_ledger()
    decision = evaluate_risk(
        intent=intent,
        policy=ledger.policy,
        kill_switch=ledger.kill_switch,
        current_position_shares=int(projection["position_shares"]),
        open_order_count=ledger.open_order_count,
    )
    order, fill = (simulator or _ledger_simulator(ledger)).simulate(
        intent=intent,
        risk_decision=decision,
        bars=bars,
        squeeze_context=squeeze_context,
    )
    return decision, order, fill


def _build_preview_envelope(
    *,
    ledger: PaperExecutionLedger,
    intent: dict[str, Any],
    decision: dict[str, Any],
    order: dict[str, Any],
    fill: dict[str, Any] | None,
    client_order_id: str,
    idempotency_key: str,
    observation_time: int,
) -> dict[str, Any]:
    projection = ledger._project_ledger()
    scale = int(ledger.policy["price_scale"])
    current_position = int(projection["position_shares"])
    projected_position = current_position
    if fill is not None:
        signed = int(fill["fill_quantity"]) if fill["direction"] == "long" else -int(fill["fill_quantity"])
        projected_position += signed

    estimated_notional_minor = 0
    if fill is not None:
        estimated_notional_minor = int(fill["fill_quantity"]) * int(fill["fill_price_minor"])

    current_gross = abs(current_position)
    projected_gross = abs(projected_position)
    current_net = current_position
    projected_net = projected_position

    max_position = int(ledger.policy["max_position_shares"])
    max_order = int(ledger.policy["max_order_shares"])
    position_headroom = max(0, max_position - abs(projected_position))
    order_headroom = max(0, max_order - int(intent.get("desired_quantity", 0)))

    risk_verdict = "PASS" if decision["decision"] in {"APPROVE", "RESIZE"} else "BLOCKED"
    fill_available = fill is not None
    order_reasons = list(order.get("reason_codes") or []) if isinstance(order, dict) else []
    if fill_available:
        quality_state = "PASS"
    elif ledger.data_mode == "LIVE_OBSERVATIONAL" and "SIM_NO_POST_SIGNAL_BAR" in order_reasons:
        quality_state = "WAITING_FOR_ELIGIBLE_LIVE_EVENT"
    else:
        quality_state = "NO_EXECUTABLE_BAR"

    return {
        "client_command_id": client_order_id,
        "client_order_id": client_order_id,
        "correlation_id": intent.get("correlation_id"),
        "data_mode": ledger.data_mode,
        "data_provider": ledger.data_provider,
        "decision": decision["decision"],
        "estimated_gross_exposure_shares": projected_gross,
        "estimated_net_exposure_shares": projected_net,
        "estimated_notional_minor": estimated_notional_minor,
        "execution_authority": ledger.execution_authority,
        "execution_mode": ledger.execution_mode,
        "execution_model": "BarConservativeSimulator",
        "execution_model_version": SIMULATOR_VERSION,
        "execution_provider": ledger.execution_provider,
        "fill_preview": fill,
        "fill_preview_available": fill_available,
        "idempotency_key": idempotency_key,
        "instrument": intent.get("instrument"),
        "intent": intent,
        "limit_price_minor": intent.get("limit_price_minor"),
        "market_data_available_time": observation_time,
        "order_preview": order,
        "order_type": intent.get("order_type", "MARKET"),
        "projected_position_shares": projected_position,
        "quality_state": quality_state,
        "reason_codes": decision.get("reason_codes", []),
        "risk_limits": {
            "max_open_orders": int(ledger.policy["max_open_orders"]),
            "max_order_shares": max_order,
            "max_position_shares": max_position,
        },
        "risk_status": risk_verdict,
        "risk_utilization": {
            "open_order_count": ledger.open_order_count,
            "open_order_headroom": max(0, int(ledger.policy["max_open_orders"]) - ledger.open_order_count),
            "order_headroom_shares": order_headroom,
            "position_headroom_shares": position_headroom,
        },
        "side": intent.get("side"),
        "current_gross_exposure_shares": current_gross,
        "current_net_exposure_shares": current_net,
        "current_position_shares": current_position,
        "quantity": int(intent.get("desired_quantity", 0)),
        "simulation_model": SIMULATOR_VERSION,
    }


def preview_interactive_order(
    *,
    ledger: PaperExecutionLedger,
    bars: list[dict[str, Any]],
    symbol: str,
    instrument_id: str,
    side: str,
    quantity: int,
    observation_time: int,
    client_order_id: str,
    idempotency_key: str,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    correlation_id: str | None = None,
    decision_source_snapshot: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intent = build_user_order_intent(
        instrument=build_instrument_ref(instrument_id=instrument_id, symbol=symbol),
        side=side,
        quantity=quantity,
        observation_time=observation_time,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        decision_source_snapshot=decision_source_snapshot,
    )
    # Dry-run: a preview fill is never recorded, so it must not consume the
    # session's per-bar participation capacity (E9) — use a throwaway simulator.
    decision, order, fill = execute_order_intent(
        intent=intent,
        ledger=ledger,
        bars=bars,
        squeeze_context=squeeze_context,
        simulator=BarConservativeSimulator(policy=ledger.policy),
    )
    return _build_preview_envelope(
        ledger=ledger,
        intent=intent,
        decision=decision,
        order=order,
        fill=fill,
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        observation_time=observation_time,
    )


def submit_interactive_order(
    *,
    ledger: PaperExecutionLedger,
    bars: list[dict[str, Any]],
    symbol: str,
    instrument_id: str,
    side: str,
    quantity: int,
    observation_time: int,
    client_order_id: str,
    idempotency_key: str,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    correlation_id: str | None = None,
    decision_source_snapshot: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")
    if ledger.execution_mode != "INTERNAL_SIMULATION":
        raise ValueError("PAPER_EXECUTION_MODE_INVALID")

    intent = build_user_order_intent(
        instrument=build_instrument_ref(instrument_id=instrument_id, symbol=symbol),
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
    ledger.append_intent(intent)
    decision, order, fill = execute_order_intent(
        intent=intent,
        ledger=ledger,
        bars=bars,
        squeeze_context=squeeze_context,
    )
    ledger.append_risk_decision(decision)
    ledger.append_order(order, intent=intent)
    if fill is not None:
        ledger.append_fill(fill, order=order)
    ledger.record_idempotent_order(idempotency_key=idempotency_key, order_id=str(order["order_id"]))
    return {
        "correlation_id": intent.get("correlation_id"),
        "decision": decision["decision"],
        "duplicate": False,
        "execution_attempt_id": order.get("order_id"),
        "fill": fill,
        "fill_id": fill.get("fill_id") if fill else None,
        "idempotency_key": idempotency_key,
        "intent_id": intent["intent_id"],
        "order": order,
        "order_id": order.get("order_id"),
        "risk_decision_id": decision.get("intent_id"),
    }


def cancel_interactive_order(
    *,
    ledger: PaperExecutionLedger,
    order_id: str,
) -> dict[str, Any]:
    """Cancel path for paper orders. BarConservativeSimulator fills synchronously."""
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
    # cancel of a CREATED order would raise ORDER_TRANSITION_INVALID inside
    # ledger.cancel_order anyway. Fall through to the explicit
    # PAPER_ORDER_CANCEL_INVALID_STATE sentinel below — the same observable
    # behaviour as the BROKER_PAPER path in broker_paper.py.
    if state in {"ACTIVATED", "WORKING"}:
        cancelled = ledger.cancel_order(order_id=order_id, prior_state=state)
        return {
            "duplicate": False,
            "order": cancelled,
            "order_id": order_id,
            "state": "CANCELLED",
        }
    raise ValueError(f"PAPER_ORDER_CANCEL_INVALID_STATE: {state}")


def execute_normalized_intent_for_parity(
    *,
    intent: dict[str, Any],
    policy: dict[str, Any],
    bars: list[dict[str, Any]],
    current_position_shares: int = 0,
    open_order_count: int = 0,
    squeeze_context: dict[str, Any] | None = None,
    simulator: BarConservativeSimulator | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Dry-run canonical execution for parity tests (no ledger writes)."""
    from ..risk.kill_switch import KillSwitchState

    normalized = normalize_execution_intent(intent)
    decision = evaluate_risk(
        intent=normalized,
        policy=policy,
        kill_switch=KillSwitchState(),
        current_position_shares=current_position_shares,
        open_order_count=open_order_count,
    )
    # Fresh instance by default keeps historical dry-run semantics (zero
    # starting allocations); callers replaying a whole session can thread one
    # shared simulator through to mirror INTERNAL_SIMULATION accumulation (E9).
    simulator = simulator or BarConservativeSimulator(policy=policy)
    order, fill = simulator.simulate(
        intent=normalized,
        risk_decision=decision,
        bars=bars,
        squeeze_context=squeeze_context,
    )
    return decision, order, fill

