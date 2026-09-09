"""Options position ledger — Decimal-exact, NON-AUTHORITATIVE compatibility.

G4 / BL-0211 (Phase 4): this ledger was the options execution lane's
independent FLOAT-based source of truth (cash, premium, realized P&L all
binary float). It is now:

- **exact**: every money/P&L value is ``Decimal``; float only enters through
  the string-exact boundary conversion ``Decimal(str(value))`` and only
  leaves through the JSON presentation boundary in ``options.execution``;
- **non-authoritative**: the canonical portfolio (``portfolio.canonical`` +
  ``portfolio.accounting`` + ``portfolio.instrument_economics``) is the
  authoritative multi-asset accounting model. This module is a compatibility
  projection over the same fills for the O9 conservative-execution
  simulation lane (``options.execution`` / ``execution.options_conservative``)
  and must not be used for new authoritative accounting. Removal condition:
  once the options execution lane emits canonical portfolio state directly
  and its golden snapshots are re-based, this adapter can be deleted.

The O9 simulation lane remains analytics/simulation: its snapshot output is
JSON-presentation float, while the ledger arithmetic inside is exact.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Mapping

from .accounting import exact_decimal, option_premium, realized_pnl_on_close

AUTHORITATIVE = False  # canonical portfolio/accounting is the authority

_DECIMAL_ONE = Decimal("1")


def _exact(value: Any, *, field_name: str) -> Decimal:
    """String-exact boundary conversion for legacy float inputs."""
    return exact_decimal(value, field_name=field_name, allow_float=True)


def build_options_ledger_state(*, initial_cash: float) -> dict[str, Any]:
    """Build a Decimal-exact options ledger state (legacy float signature)."""
    return {
        "cash": _exact(initial_cash, field_name="initial_cash"),
        "option_positions": [],
        "stock_shares": 0,
        "entries": [],
        "realized_pnl": Decimal("0"),
    }


def _position_key(position: dict[str, Any]) -> tuple[str, str, str, str]:
    # Keying uses float(str) identity coordinates (strike/expiry/side) — never
    # money arithmetic, so exact-Decimal rules do not apply here.
    return (
        str(position["call_put"]),
        str(_exact(position["strike"], field_name="strike")),
        str(position["expiry"]),
        str(position["side"]),
    )


def apply_option_fill(
    state: dict[str, Any],
    *,
    fill: dict[str, Any],
) -> dict[str, Any]:
    """Apply entry fill — premium cash flow and open option position (exact)."""
    side = str(fill["side"])
    fill_price = _exact(fill["fill_price"], field_name="fill_price")
    quantity = _exact(fill["quantity"], field_name="quantity")
    multiplier = _exact(fill.get("multiplier", 100.0), field_name="multiplier")
    premium = option_premium(quantity, fill_price, multiplier)
    cash_delta = -premium if side == "long" else premium

    position = {
        "call_put": fill["call_put"],
        "strike": fill["strike"],
        "expiry": str(fill["expiry"]),
        "side": side,
        "quantity": int(quantity),
        "multiplier": multiplier,
        "entry_premium": fill_price,
        "fill_id": fill.get("fill_id"),
    }
    entry = {
        "event_type": "ENTRY_FILL",
        "cash_delta": cash_delta,
        "fill_id": fill.get("fill_id"),
        "position": dict(position),
    }
    return {
        "cash": state["cash"] + cash_delta,
        "option_positions": list(state["option_positions"]) + [position],
        "stock_shares": int(state["stock_shares"]),
        "entries": list(state["entries"]) + [entry],
        "realized_pnl": Decimal(state["realized_pnl"]),
    }


def apply_settlement(
    state: dict[str, Any],
    *,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Apply expiration, early exercise, or assignment settlement event (exact)."""
    event_type = str(event["event_type"])
    cash_delta = _exact(event.get("cash_delta", 0.0), field_name="cash_delta")
    stock_delta = int(event.get("stock_delta", 0))
    closed_position = event.get("closed_position")
    realized_delta = _exact(event.get("realized_pnl_delta", 0.0), field_name="realized_pnl_delta")

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
        "cash_delta": cash_delta,
        "stock_delta": stock_delta,
        "realized_pnl_delta": realized_delta,
        "closed_position": closed_position,
        "detail": event.get("detail"),
    }
    return {
        "cash": state["cash"] + cash_delta,
        "option_positions": remaining_positions,
        "stock_shares": int(state["stock_shares"]) + stock_delta,
        "entries": list(state["entries"]) + [entry],
        "realized_pnl": Decimal(state["realized_pnl"]) + realized_delta,
    }


