"""Exact fill-driven ledger mutations."""

from __future__ import annotations

from typing import Any


def build_ledger_state(*, initial_cash_minor: int) -> dict[str, Any]:
    return {
        "cash_minor": initial_cash_minor,
        "entries": [],
        "position_shares": 0,
        # Signed notional cost basis for the net position. Long positions are
        # positive; short positions are negative. Keeping total basis (rather
        # than a fill-price average) preserves weighted-cost information across
        # partial closes and reversals.
        "position_cost_basis_minor": 0,
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

    commission = (
        int(fill["commission_minor"])
        if "commission_minor" in fill
        else qty * int(policy["commission_minor_per_share"])
    )
    fees = (
        int(fill["fees_minor"])
        if "fees_minor" in fill
        else int(policy["fee_minor_per_order"])
    )
    cash_delta = -(signed_qty * price_minor) - commission - fees

    position_before = int(state["position_shares"])
    position_cost_basis_before = int(
        state.get("position_cost_basis_minor", position_before * price_minor)
    )
    position_after = position_before + signed_qty
    realized_delta = _realized_delta(
        position_before=position_before,
        signed_qty=signed_qty,
        price_minor=price_minor,
        position_cost_basis_minor=position_cost_basis_before,
        commission=commission,
        fees=fees,
    )
    position_cost_basis_after = _cost_basis_after_fill(
        position_before=position_before,
        signed_qty=signed_qty,
        price_minor=price_minor,
        position_cost_basis_minor=position_cost_basis_before,
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
        "position_cost_basis_minor": position_cost_basis_after,
        "realized_pnl_minor": int(state["realized_pnl_minor"]) + realized_delta,
        "total_commission_minor": int(state["total_commission_minor"]) + commission,
        "total_fees_minor": int(state["total_fees_minor"]) + fees,
    }


def _realized_delta(
    *,
    position_before: int,
    signed_qty: int,
    price_minor: int,
    position_cost_basis_minor: int,
    commission: int,
    fees: int,
) -> int:
    if position_before == 0:
        return -(commission + fees)
    if position_before > 0 and signed_qty < 0:
        closed = min(abs(signed_qty), position_before)
        closed_cost_basis = _closed_cost_basis(
            position_before=position_before,
            position_cost_basis_minor=position_cost_basis_minor,
            closed=closed,
        )
        return closed * price_minor - closed_cost_basis - commission - fees
    if position_before < 0 and signed_qty > 0:
        closed = min(signed_qty, abs(position_before))
        closed_cost_basis = _closed_cost_basis(
            position_before=position_before,
            position_cost_basis_minor=position_cost_basis_minor,
            closed=closed,
        )
        return closed_cost_basis - closed * price_minor - commission - fees
    return -(commission + fees)


def _cost_basis_after_fill(
    *,
    position_before: int,
    signed_qty: int,
    price_minor: int,
    position_cost_basis_minor: int,
) -> int:
    if position_before == 0:
        return signed_qty * price_minor

    same_side = (position_before > 0 and signed_qty > 0) or (
        position_before < 0 and signed_qty < 0
    )
    if same_side:
        return position_cost_basis_minor + signed_qty * price_minor

    closed = min(abs(signed_qty), abs(position_before))
    retained_basis = abs(position_cost_basis_minor) - _closed_cost_basis(
        position_before=position_before,
        position_cost_basis_minor=position_cost_basis_minor,
        closed=closed,
    )
    remaining_shares = abs(position_before + signed_qty)
    if remaining_shares == 0:
        return 0
    if abs(signed_qty) <= abs(position_before):
        return (1 if position_before > 0 else -1) * retained_basis

    # A reversal first closes the existing net position, then opens the
    # remainder at the reversal fill price.
    return (1 if signed_qty > 0 else -1) * remaining_shares * price_minor


def _closed_cost_basis(
    *,
    position_before: int,
    position_cost_basis_minor: int,
    closed: int,
) -> int:
    if position_before == 0 or closed <= 0:
        return 0
    return abs(position_cost_basis_minor) * closed // abs(position_before)


def _avg_cost(position_before: int, position_cost_basis_minor: int) -> int:
    """Return the current net position's weighted average entry price."""

    if position_before == 0:
        return 0
    return abs(position_cost_basis_minor) // abs(position_before)


def build_portfolio_state(*, initial_cash_minor: int) -> dict[str, Any]:
    """Portfolio-scoped ledger state: one cash bucket, one position per instrument."""

    return {
        "cash_minor": initial_cash_minor,
        "entries": [],
        "positions": {},
        "realized_pnl_minor": 0,
        "total_commission_minor": 0,
        "total_fees_minor": 0,
    }


def position_effect(*, position_before: int, position_after: int) -> str:
    """Classify one fill's effect on its own instrument's net position."""

    if position_before == 0:
        return "OPEN"
    if position_after == 0:
        return "CLOSE"
    if (position_before > 0) != (position_after > 0):
        return "REVERSE"
    return "ADD" if abs(position_after) > abs(position_before) else "REDUCE"


def apply_portfolio_fill(
    state: dict[str, Any],
    *,
    fill: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Apply one fill to its own instrument's position and the shared cash.

    The per-instrument arithmetic is ``apply_fill`` itself, run against that
    instrument's slice of the state, so weighted cost basis, pro-rata closes
    and cost handling cannot drift from the single-position ledger.
    """

    instrument_id = str(fill["instrument_id"])
    positions = dict(state["positions"])
    before = positions.get(instrument_id) or {
        "first_entry_time": None,
        "latest_fill_time": None,
        "position_cost_basis_minor": 0,
        "position_shares": 0,
        "realized_pnl_minor": 0,
    }
    slice_before = {
        "cash_minor": int(state["cash_minor"]),
        "entries": [],
        "position_cost_basis_minor": int(before["position_cost_basis_minor"]),
        "position_shares": int(before["position_shares"]),
        "realized_pnl_minor": 0,
        "total_commission_minor": 0,
        "total_fees_minor": 0,
    }
    slice_after = apply_fill(slice_before, fill=fill, policy=policy)
    entry = dict(slice_after["entries"][0])
    fill_time = fill.get("fill_time")
    shares_before = int(before["position_shares"])
    shares_after = int(slice_after["position_shares"])
    effect = position_effect(position_before=shares_before, position_after=shares_after)
    # A flat instrument's next fill starts a new position, so its entry clock
    # restarts; a reversal opens the remainder at the reversing fill.
    first_entry_time = fill_time if effect in {"OPEN", "REVERSE"} else before["first_entry_time"]
    positions[instrument_id] = {
        "first_entry_time": first_entry_time,
        "latest_fill_time": fill_time,
        "position_cost_basis_minor": int(slice_after["position_cost_basis_minor"]),
        "position_shares": shares_after,
        "realized_pnl_minor": int(before["realized_pnl_minor"]) + int(slice_after["realized_pnl_minor"]),
    }
    entry.update(
        {
            "commission_minor": int(slice_after["total_commission_minor"]),
            "fees_minor": int(slice_after["total_fees_minor"]),
            "fill_time": fill_time,
            "instrument_id": instrument_id,
            "position_cost_basis_after_minor": int(slice_after["position_cost_basis_minor"]),
            "position_effect": effect,
        }
    )
    return {
        "cash_minor": int(slice_after["cash_minor"]),
        "entries": list(state["entries"]) + [entry],
        "positions": positions,
        "realized_pnl_minor": int(state["realized_pnl_minor"]) + int(slice_after["realized_pnl_minor"]),
        "total_commission_minor": int(state["total_commission_minor"]) + int(slice_after["total_commission_minor"]),
        "total_fees_minor": int(state["total_fees_minor"]) + int(slice_after["total_fees_minor"]),
    }
