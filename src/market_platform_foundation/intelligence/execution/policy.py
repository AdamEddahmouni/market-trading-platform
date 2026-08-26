"""Execution policy construction (BUILD 22)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .identity import derive_execution_policy_id
from .types import ExecutionMode, ExecutionPolicyV1, SizingPolicyKind


def build_execution_policy(
    *,
    trade_fraction_nav: float = 0.01,
    max_trade_notional_minor: int | None = None,
    max_trade_fraction_nav: float | None = None,
    max_position_notional_minor: int | None = None,
    max_position_fraction_nav: float | None = None,
    max_symbol_concentration_fraction: float = 0.25,
    max_gross_exposure_fraction: float = 1.0,
    max_net_exposure_fraction: float = 1.0,
    max_open_orders_per_symbol: int = 3,
    max_total_open_orders: int = 10,
    minimum_trade_notional_minor: int = 100,
    minimum_quantity: int = 1,
    daily_loss_limit_fraction: float | None = None,
    allow_short: bool = False,
    allow_position_reversal: bool = False,
    allow_size_reduction: bool = True,
    max_portfolio_snapshot_age_ns: int | None = None,
    allowed_order_types: tuple[str, ...] = ("MARKET",),
    price_scale: int = 100,
    currency: str = "USD",
) -> ExecutionPolicyV1:
    body = ExecutionPolicyV1(
        execution_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        mode=ExecutionMode.PAPER,
        sizing_policy=SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS,
        trade_fraction_nav=trade_fraction_nav,
        max_trade_notional_minor=max_trade_notional_minor,
        max_trade_fraction_nav=max_trade_fraction_nav,
        max_position_notional_minor=max_position_notional_minor,
        max_position_fraction_nav=max_position_fraction_nav,
        max_symbol_concentration_fraction=max_symbol_concentration_fraction,
        max_gross_exposure_fraction=max_gross_exposure_fraction,
        max_net_exposure_fraction=max_net_exposure_fraction,
        max_open_orders_per_symbol=max_open_orders_per_symbol,
        max_total_open_orders=max_total_open_orders,
        minimum_trade_notional_minor=minimum_trade_notional_minor,
        minimum_quantity=minimum_quantity,
        daily_loss_limit_fraction=daily_loss_limit_fraction,
        allow_short=allow_short,
        allow_position_reversal=allow_position_reversal,
        allow_size_reduction=allow_size_reduction,
        max_portfolio_snapshot_age_ns=max_portfolio_snapshot_age_ns,
        allowed_order_types=allowed_order_types,
        price_scale=price_scale,
        currency=currency,
    )
    policy_id = derive_execution_policy_id(body)
    return ExecutionPolicyV1(
        execution_policy_id=policy_id,
        schema_version=body.schema_version,
        mode=body.mode,
        sizing_policy=body.sizing_policy,
        trade_fraction_nav=body.trade_fraction_nav,
        max_trade_notional_minor=body.max_trade_notional_minor,
        max_trade_fraction_nav=body.max_trade_fraction_nav,
        max_position_notional_minor=body.max_position_notional_minor,
        max_position_fraction_nav=body.max_position_fraction_nav,
        max_symbol_concentration_fraction=body.max_symbol_concentration_fraction,
        max_gross_exposure_fraction=body.max_gross_exposure_fraction,
        max_net_exposure_fraction=body.max_net_exposure_fraction,
        max_open_orders_per_symbol=body.max_open_orders_per_symbol,
        max_total_open_orders=body.max_total_open_orders,
        minimum_trade_notional_minor=body.minimum_trade_notional_minor,
        minimum_quantity=body.minimum_quantity,
        daily_loss_limit_fraction=body.daily_loss_limit_fraction,
        allow_short=body.allow_short,
        allow_position_reversal=body.allow_position_reversal,
        allow_size_reduction=body.allow_size_reduction,
        max_portfolio_snapshot_age_ns=body.max_portfolio_snapshot_age_ns,
        allowed_order_types=body.allowed_order_types,
        price_scale=body.price_scale,
        currency=body.currency,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


__all__ = ["build_execution_policy"]
