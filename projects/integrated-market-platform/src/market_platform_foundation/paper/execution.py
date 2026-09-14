"""Interactive paper order execution through deterministic simulator."""

from __future__ import annotations

from typing import Any, Mapping

from ..execution.fill_model import LIVE_EXECUTION_FORBIDDEN, FillModelLiveForbidden
from ..execution.simulator import SIMULATOR_VERSION, BarConservativeSimulator
from ..numeric import decimal_to_minor_units
from ..operating_modes import PAPER_EXECUTION_AUTHORITIES
from ..risk.decision import evaluate_risk
from ..risk.financial import canonical_order_multiplier
from ..risk.pretrade import PreTradeRiskContext, evaluate_pretrade
from ..rt01.context import current_context
from ..rt01.enums import TraceStage, TraceStatus
from ..rt01.tracer import get_tracer
from .contracts import (
    ORDER_LIFECYCLE_TERMINAL_STATES,
    build_instrument_ref,
    build_semantic_intent_digest,
    build_user_order_intent,
    normalize_execution_intent,
)
from .ledger import PaperExecutionLedger


def _market_price_reference_minor(ledger: PaperExecutionLedger, bars: list[dict[str, Any]]) -> int | None:
    """Conservative submit-time price reference for MARKET orders (G3 §24).

    Uses the last available bar's close (high for buys when close is absent)
    so a MARKET buy is never priced at zero or silently assumed affordable.
    """
    if not bars:
        return None
    payload = bars[-1].get("bar_payload")
    if not isinstance(payload, dict):
        return None
    for key in ("close", "high"):
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            return decimal_to_minor_units(str(raw), scale=int(ledger.policy["price_scale"]))
        except ValueError:
            continue
    return None


