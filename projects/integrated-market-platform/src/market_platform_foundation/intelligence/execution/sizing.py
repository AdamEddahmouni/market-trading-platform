"""Deterministic position sizing (BUILD 22)."""

from __future__ import annotations

from dataclasses import dataclass

from .exposure import (
    projected_positions_after_trade,
    snapshot_exposure,
    symbol_market_value_minor,
    symbol_position_quantity,
)
from .types import ExecutionPolicyV1, PaperPortfolioSnapshotV1, SizingPolicyKind


@dataclass(frozen=True, slots=True)
class SizingResult:
    quantity: int
    notional_minor: int
    capped_by: tuple[str, ...] = ()


def reference_price_for_side(*, bid_minor: int, ask_minor: int, side: str) -> int:
    if side == "BUY":
        return ask_minor
    return bid_minor


def size_fixed_fraction_nav_with_caps(
    *,
    policy: ExecutionPolicyV1,
    portfolio: PaperPortfolioSnapshotV1,
    instrument_id: str,
    symbol: str,
    side: str,
    reference_price_minor: int,
) -> SizingResult:
    if policy.sizing_policy != SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS:
        raise ValueError("SIZING_POLICY_UNSUPPORTED")

    equity = portfolio.equity_minor
    base_notional = int(equity * policy.trade_fraction_nav)
    capped_by: list[str] = []
    target_notional = base_notional

    if policy.max_trade_notional_minor is not None:
        if target_notional > policy.max_trade_notional_minor:
            target_notional = policy.max_trade_notional_minor
            capped_by.append("MAX_TRADE_NOTIONAL")
    if policy.max_trade_fraction_nav is not None:
        cap = int(equity * policy.max_trade_fraction_nav)
        if target_notional > cap:
            target_notional = cap
            capped_by.append("MAX_TRADE_FRACTION_NAV")

    current_symbol_value = symbol_market_value_minor(portfolio.positions, instrument_id=instrument_id)
    if policy.max_position_notional_minor is not None:
        headroom = max(0, policy.max_position_notional_minor - current_symbol_value)
        if target_notional > headroom:
            target_notional = headroom
            capped_by.append("MAX_POSITION_NOTIONAL")
    if policy.max_position_fraction_nav is not None:
        cap = int(equity * policy.max_position_fraction_nav)
        headroom = max(0, cap - current_symbol_value)
        if target_notional > headroom:
            target_notional = headroom
            capped_by.append("MAX_POSITION_FRACTION_NAV")

    # concentration cap on projected symbol fraction
    if target_notional > 0:
        projected_symbol_value = current_symbol_value + target_notional
        max_symbol_value = int(equity * policy.max_symbol_concentration_fraction)
        if projected_symbol_value > max_symbol_value:
            target_notional = max(0, max_symbol_value - current_symbol_value)
            capped_by.append("MAX_SYMBOL_CONCENTRATION")

    pre = snapshot_exposure(portfolio)
    projected = projected_positions_after_trade(
        portfolio.positions,
        instrument_id=instrument_id,
        symbol=symbol,
        side=side,
        quantity=max(1, target_notional // reference_price_minor) if reference_price_minor else 0,
        reference_price_minor=reference_price_minor,
    )
    from .exposure import compute_exposure

    post = compute_exposure(projected)
    max_gross = int(equity * policy.max_gross_exposure_fraction)
    if post.gross_exposure_minor > max_gross and reference_price_minor > 0:
        allowed_gross_add = max(0, max_gross - pre.gross_exposure_minor)
        if target_notional > allowed_gross_add:
            target_notional = allowed_gross_add
            capped_by.append("MAX_GROSS_EXPOSURE")

    projected = projected_positions_after_trade(
        portfolio.positions,
        instrument_id=instrument_id,
        symbol=symbol,
        side=side,
        quantity=max(1, target_notional // reference_price_minor) if reference_price_minor else 0,
        reference_price_minor=reference_price_minor,
    )
    post = compute_exposure(projected)
    max_net = int(equity * policy.max_net_exposure_fraction)
    if abs(post.net_exposure_minor) > max_net and reference_price_minor > 0:
        current_net = pre.net_exposure_minor
        if side == "BUY":
            allowed = max(0, max_net - current_net)
        else:
            allowed = max(0, max_net + current_net)
        if target_notional > allowed:
            target_notional = allowed
            capped_by.append("MAX_NET_EXPOSURE")

    if side == "BUY":
        available_cash = portfolio.cash_minor - portfolio.reserved_cash_minor
        if target_notional > available_cash:
            target_notional = max(0, available_cash)
            capped_by.append("INSUFFICIENT_PAPER_CASH")

    quantity = target_notional // reference_price_minor if reference_price_minor > 0 else 0
    notional = quantity * reference_price_minor
    return SizingResult(quantity=quantity, notional_minor=notional, capped_by=tuple(capped_by))


def validate_position_interaction(
    *,
    policy: ExecutionPolicyV1,
    portfolio: PaperPortfolioSnapshotV1,
    instrument_id: str,
    side: str,
    quantity: int,
) -> tuple[int, tuple[str, ...]]:
    """Return permitted quantity after reversal/short rules."""
    reasons: list[str] = []
    current_qty = symbol_position_quantity(portfolio.positions, instrument_id=instrument_id)
    signed_delta = quantity if side == "BUY" else -quantity
    projected = current_qty + signed_delta

    if side == "SELL" and not policy.allow_short and current_qty <= 0:
        reasons.append("SHORT_NOT_ALLOWED")
        return 0, tuple(reasons)
    if side == "SELL" and not policy.allow_short and projected < 0:
        flatten_qty = current_qty
        if flatten_qty <= 0:
            reasons.append("SHORT_NOT_ALLOWED")
            return 0, tuple(reasons)
        if projected < 0 and not policy.allow_position_reversal:
            reasons.append("POSITION_REVERSAL_NOT_ALLOWED")
            return flatten_qty, tuple(reasons)

    if not policy.allow_position_reversal:
        if current_qty > 0 and side == "SELL" and projected < 0:
            reasons.append("POSITION_REVERSAL_NOT_ALLOWED")
            return current_qty, tuple(reasons)
        if current_qty < 0 and side == "BUY" and projected > 0:
            reasons.append("POSITION_REVERSAL_NOT_ALLOWED")
            return abs(current_qty), tuple(reasons)

    return quantity, tuple(reasons)


__all__ = [
    "SizingResult",
    "reference_price_for_side",
    "size_fixed_fraction_nav_with_caps",
    "validate_position_interaction",
]
