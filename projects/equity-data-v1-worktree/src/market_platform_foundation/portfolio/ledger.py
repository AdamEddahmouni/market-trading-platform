"""Exact fill-driven ledger mutations."""

from __future__ import annotations

from typing import Any


def build_ledger_state(*, initial_cash_minor: int) -> dict[str, Any]:
    return {
        "cash_minor": initial_cash_minor,
        "entries": [],
        "position_shares": 0,
        "realized_pnl_minor": 0,
        "total_commission_minor": 0,
        "total_fees_minor": 0,
    }


def apply_fill(
    state: dict[str, Any],
    *,
    fill: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    qty = int(fill["fill_quantity"])
    price_minor = int(fill["fill_price_minor"])
    direction = str(fill["direction"])
    signed_qty = qty if direction == "long" else -qty

    commission = qty * int(policy["commission_minor_per_share"])
    fees = int(policy["fee_minor_per_order"])
    cash_delta = -(signed_qty * price_minor) - commission - fees

    position_before = int(state["position_shares"])
    position_after = position_before + signed_qty
    realized_delta = _realized_delta(
        position_before=position_before,
        signed_qty=signed_qty,
        price_minor=price_minor,
        commission=commission,
        fees=fees,
    )

    entry = {
        "cash_delta_minor": cash_delta,
        "fill_id": fill["fill_id"],
        "position_after": position_after,
        "position_before": position_before,
        "realized_pnl_delta_minor": realized_delta,
    }
    return {
        "cash_minor": int(state["cash_minor"]) + cash_delta,
        "entries": list(state["entries"]) + [entry],
        "position_shares": position_after,
        "realized_pnl_minor": int(state["realized_pnl_minor"]) + realized_delta,
        "total_commission_minor": int(state["total_commission_minor"]) + commission,
        "total_fees_minor": int(state["total_fees_minor"]) + fees,
    }


def _realized_delta(
    *,
    position_before: int,
    signed_qty: int,
    price_minor: int,
    commission: int,
    fees: int,
) -> int:
    if position_before == 0:
        return -(commission + fees)
    if position_before > 0 and signed_qty < 0:
        closed = min(abs(signed_qty), position_before)
        return closed * price_minor - closed * _avg_cost(position_before, price_minor) - commission - fees
    if position_before < 0 and signed_qty > 0:
        closed = min(signed_qty, abs(position_before))
        return closed * _avg_cost(position_before, price_minor) - closed * price_minor - commission - fees
    return -(commission + fees)


def _avg_cost(position_before: int, price_minor: int) -> int:
    return price_minor
