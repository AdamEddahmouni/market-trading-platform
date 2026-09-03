"""Preregistered risk policy specification."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

POLICY_VERSION = "phase7.cash-multisymbol/2.0.0"


def build_risk_policy(
    *,
    max_position_shares: int = 500,
    max_order_shares: int = 100,
    max_open_orders: int = 3,
    max_order_notional_minor: int = 10_000_00,
    max_position_notional_minor: int = 100_000_00,
    broker_market_reserve_buffer_bps: int = 500,
    participation_cap_numerator: int = 1,
    participation_cap_denominator: int = 100,
    commission_minor_per_share: int = 0,
    fee_minor_per_order: int = 0,
    initial_cash_minor: int = 1_000_000_00,
    currency: str = "USD",
    price_scale: int = 100,
    cash_account: bool = True,
    long_only: bool = True,
) -> dict[str, Any]:
    body = {
        "cash_account": cash_account,
        "broker_market_reserve_buffer_bps": broker_market_reserve_buffer_bps,
        "commission_minor_per_share": commission_minor_per_share,
        "currency": currency,
        "fee_minor_per_order": fee_minor_per_order,
        "initial_cash_minor": initial_cash_minor,
        "long_only": long_only,
        "max_open_orders": max_open_orders,
        "max_order_notional_minor": max_order_notional_minor,
        "max_order_shares": max_order_shares,
        "max_position_notional_minor": max_position_notional_minor,
        "max_position_shares": max_position_shares,
        "participation_cap_denominator": participation_cap_denominator,
        "participation_cap_numerator": participation_cap_numerator,
        "policy_version": POLICY_VERSION,
        "price_scale": price_scale,
    }
    return {
        **body,
        "risk_policy_identity_hash": sha256_bytes(canonical_bytes(body)),
    }


DEFAULT_RISK_POLICY = build_risk_policy()