def _enforce_pretrade_admission(
    *,
    ledger: PaperExecutionLedger,
    intent: dict[str, Any],
    bars: list[dict[str, Any]],
    reference_price_minor: int | None = None,
) -> None:
    """Final server-side pre-trade gate at submission (G3/G13).

    Dispatches through ``evaluate_pretrade`` for equities, options, and
    futures. Cash-funded buys, margin-gated futures opens, and sell-to-close
    semantics are enforced here; uncovered shorts fail closed.
    """
    side = str(intent.get("side", "")).upper()
    order_type = str(intent.get("order_type", "MARKET"))
    limit = intent.get("limit_price_minor")
    price_minor = (
        int(limit)
        if order_type == "LIMIT" and limit is not None
        else reference_price_minor
        if reference_price_minor is not None
        else _market_price_reference_minor(ledger, bars)
    )
    instrument = intent.get("instrument") or {}
    account = ledger.project_account()
    projection = ledger._project_ledger()
    kind = str(instrument.get("instrument_kind", "TRADABLE_SECURITY")).upper()
    position_qty = int(projection.get("position_shares", 0))
    if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
        canonical_pos = ledger.canonical_portfolio.get_position(str(intent.get("instrument_id", "")))
        if canonical_pos is not None:
            position_qty = int(canonical_pos.quantity)
    margin_facts = intent.get("margin_facts")
    margin_revision = ""
    if margin_facts is not None:
        from ..risk.margin_facts import MarginRequirementFacts

        facts = (
            margin_facts
            if isinstance(margin_facts, MarginRequirementFacts)
            else MarginRequirementFacts.from_dict(margin_facts)
        )
        margin_revision = facts.revision_digest()
    context = PreTradeRiskContext(
        operational_identity=str(intent.get("client_order_id", "")),
        account_id=str(ledger.paper_account_id),
        mode=str(ledger.execution_mode),
        instrument_id=str(intent.get("instrument_id", "")),
        asset_class=str(instrument.get("asset_class", "EQUITY")),
        instrument_kind=str(instrument.get("instrument_kind", "TRADABLE_SECURITY")),
        symbol=str(instrument.get("symbol", intent.get("instrument_id", ""))),
        contract_multiplier=canonical_order_multiplier(instrument),
        side=side,
        quantity=int(intent.get("desired_quantity", 0)),
        order_type=order_type,
        limit_price_minor=int(limit) if limit is not None else None,
        reference_price_minor=price_minor,
        currency=str(
            intent.get("currency")
            or instrument.get("currency")
            or ledger.policy.get("currency", "USD")
        ),
        account_currency=str(ledger.policy.get("currency", "USD")),
        portfolio_cash_minor=int(account.get("cash_minor", 0)),
        # G4 Phase 6: the Paper ledger funds one currency; its bucket is
        # supplied as per-currency cash so a non-USD order fails closed with
        # INSUFFICIENT_SETTLEMENT_CURRENCY (bucket missing) instead of any
        # silent conversion.
        currency_cash_minor={
            str(ledger.policy.get("currency", "USD")).upper(): int(account.get("cash_minor", 0))
        },
        position_quantity=position_qty,
        risk_policy_revision=str(ledger.policy.get("risk_policy_identity_hash", "")),
        margin_facts=(
            margin_facts
            if margin_facts is None
            or isinstance(margin_facts, MarginRequirementFacts)
            else MarginRequirementFacts.from_dict(margin_facts)
        )
        if margin_facts is not None
        else None,
        margin_facts_revision=margin_revision,
        price_scale=int(ledger.policy.get("price_scale", 100)),
        source_time_ns=int(intent.get("created_time", 0)),
    )
    if side == "BUY" or kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
        if side == "BUY" and kind in {"OPTION_CONTRACT", "TRADABLE_SECURITY", "ETF_FUND", "CRYPTO_PAIR"}:
            if price_minor is None:
                raise ValueError("REQUIRED_PRICE_MISSING: no price reference for pre-trade check")
        decision = evaluate_pretrade(context)
        if not decision.accepted:
            raise ValueError(
                f"{decision.reason_codes[0] if decision.reason_codes else 'RISK_REJECTED'}: "
                f"{{'required_cash_minor': {decision.required_cash_minor}, "
                f"'available_cash_minor': {decision.available_cash_minor}}}"
            )

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
    if str(ledger.execution_mode).upper() == "LIVE":
        raise FillModelLiveForbidden(LIVE_EXECUTION_FORBIDDEN)
    intent = dict(intent)
    intent.setdefault("execution_mode", ledger.execution_mode)
    projection = ledger._project_ledger()
    decision = evaluate_risk(
        intent=intent,
        policy=ledger.policy,
        kill_switch=ledger.kill_switch,
        current_position_shares=int(projection["position_shares"]),
        open_order_count=ledger.open_order_count,
    )
    if intent.get("lineage_refs"):
        decision["lineage_refs"] = intent["lineage_refs"]
    if intent.get("quantity_facts"):
        decision["quantity_facts"] = intent["quantity_facts"]
    if intent.get("risk_decision_id"):
        decision["risk_decision_id"] = intent["risk_decision_id"]
    order, fill = (simulator or _ledger_simulator(ledger)).simulate(
        intent=intent,
        risk_decision=decision,
        bars=bars,
        squeeze_context=squeeze_context,
    )
    for key in (
        "lineage_refs",
        "quantity_facts",
        "risk_decision_id",
        "allocation_desired_quantity",
        "allocation_desired_notional_minor",
        "proposal_requested_quantity",
        "proposal_requested_notional_minor",
        "risk_approved_quantity",
        "risk_approved_notional_minor",
    ):
        if key in intent:
            order[key] = intent[key]
    facts = intent.get("quantity_facts")
    if isinstance(facts, dict):
        if facts.get("proposal_requested_quantity") is not None:
            order["requested_quantity"] = facts["proposal_requested_quantity"]
        if facts.get("risk_approved_quantity") is not None:
            order["approved_quantity"] = facts["risk_approved_quantity"]
    order["submitted_quantity"] = int(decision.get("approved_quantity", 0))
    if fill is not None:
        for key in ("lineage_refs", "quantity_facts"):
            if key in intent:
                fill[key] = intent[key]
        fill["submitted_quantity"] = int(decision.get("approved_quantity", 0))
        fill["filled_quantity"] = int(fill["fill_quantity"])
        if intent.get("risk_decision_id"):
            fill["risk_decision_id"] = intent["risk_decision_id"]
        if isinstance(facts, dict):
            if facts.get("proposal_requested_quantity") is not None:
                fill["requested_quantity"] = facts["proposal_requested_quantity"]
            if facts.get("risk_approved_quantity") is not None:
                fill["approved_quantity"] = facts["risk_approved_quantity"]
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
    lineage_refs: tuple[Any, ...] | list[Any] = (),
    quantity_facts: Mapping[str, Any] | None = None,
    risk_decision_id: str | None = None,
    squeeze_context: dict[str, Any] | None = None,
    instrument: Mapping[str, Any] | None = None,
    margin_facts: Any = None,
) -> dict[str, Any]:
    intent = build_user_order_intent(
        instrument=instrument if instrument is not None else build_instrument_ref(instrument_id=instrument_id, symbol=symbol),
        side=side,
        quantity=quantity,
        observation_time=observation_time,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        decision_source_snapshot=decision_source_snapshot,
        lineage_refs=lineage_refs,
        quantity_facts=quantity_facts,
        risk_decision_id=risk_decision_id,
    )
    if margin_facts is not None:
        from ..risk.margin_facts import MarginRequirementFacts

        if isinstance(margin_facts, MarginRequirementFacts):
            intent["margin_facts"] = margin_facts.to_dict()
        else:
            intent["margin_facts"] = margin_facts
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


