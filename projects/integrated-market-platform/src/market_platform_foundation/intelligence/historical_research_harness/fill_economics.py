"""Fill → position → PnL → costs for prediction-coupled simulator research (V3).

Authority: HISTORICAL_DEVELOPMENT only. Uses weighted average cost basis via
``portfolio.ledger.apply_fill`` (not FIFO). Does not bind Paper session or
``PaperExecutionLedger``.

Gross / cost / net identity (Lane B pins after re-review):

``portfolio.ledger.apply_fill`` records **post-policy-fee** realized deltas
(``_realized_delta`` subtracts commission and fees). Research **gross** is
**pre-policy-fee market PnL**: ledger ``realized_pnl_minor`` plus
``total_commission_minor`` and ``total_fees_minor`` added back once; unrealized
uses bar mark vs cost basis (unchanged). **transaction_costs** = sum(slippage
from notional × bps) + policy commission + policy fees (charged once in net).
**net_pnl** = gross_pnl − transaction_costs. Slippage does NOT depend on PnL sign.

Cost formula (``COST_MODEL_VERSION``):
  fill_notional_native = abs(fill_quantity) * (fill_price_minor / price_scale)
  slippage_cost_native = fill_notional_native * (cost_slippage_bps / 10_000)
  transaction_costs = sum(slippage) + policy commission + policy fees
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...numeric import decimal_to_minor_units
from ...portfolio.ledger import apply_fill, build_ledger_state
from ...risk.policy import DEFAULT_RISK_POLICY

ACCOUNTING_VERSION = "simulator-research-fill-economics/3.0.1"
COST_MODEL_VERSION = "simulator-research/notional-linear-bps/1.0.0"
NET_PNL_TOLERANCE = 1e-6


class FillEconomicsInvariantError(RuntimeError):
    """Research fill economics failed a fail-closed invariant."""


def _price_scale(policy: Mapping[str, Any]) -> int:
    return int(policy.get("price_scale", 100))


def _minor_to_native(minor: int, scale: int) -> float:
    return float(minor) / float(scale)


def _avg_entry_price_minor(position_shares: int, position_cost_basis_minor: int) -> int:
    if position_shares == 0:
        return 0
    return abs(position_cost_basis_minor) // abs(position_shares)


def _mark_price_minor_from_events(
    events: Sequence[Mapping[str, Any]],
    *,
    instrument_id: str | None,
    price_scale: int,
) -> int | None:
    bars = [
        event
        for event in events
        if event.get("event_type") == "BAR_OHLCV_1M"
        and (instrument_id is None or str(event.get("instrument_id")) == instrument_id)
    ]
    if not bars:
        return None
    last = max(bars, key=lambda row: int(row["available_time"]))
    payload = last.get("bar_payload")
    if not isinstance(payload, dict):
        return None
    close = str(payload.get("close", ""))
    try:
        return decimal_to_minor_units(close, scale=price_scale)
    except ValueError:
        return None


def _fill_notional_native(fill: Mapping[str, Any], *, price_scale: int) -> float:
    qty = abs(int(fill["fill_quantity"]))
    price_minor = int(fill["fill_price_minor"])
    return qty * _minor_to_native(price_minor, price_scale)


def _slippage_cost_native(fill_notional_native: float, cost_slippage_bps: float) -> float:
    return fill_notional_native * (cost_slippage_bps / 10_000.0)


def _position_reduced(position_before: int, position_after: int) -> bool:
    if position_before == 0:
        return False
    if position_after == 0:
        return True
    if (position_before > 0 and position_after < 0) or (position_before < 0 and position_after > 0):
        return True
    return abs(position_after) < abs(position_before)


def aggregate_fill_economics(
    fills: Sequence[Mapping[str, Any]],
    *,
    events: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any] | None = None,
    cost_slippage_bps: float,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    """Apply fills through ledger accounting and compute research economics."""

    active_policy = dict(policy or DEFAULT_RISK_POLICY)
    scale = _price_scale(active_policy)
    ledger = build_ledger_state(initial_cash_minor=int(active_policy["initial_cash_minor"]))
    fill_records: list[dict[str, Any]] = []
    traded_notional_native = 0.0
    slippage_total = 0.0
    winning_closed = 0
    losing_closed = 0

    for fill in fills:
        if not isinstance(fill, Mapping):
            continue
        position_before = int(ledger["position_shares"])
        basis_before = int(ledger.get("position_cost_basis_minor", 0))
        avg_before = _avg_entry_price_minor(position_before, basis_before)

        notional = _fill_notional_native(fill, price_scale=scale)
        slippage = _slippage_cost_native(notional, cost_slippage_bps)
        traded_notional_native += notional
        slippage_total += slippage

        prior_entries = len(ledger["entries"])
        ledger = apply_fill(ledger, fill=dict(fill), policy=active_policy)
        entry = ledger["entries"][-1] if len(ledger["entries"]) > prior_entries else {}
        position_after = int(ledger["position_shares"])
        basis_after = int(ledger.get("position_cost_basis_minor", 0))
        avg_after = _avg_entry_price_minor(position_after, basis_after)
        realized_delta_minor = int(entry.get("realized_pnl_delta_minor", 0))

        commission_minor = 0
        fees_minor = 0
        if "commission_minor" in fill:
            commission_minor = int(fill["commission_minor"])
        else:
            commission_minor = int(fill["fill_quantity"]) * int(
                active_policy.get("commission_minor_per_share", 0)
            )
        if "fees_minor" in fill:
            fees_minor = int(fill["fees_minor"])
        else:
            fees_minor = int(active_policy.get("fee_minor_per_order", 0))
        policy_fees_native = _minor_to_native(commission_minor + fees_minor, scale)

        if _position_reduced(position_before, position_after):
            if realized_delta_minor > 0:
                winning_closed += 1
            elif realized_delta_minor < 0:
                losing_closed += 1

        side = "buy" if str(fill.get("direction")) == "long" else "sell"
        fill_records.append(
            {
                "instrument": str(fill.get("instrument_id") or instrument_id or "UNKNOWN"),
                "side": side,
                "quantity": int(fill["fill_quantity"]),
                "fill_price": _minor_to_native(int(fill["fill_price_minor"]), scale),
                "fill_price_minor": int(fill["fill_price_minor"]),
                "fill_time": int(fill.get("fill_time", 0)),
                "position_before": position_before,
                "position_after": position_after,
                "average_entry_price_before": _minor_to_native(avg_before, scale),
                "average_entry_price_after": _minor_to_native(avg_after, scale),
                "realized_pnl_delta": _minor_to_native(realized_delta_minor, scale),
                "realized_pnl_delta_minor": realized_delta_minor,
                "fees": policy_fees_native,
                "slippage_cost": slippage,
                "other_declared_costs": 0.0,
            }
        )

    mark_minor = _mark_price_minor_from_events(events, instrument_id=instrument_id, price_scale=scale)
    position_shares = int(ledger["position_shares"])
    basis_minor = int(ledger.get("position_cost_basis_minor", 0))
    gross_unrealized_minor = 0
    if position_shares != 0 and mark_minor is not None:
        if position_shares > 0:
            gross_unrealized_minor = position_shares * mark_minor - basis_minor
        else:
            gross_unrealized_minor = abs(basis_minor) - abs(position_shares) * mark_minor

    ledger_post_fee_realized_minor = int(ledger["realized_pnl_minor"])
    policy_fees_total_minor = int(ledger.get("total_commission_minor", 0)) + int(
        ledger.get("total_fees_minor", 0)
    )
    # Ledger realized is post-fee; gross is market PnL before policy commission/fees.
    gross_realized_minor = ledger_post_fee_realized_minor + policy_fees_total_minor
    gross_realized = _minor_to_native(gross_realized_minor, scale)
    gross_unrealized = _minor_to_native(gross_unrealized_minor, scale)
    gross_pnl = gross_realized + gross_unrealized

    policy_fees_total_native = _minor_to_native(policy_fees_total_minor, scale)
    transaction_costs = slippage_total + policy_fees_total_native
    net_pnl = gross_pnl - transaction_costs

    turnover = traded_notional_native
    exposure = abs(position_shares)
    position_count = 1 if position_shares != 0 else 0

    return {
        "accounting_version": ACCOUNTING_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "cost_slippage_bps": cost_slippage_bps,
        "fill_economics": fill_records,
        "fill_count": len(fill_records),
        "gross_realized_pnl": gross_realized,
        "gross_unrealized_pnl": gross_unrealized,
        "gross_pnl": gross_pnl,
        "transaction_costs": transaction_costs,
        "estimated_costs": transaction_costs,
        "net_pnl": net_pnl,
        "turnover": turnover,
        "exposure": exposure,
        "position_count": position_count,
        "traded_notional": traded_notional_native,
        "winning_closed_trades": winning_closed,
        "losing_closed_trades": losing_closed,
        "mark_price_minor": mark_minor,
        "position_shares": position_shares,
        "ledger_post_fee_realized_pnl_minor": ledger_post_fee_realized_minor,
        "policy_fees_total_minor": policy_fees_total_minor,
        "ledger_realized_pnl_minor": ledger_post_fee_realized_minor,
    }


def assert_fill_economics_invariants(
    summary: Mapping[str, Any],
    *,
    trade_intent_count: int = 0,
) -> None:
    """Fail-closed checks for research simulator economics."""

    fill_count = int(summary.get("fill_count") or 0)
    fills_field = summary.get("fills")
    if isinstance(fills_field, int):
        fill_count = max(fill_count, fills_field)

    turnover = float(summary.get("turnover") or 0)
    transaction_costs = float(summary.get("transaction_costs") or summary.get("estimated_costs") or 0)
    gross_pnl = float(summary.get("gross_pnl") or 0)
    net_pnl = float(summary.get("net_pnl") or 0)
    traded_notional = float(summary.get("traded_notional") or 0)
    cost_bps = float(summary.get("cost_slippage_bps") or 0)

    no_trade = trade_intent_count == 0 and fill_count == 0
    if no_trade:
        for field in ("turnover", "transaction_costs", "gross_pnl", "net_pnl", "traded_notional"):
            value = float(summary.get(field) or summary.get("estimated_costs") or 0)
            if value != 0:
                raise FillEconomicsInvariantError(f"NO_TRADE_NONZERO_{field}")
        return

    if fill_count > 0:
        economics = summary.get("fill_economics")
        if not isinstance(economics, list) or len(economics) != fill_count:
            raise FillEconomicsInvariantError("FILL_ECONOMICS_PROVENANCE_MISSING")
        for row in economics:
            if not isinstance(row, dict):
                raise FillEconomicsInvariantError("FILL_ECONOMICS_ROW_INVALID")
            for key in (
                "position_before",
                "position_after",
                "realized_pnl_delta",
                "slippage_cost",
            ):
                if key not in row:
                    raise FillEconomicsInvariantError(f"FILL_ECONOMICS_FIELD_MISSING:{key}")

    if traded_notional > 0 and cost_bps > 0:
        slippage = sum(
            float(row.get("slippage_cost", 0))
            for row in (summary.get("fill_economics") or [])
            if isinstance(row, dict)
        )
        if slippage <= 0 and transaction_costs <= 0:
            reason = summary.get("transaction_costs_zero_reason")
            if not reason:
                raise FillEconomicsInvariantError("TRANSACTION_COSTS_REQUIRED")

    if abs(net_pnl - (gross_pnl - transaction_costs)) > NET_PNL_TOLERANCE:
        raise FillEconomicsInvariantError("NET_PNL_IDENTITY_VIOLATION")


__all__ = [
    "ACCOUNTING_VERSION",
    "COST_MODEL_VERSION",
    "FillEconomicsInvariantError",
    "NET_PNL_TOLERANCE",
    "aggregate_fill_economics",
    "assert_fill_economics_invariants",
]
