"""Options position ledger — separate from equity share ledger (O9 fixture scope)."""

from __future__ import annotations

from typing import Any


def build_options_ledger_state(*, initial_cash: float) -> dict[str, Any]:
    return {
        "cash": round(initial_cash, 6),
        "option_positions": [],
        "stock_shares": 0,
        "entries": [],
        "realized_pnl": 0.0,
    }


def _position_key(position: dict[str, Any]) -> tuple[str, float, str, str]:
    return (
        str(position["call_put"]),
        float(position["strike"]),
        str(position["expiry"]),
        str(position["side"]),
    )


def apply_option_fill(
    state: dict[str, Any],
    *,
    fill: dict[str, Any],
) -> dict[str, Any]:
    """Apply entry fill — premium cash flow and open option position."""
    side = str(fill["side"])
    fill_price = float(fill["fill_price"])
    quantity = int(fill["quantity"])
    multiplier = float(fill.get("multiplier", 100.0))
    premium = fill_price * multiplier * quantity
    cash_delta = -premium if side == "long" else premium

    position = {
        "call_put": fill["call_put"],
        "strike": float(fill["strike"]),
        "expiry": str(fill["expiry"]),
        "side": side,
        "quantity": quantity,
        "multiplier": multiplier,
        "entry_premium": fill_price,
        "fill_id": fill.get("fill_id"),
    }
    entry = {
        "event_type": "ENTRY_FILL",
        "cash_delta": round(cash_delta, 6),
        "fill_id": fill.get("fill_id"),
        "position": dict(position),
    }
    return {
        "cash": round(float(state["cash"]) + cash_delta, 6),
        "option_positions": list(state["option_positions"]) + [position],
        "stock_shares": int(state["stock_shares"]),
        "entries": list(state["entries"]) + [entry],
        "realized_pnl": float(state["realized_pnl"]),
    }


def apply_settlement(
    state: dict[str, Any],
    *,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Apply expiration, early exercise, or assignment settlement event."""
    event_type = str(event["event_type"])
    cash_delta = float(event.get("cash_delta", 0.0))
    stock_delta = int(event.get("stock_delta", 0))
    closed_position = event.get("closed_position")
    realized_delta = float(event.get("realized_pnl_delta", 0.0))

    remaining_positions = list(state["option_positions"])
    if isinstance(closed_position, dict):
        closed_key = _position_key(closed_position)
        filtered: list[dict[str, Any]] = []
        removed = False
        for pos in remaining_positions:
            if not removed and _position_key(pos) == closed_key:
                removed = True
                continue
            filtered.append(pos)
        remaining_positions = filtered

    entry = {
        "event_type": event_type,
        "cash_delta": round(cash_delta, 6),
        "stock_delta": stock_delta,
        "realized_pnl_delta": round(realized_delta, 6),
        "closed_position": closed_position,
        "detail": event.get("detail"),
    }
    return {
        "cash": round(float(state["cash"]) + cash_delta, 6),
        "option_positions": remaining_positions,
        "stock_shares": int(state["stock_shares"]) + stock_delta,
        "entries": list(state["entries"]) + [entry],
        "realized_pnl": round(float(state["realized_pnl"]) + realized_delta, 6),
    }


__all__ = [
    "apply_option_fill",
    "apply_settlement",
    "build_options_ledger_state",
]
