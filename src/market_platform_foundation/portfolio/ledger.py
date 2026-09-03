"""Exact fill-driven ledger mutations."""

from __future__ import annotations

from typing import Any


def build_ledger_state(*, initial_cash_minor: int) -> dict[str, Any]:
    return {
        "cash_minor": initial_cash_minor,
        "entries": [],
        "positions_by_instrument": {},
        # Aggregate compatibility fields. New consumers must use the
        # instrument-keyed projection above; these keep legacy single-symbol
        # readers operational while they migrate.
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
    if qty <= 0:
        raise ValueError("PAPER_FILL_QUANTITY_INVALID")
    if price_minor < 0:
        raise ValueError("PAPER_FILL_PRICE_INVALID")
    if direction not in {"long", "short"}:
        raise ValueError("PAPER_FILL_DIRECTION_INVALID")
    signed_qty = qty if direction == "long" else -qty
    # Historical fills predate instrument-keyed accounting. Keep them
    # replayable under a deterministic compatibility bucket while all newly
    # generated Paper fills carry their real instrument_id.
    instrument_id = str(fill.get("instrument_id", "")).strip().upper() or "__LEGACY__"

    commission = (
        int(fill["commission_minor"])
        if "commission_minor" in fill
        else qty * int(policy["commission_minor_per_share"])
    )
    order_id = str(fill.get("order_id", ""))
    order_fee_already_charged = bool(
        order_id
        and any(str(entry.get("order_id", "")) == order_id for entry in state["entries"])
    )
    fees = (
        int(fill["fees_minor"])
        if "fees_minor" in fill
        else (0 if order_fee_already_charged else int(policy["fee_minor_per_order"]))
    )
    cash_delta = -(signed_qty * price_minor) - commission - fees

    positions = {
        str(key): dict(value)
        for key, value in dict(state.get("positions_by_instrument") or {}).items()
    }
    # Legacy attribution callers seed only the aggregate compatibility fields.
    # Materialize that seed into the compatibility bucket before applying the
    # next fill so weighted basis and reversal accounting remain intact.
    if not positions and (
        int(state.get("position_shares", 0)) != 0
        or int(state.get("position_cost_basis_minor", 0)) != 0
    ):
        positions["__LEGACY__"] = {
            "position_cost_basis_minor": int(state.get("position_cost_basis_minor", 0)),
            "position_shares": int(state.get("position_shares", 0)),
            "realized_pnl_minor": 0,
        }
    prior_position = positions.get(
        instrument_id,
        {
            "position_cost_basis_minor": 0,
            "position_shares": 0,
            "realized_pnl_minor": 0,
        },
    )
    position_before = int(prior_position["position_shares"])
    position_cost_basis_before = int(
        prior_position.get("position_cost_basis_minor", position_before * price_minor)
    )
    position_after = position_before + signed_qty
    if bool(policy.get("long_only", False)) and position_after < 0:
        raise ValueError("PAPER_SHORT_SELL_NOT_ALLOWED")
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
        "instrument_id": instrument_id,
        "order_id": order_id,
        "position_after": position_after,
        "position_before": position_before,
        "realized_pnl_delta_minor": realized_delta,
    }
    cash_after = int(state["cash_minor"]) + cash_delta
    if bool(policy.get("cash_account", False)) and cash_after < 0:
        raise ValueError("PAPER_CASH_NEGATIVE")

    positions[instrument_id] = {
        "position_cost_basis_minor": position_cost_basis_after,
        "position_shares": position_after,
        "realized_pnl_minor": int(prior_position.get("realized_pnl_minor", 0)) + realized_delta,
    }
    aggregate_shares = sum(int(row["position_shares"]) for row in positions.values())
    aggregate_basis = sum(int(row["position_cost_basis_minor"]) for row in positions.values())

    return {
        "cash_minor": cash_after,
        "entries": list(state["entries"]) + [entry],
        "positions_by_instrument": positions,
        "position_shares": aggregate_shares,
        "position_cost_basis_minor": aggregate_basis,
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