def submit_interactive_order(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Submit an internal Paper order and emit an optional RT-01 span."""
    context = current_context()
    span = None
    if context is not None:
        span = get_tracer().start_span(
            TraceStage.ORDER_READY,
            "submit_internal_paper_order",
            parent=context,
            input_ref=str(kwargs.get("client_order_id") or "paper-order"),
        )
    try:
        result = _submit_interactive_order(*args, **kwargs)
    except Exception as exc:
        if span is not None:
            span.end(
                status=TraceStatus.ERROR,
                error_class=type(exc).__name__,
                error_code=type(exc).__name__,
            )
        raise
    if span is not None:
        span.end(output_ref=str(result.get("order_id") or "no-order"))
    return result


def _submit_interactive_order(
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
    lineage_refs: tuple[Any, ...] | list[Any] = (),
    quantity_facts: Mapping[str, Any] | None = None,
    risk_decision_id: str | None = None,
    squeeze_context: dict[str, Any] | None = None,
    instrument: Mapping[str, Any] | None = None,
    reference_price_minor: int | None = None,
    margin_facts: Any = None,
) -> dict[str, Any]:
    intent = build_user_order_intent(
        instrument=instrument if instrument is not None else build_instrument_ref(instrument_id=instrument_id, symbol=symbol),
        side=side,
        quantity=quantity,
        observation_time=observation_time,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id or client_order_id,
        decision_source_snapshot=decision_source_snapshot,
        lineage_refs=lineage_refs,
        quantity_facts=quantity_facts,
        risk_decision_id=risk_decision_id,
    )
    if margin_facts is not None:
        from ..risk.margin_facts import MarginRequirementFacts

        if isinstance(margin_facts, MarginRequirementFacts):
            intent["margin_facts"] = margin_facts.to_dict()
        else:
            intent["margin_facts"] = margin_facts
    with ledger.submit_critical_section():
        existing_order_id = ledger.lookup_idempotent_order(idempotency_key)
        if existing_order_id:
            existing = ledger.lookup_order(existing_order_id)
            existing_digest = (existing or {}).get("intent_digest")
            if existing_digest is None:
                recorded = ledger.lookup_intent_for_order(existing_order_id)
                existing_digest = build_semantic_intent_digest(recorded) if recorded else None
            if existing_digest is not None and existing_digest != build_semantic_intent_digest(intent):
                raise ValueError(
                    "IDEMPOTENCY_CONFLICT: same idempotency key submitted with a different order intent"
                )
            if existing is not None:
                return {
                    "duplicate": True,
                    "idempotency_key": idempotency_key,
                    "order": existing,
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

        _enforce_pretrade_admission(
            ledger=ledger,
            intent=intent,
            bars=bars,
            reference_price_minor=reference_price_minor,
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
            "risk_decision_id": decision.get("risk_decision_id") or intent.get("risk_decision_id"),
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
    if state == "FILLED":
        raise ValueError("PAPER_ORDER_CANCEL_NOT_SUPPORTED: order already filled")
    if state in {"PARTIALLY_FILLED", "REPLACED"}:
        # G3 §40: cancel applies to the working remainder only. Prior fills are
        # immutable ledger events and stay intact; only the open remainder
        # transitions to CANCEL_PENDING -> CANCELLED. A replaced order is
        # still working (its remainder is the replaced total minus fills), so
        # it is cancellable the same way (G3 §41/§42).
        cancelled = ledger.cancel_order(order_id=order_id, prior_state=state)
        return {
            "duplicate": False,
            "filled_quantity": int(order.get("cumulative_filled_quantity", 0)),
            "order": cancelled,
            "order_id": order_id,
            "state": "CANCELLED",
            "working_remaining": 0,
        }
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


def replace_interactive_order(
    *,
    ledger: PaperExecutionLedger,
    order_id: str,
    replaced_quantity: int,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
) -> dict[str, Any]:
    """Replace the working remainder of an open Paper order (G3 §41–43, BL-0205).

    Only a working remainder is replaceable: prior fills are immutable ledger
    events and stay intact; the replacement total must not fall below the
    cumulative filled quantity (G3 §41). Instrument identity, side, account,
    and mode cannot change — replacement modifies remaining quantity and/or
    price only (G3 §43). Reservation is recomputed atomically against the
    canonical available cash minus other working obligations, with this
    order's old obligation replaced by the new remainder's requirement
    (G3 §42). Idempotent replace retries return the recorded replacement.
    """
    if ledger.execution_authority not in PAPER_EXECUTION_AUTHORITIES:
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")
    if not isinstance(replaced_quantity, int) or isinstance(replaced_quantity, bool) or replaced_quantity <= 0:
        raise ValueError("ORDER_QUANTITY_INVALID")
    if limit_price_minor is not None and (not isinstance(limit_price_minor, int) or limit_price_minor < 0):
        raise ValueError("ORDER_LIMIT_PRICE_INVALID")
    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError("ORDER_TYPE_INVALID")

    order = ledger.lookup_order(order_id)
    if order is None:
        raise ValueError("PAPER_ORDER_NOT_FOUND")
    state = str(order.get("state", ""))
    if state not in {"WORKING", "ACTIVATED", "PARTIALLY_FILLED", "REPLACED"}:
        raise ValueError(f"PAPER_ORDER_REPLACE_INVALID_STATE: {state}")

    cumulative_filled = int(order.get("cumulative_filled_quantity", 0))
    if replaced_quantity < cumulative_filled:
        raise ValueError(
            f"PAPER_ORDER_REPLACE_BELOW_FILLED: replaced {replaced_quantity} < filled {cumulative_filled}"
        )

    if str(order.get("side", "")).upper() == "BUY":
        price_minor = int(limit_price_minor) if order_type == "LIMIT" and limit_price_minor is not None else _replace_price_reference_minor(ledger, order)
        reason, facts = _replace_financial_check(
            ledger=ledger,
            order=order,
            replaced_quantity=replaced_quantity,
            price_minor=price_minor,
        )
        if reason:
            raise ValueError(f"{reason}: {facts}")

    return ledger.replace_order(
        order_id=order_id,
        prior_state=state,
        replaced_quantity=replaced_quantity,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        client_order_id=order.get("client_order_id"),
    )


def _replace_price_reference_minor(ledger: PaperExecutionLedger, order: Mapping[str, Any]) -> int | None:
    """Submit-time price reference for a MARKET replacement (G3 §42).

    Uses the order's last fill price (or the live mark) when no limit price
    is given — never silently zero. Callers that lack any price evidence
    fail closed through the financial gate instead of pricing the remainder
    at zero.
    """
    for key in ("average_fill_minor", "fill_price_minor", "mark_minor"):
        value = order.get(key)
        if value is not None:
            return int(value)
    return None


def _replace_financial_check(
    *,
    ledger: PaperExecutionLedger,
    order: Mapping[str, Any],
    replaced_quantity: int,
    price_minor: int | None,
) -> tuple[str | None, dict[str, Any]]:
    """Atomic reservation recheck for a replacement (G3 §42).

    ``available`` is canonical cash minus other working obligations; the
    replaced order's own old obligation is excluded and replaced by the new
    remainder's requirement, so raising the price of the working remainder is
    rechecked against real headroom rather than the order's own reservation.
    """
    from ..risk.financial import available_cash_minor, working_order_obligations_minor

    account = ledger.project_account()
    cash = int(account.get("cash_minor", 0))
    order_id = str(order.get("order_id", ""))
    # G4: one canonical obligation formula — the replace recheck excludes the
    # replaced order's own old reservation via the shared helper instead of a
    # duplicated local loop (which could drift from the gate's semantics).
    other_obligations = working_order_obligations_minor(ledger, exclude_order_id=order_id)
    working_remaining = max(0, replaced_quantity - int(order.get("cumulative_filled_quantity", 0)))
    from ..risk.financial import canonical_order_multiplier

    kind = str(order.get("instrument_kind", "TRADABLE_SECURITY")).upper()
    if kind == "FUTURE_CONTRACT":
        intent = ledger.lookup_intent_for_order(order_id)
        margin_raw = (intent or {}).get("margin_facts")
        if margin_raw is None:
            return "MARGIN_MISSING", {"order_id": order_id, "working_remaining": working_remaining}
        from ..risk.margin_facts import MarginRequirementFacts, required_margin_minor

        facts = (
            margin_raw
            if isinstance(margin_raw, MarginRequirementFacts)
            else MarginRequirementFacts.from_dict(margin_raw)
        )
        required = required_margin_minor(
            facts=facts,
            contracts=working_remaining,
            scale=int(ledger.policy.get("price_scale", 100)),
        )
    else:
        if price_minor is None:
            return "REQUIRED_PRICE_MISSING", {"order_id": order_id}
        required = working_remaining * int(price_minor) * canonical_order_multiplier(order)
    available = max(0, cash - other_obligations)
    if required > available:
        return "INSUFFICIENT_CASH", {
            "available_cash_minor": available,
            "required_cash_minor": required,
            "working_remaining": working_remaining,
        }
    return None, {"available_cash_minor": available, "required_cash_minor": required, "working_remaining": working_remaining}


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