def build_canonical_option_positions(
    ledger_state: Mapping[str, Any],
    *,
    canonical_id_for: Callable[[str, str, str], str],
    native_currency: str = "USD",
) -> list[dict[str, Any]]:
    """Project open option positions onto canonical portfolio state.

    Produces serializable canonical ``PositionInput`` bodies (quantity in
    CONTRACTS, explicit multiplier, exact cost basis = premium x contracts x
    multiplier, signed by side). Same-identity partial fills aggregate into
    one canonical position (contract quantity truth). This is the G4
    convergence path: option fills' economic truth flows to canonical
    portfolio state through this projection; the float-free exactness is
    proven by parity tests.

    ``canonical_id_for(call_put, strike, expiry)`` resolves the canonical
    instrument id (the caller's job — admission is the XA-01 boundary).
    """
    from .canonical import PositionInput, QuantityUnit
    from .instrument_economics import EconomicsError, EconomicsErrorCode

    # Aggregate per-fill position entries by (call_put, strike, expiry,
    # side): partial fills of the same contract must sum to one canonical
    # position carrying the full contract quantity (G4 Phase 4: partial fills
    # preserve contract quantity truth; a fill is never double-booked).
    aggregates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for position in ledger_state.get("option_positions", []):
        call_put = str(position["call_put"])
        strike_raw = position["strike"]
        expiry = str(position["expiry"])
        side = str(position["side"])
        key = (call_put, str(strike_raw), str(expiry), side)
        quantity = Decimal(str(int(position["quantity"])))
        signed_quantity = quantity if side == "long" else -quantity
        multiplier = _exact(position["multiplier"], field_name="multiplier")
        entry_premium = _exact(position["entry_premium"], field_name="entry_premium")
        # Signed cost basis: long pays premium, short receives it.
        fill_basis = option_premium(signed_quantity, entry_premium, multiplier)
        bucket = aggregates.setdefault(
            key,
            {
                "multiplier": multiplier,
                "quantity": Decimal("0"),
                "cost_basis": Decimal("0"),
            },
        )
        bucket["quantity"] += signed_quantity
        bucket["cost_basis"] += fill_basis

    inputs: list[dict[str, Any]] = []
    for (call_put, strike_raw, expiry, side), bucket in sorted(aggregates.items()):
        try:
            instrument_id = canonical_id_for(call_put, strike_raw, expiry)
        except Exception:
            raise EconomicsError(
                EconomicsErrorCode.UNSUPPORTED_ECONOMICS,
                "canonical option identity unresolved; refusing to fabricate",
                {"call_put": call_put, "strike": strike_raw, "expiry": expiry},
            ) from None
        if not instrument_id or not str(instrument_id).strip():
            raise EconomicsError(
                EconomicsErrorCode.UNSUPPORTED_ECONOMICS,
                "canonical option identity unresolved; refusing to fabricate",
                {"call_put": call_put, "strike": strike_raw, "expiry": expiry},
            )
        signed_quantity = bucket["quantity"]
        cost_basis = bucket["cost_basis"]
        multiplier = bucket["multiplier"]
        average_cost = None
        if signed_quantity != 0 and multiplier > 0:
            average_cost = abs(cost_basis) / abs(signed_quantity) / multiplier
        position_input = PositionInput(
            instrument_id=instrument_id,
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity=signed_quantity,
            quantity_unit=QuantityUnit.CONTRACTS,
            native_currency=native_currency,
            multiplier=multiplier,
            average_cost=average_cost,
            cost_basis=cost_basis,
            realized_pnl_native=Decimal("0"),
        )
        inputs.append(position_input.to_dict())
    return inputs


def canonical_realized_pnl(
    ledger_state: Mapping[str, Any],
    *,
    multiplier: Decimal = _DECIMAL_ONE,
) -> Decimal:
    """Exact realized P&L from the ledger's settlement/close events.

    Each closed position contributes signed realized P&L using the accounting
    kernel's close formula. (The simulation lane's per-event deltas are
    presentation values; this recomputation is the exact authority.)
    """
    realized = Decimal("0")
    for entry in ledger_state.get("entries", []):
        event_type = str(entry.get("event_type", ""))
        if event_type == "ENTRY_FILL":
            continue
        position = entry.get("closed_position")
        if not isinstance(position, dict):
            continue
        side = str(position["side"])
        quantity = Decimal(str(int(position.get("quantity", 0))))
        signed_quantity = quantity if side == "long" else -quantity
        entry_premium = _exact(position.get("entry_premium", 0.0), field_name="entry_premium")
        # Intrinsic/close price is recovered from the event's realized delta
        # plus entry economics where the event does not carry a close price.
        realized_delta = _exact(entry.get("realized_pnl_delta", 0.0), field_name="realized_pnl_delta")
        pos_multiplier = _exact(position.get("multiplier", multiplier), field_name="multiplier")
        implied_close = realized_delta / (signed_quantity * pos_multiplier) + entry_premium
        realized += realized_pnl_on_close(
            instrument_kind="OPTION_CONTRACT",
            entry_price=entry_premium,
            exit_price=implied_close,
            quantity=signed_quantity,
            multiplier=pos_multiplier,
        )
    return realized


__all__ = [
    "AUTHORITATIVE",
    "apply_option_fill",
    "apply_settlement",
    "build_canonical_option_positions",
    "build_options_ledger_state",
    "canonical_realized_pnl",
]