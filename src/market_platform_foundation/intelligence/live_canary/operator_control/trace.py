"""Exact Forecast→Fill lineage trace (BUILD 31)."""

from __future__ import annotations

from typing import Any

from .context import OperatorControlContext, PendingOrderReview


def build_lineage_trace(
    ctx: OperatorControlContext,
    *,
    fill_receipt_id: str | None = None,
    confirmation_id: str | None = None,
) -> dict[str, Any]:
    """Exact ref-based lineage — no nearest-time guessing."""
    trace: dict[str, Any] = {
        "forecast_ref": None,
        "opportunity_ref": None,
        "trade_proposal_ref": None,
        "risk_decision_ref": None,
        "broker_order_intent_ref": None,
        "order_confirmation_ref": None,
        "gate_decision_ref": None,
        "submission_receipt_ref": None,
        "broker_ack_ref": None,
        "fill_receipt_ref": fill_receipt_id,
        "reconciliation_checkpoint_ref": None,
        "broken_links": [],
    }
    if confirmation_id and confirmation_id in ctx.confirmed_orders:
        confirmed = ctx.confirmed_orders[confirmation_id]
        trace["order_confirmation_ref"] = confirmed.confirmation_id
        trace["risk_decision_ref"] = confirmed.risk_decision_ref
        trace["broker_order_intent_ref"] = confirmed.broker_order_intent_ref
    for pending in ctx.pending_order_reviews.values():
        if confirmation_id and pending.confirmation_preview.confirmation_id == confirmation_id:
            trace["opportunity_ref"] = pending.opportunity_ref
            trace["trade_proposal_ref"] = pending.trade_proposal_ref
            trace["forecast_ref"] = pending.forecast_ref
            trace["risk_decision_ref"] = pending.risk_decision_ref
            trace["broker_order_intent_ref"] = pending.order_intent.broker_order_intent_id
            trace["order_confirmation_ref"] = pending.confirmation_preview.confirmation_id
            trace["requested_quantity"] = pending.requested_quantity
            trace["approved_quantity"] = pending.approved_quantity
            trace["final_quantity"] = pending.confirmation_preview.quantity
    if fill_receipt_id:
        fill = next((f for f in ctx.ledger.fill_receipts if f.fill_receipt_id == fill_receipt_id), None)
        if fill:
            trace["fill_receipt_ref"] = fill.fill_receipt_id
            submission = next(
                (
                    s
                    for s in ctx.ledger.submission_receipts
                    if s.broker_order_id == fill.broker_order_id
                ),
                None,
            )
            if submission:
                trace["submission_receipt_ref"] = submission.submission_receipt_id
                trace["order_confirmation_ref"] = submission.confirmation_ref
                trace["broker_ack_ref"] = submission.broker_order_id
            else:
                trace["broken_links"].append("submission_for_fill")
        else:
            trace["broken_links"].append("fill_not_found")
    checkpoint = ctx.latest_checkpoint()
    if checkpoint:
        trace["reconciliation_checkpoint_ref"] = checkpoint.checkpoint_id
    return trace


def build_order_review_model(
    pending: PendingOrderReview,
    *,
    ctx: OperatorControlContext,
    as_of_ns: int,
) -> dict[str, Any]:
    """Order confirmation review with requested vs approved sizing."""
    preview = pending.confirmation_preview
    return {
        "execution_mode_label": "LIVE_CANARY",
        "real_money_warning": "REAL LIVE ORDER",
        "broker": ctx.canary_policy.broker,
        "account_fingerprint": (
            ctx.authorization_preview.account_fingerprint if ctx.authorization_preview else None
        ),
        "account_environment": ctx.canary_policy.account_environment,
        "symbol": preview.instrument_id,
        "side": preview.side,
        "order_type": preview.order_type,
        "limit_price_minor": preview.limit_price_minor,
        "requested_quantity": pending.requested_quantity,
        "risk_approved_quantity": pending.approved_quantity,
        "broker_intent_quantity": preview.quantity,
        "risk_reduction_visible": pending.requested_quantity != pending.approved_quantity,
        "estimated_notional_minor": preview.estimated_max_notional_minor,
        "forecast_ref": pending.forecast_ref,
        "opportunity_ref": pending.opportunity_ref,
        "trade_proposal_ref": pending.trade_proposal_ref,
        "risk_decision_ref": pending.risk_decision_ref,
        "broker_order_intent_ref": pending.order_intent.broker_order_intent_id,
        "authorization_expires_at_ns": (
            ctx.authorization.effective_until_ns if ctx.authorization else None
        ),
        "confirmation_expires_at_ns": preview.expires_at_ns,
        "broker_health": ctx.broker_health,
        "reconciliation_health": ctx.reconciliation_health,
        "kill_switch_global": ctx.kill_switch.global_state.value,
        "kill_switch_program": ctx.kill_switch.program_state.value,
        "kill_switch_session": ctx.kill_switch.session_state.value,
        "as_of_ns": as_of_ns,
        "confirmation_id": preview.confirmation_id,
    }


def build_authorization_review_model(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
) -> dict[str, Any] | None:
    preview = ctx.authorization_preview
    if preview is None:
        return None
    return {
        "execution_mode_label": "LIVE_CANARY",
        "real_money_warning": "REAL MONEY",
        "broker": preview.broker,
        "account_fingerprint": preview.account_fingerprint,
        "account_environment": preview.account_environment,
        "asset_classes": list(ctx.canary_policy.allowed_asset_classes),
        "symbols": list(preview.symbol_universe),
        "allowed_sides": list(preview.allowed_sides),
        "allowed_order_types": list(preview.allowed_order_types),
        "single_order_cap_minor": preview.max_single_order_notional_minor,
        "session_cap_minor": preview.max_total_canary_notional_minor,
        "program_remaining_notional_minor": max(
            0,
            ctx.program_policy.max_program_live_notional_minor
            - ctx.accounting.filled_notional_minor,
        ),
        "authorization_duration_ns": preview.authorization_duration_ns,
        "starting_positions": list(preview.starting_positions_summary),
        "starting_open_orders": list(preview.starting_open_orders_summary),
        "critical_incidents": [
            i.incident_id for i in ctx.critical_open_incidents()
        ],
        "kill_switch_state": preview.kill_switch_state,
        "known_limitations": list(preview.known_limitations),
        "preview_id": preview.preview_id,
        "preview_hash": __import__(
            "market_platform_foundation.intelligence.live_canary.identity",
            fromlist=["derive_preview_hash"],
        ).derive_preview_hash(preview),
        "as_of_ns": as_of_ns,
    }
