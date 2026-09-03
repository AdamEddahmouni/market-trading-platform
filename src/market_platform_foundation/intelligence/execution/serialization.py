"""Serialization for BUILD 22 execution artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, contract_reference_from_dict, contract_reference_to_dict
from ..contracts.trade_proposal import TradeProposalV1, trade_proposal_v1_from_dict, trade_proposal_v1_to_dict
from .types import (
    EXECUTION_IMPLEMENTATION_VERSION,
    ExecutionMode,
    ExecutionPolicyV1,
    ExposureSnapshot,
    PaperOpenOrderSnapshot,
    PaperPortfolioSnapshotV1,
    PaperPositionSnapshot,
    RiskDecisionKind,
    RiskDecisionV1,
    RiskReasonCode,
    SizingPolicyKind,
)


def _exposure_to_dict(exposure: ExposureSnapshot | None) -> dict[str, Any] | None:
    if exposure is None:
        return None
    return {
        "gross_exposure_minor": exposure.gross_exposure_minor,
        "net_exposure_minor": exposure.net_exposure_minor,
    }


def _exposure_from_dict(payload: dict[str, Any] | None) -> ExposureSnapshot | None:
    if payload is None:
        return None
    return ExposureSnapshot(
        gross_exposure_minor=int(payload["gross_exposure_minor"]),
        net_exposure_minor=int(payload["net_exposure_minor"]),
    )


def execution_policy_v1_to_dict(policy: ExecutionPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "execution_policy_id": policy.execution_policy_id,
        "mode": policy.mode.value,
        "sizing_policy": policy.sizing_policy.value,
        "trade_fraction_nav": policy.trade_fraction_nav,
        "max_trade_notional_minor": policy.max_trade_notional_minor,
        "max_trade_fraction_nav": policy.max_trade_fraction_nav,
        "max_position_notional_minor": policy.max_position_notional_minor,
        "max_position_fraction_nav": policy.max_position_fraction_nav,
        "max_symbol_concentration_fraction": policy.max_symbol_concentration_fraction,
        "max_gross_exposure_fraction": policy.max_gross_exposure_fraction,
        "max_net_exposure_fraction": policy.max_net_exposure_fraction,
        "max_open_orders_per_symbol": policy.max_open_orders_per_symbol,
        "max_total_open_orders": policy.max_total_open_orders,
        "minimum_trade_notional_minor": policy.minimum_trade_notional_minor,
        "minimum_quantity": policy.minimum_quantity,
        "daily_loss_limit_fraction": policy.daily_loss_limit_fraction,
        "allow_short": policy.allow_short,
        "allow_position_reversal": policy.allow_position_reversal,
        "allow_size_reduction": policy.allow_size_reduction,
        "max_portfolio_snapshot_age_ns": policy.max_portfolio_snapshot_age_ns,
        "allowed_order_types": list(policy.allowed_order_types),
        "price_scale": policy.price_scale,
        "currency": policy.currency,
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def execution_policy_v1_from_dict(payload: dict[str, Any]) -> ExecutionPolicyV1:
    return ExecutionPolicyV1(
        execution_policy_id=str(payload["execution_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        mode=ExecutionMode(str(payload.get("mode", ExecutionMode.PAPER.value))),
        sizing_policy=SizingPolicyKind(
            str(payload.get("sizing_policy", SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS.value))
        ),
        trade_fraction_nav=float(payload.get("trade_fraction_nav", 0.01)),
        max_trade_notional_minor=payload.get("max_trade_notional_minor"),
        max_trade_fraction_nav=payload.get("max_trade_fraction_nav"),
        max_position_notional_minor=payload.get("max_position_notional_minor"),
        max_position_fraction_nav=payload.get("max_position_fraction_nav"),
        max_symbol_concentration_fraction=float(payload.get("max_symbol_concentration_fraction", 0.25)),
        max_gross_exposure_fraction=float(payload.get("max_gross_exposure_fraction", 1.0)),
        max_net_exposure_fraction=float(payload.get("max_net_exposure_fraction", 1.0)),
        max_open_orders_per_symbol=int(payload.get("max_open_orders_per_symbol", 3)),
        max_total_open_orders=int(payload.get("max_total_open_orders", 10)),
        minimum_trade_notional_minor=int(payload.get("minimum_trade_notional_minor", 100)),
        minimum_quantity=int(payload.get("minimum_quantity", 1)),
        daily_loss_limit_fraction=payload.get("daily_loss_limit_fraction"),
        allow_short=bool(payload.get("allow_short", False)),
        allow_position_reversal=bool(payload.get("allow_position_reversal", False)),
        allow_size_reduction=bool(payload.get("allow_size_reduction", True)),
        max_portfolio_snapshot_age_ns=payload.get("max_portfolio_snapshot_age_ns"),
        allowed_order_types=tuple(str(v) for v in payload.get("allowed_order_types", ("MARKET",))),
        price_scale=int(payload.get("price_scale", 100)),
        currency=str(payload.get("currency", "USD")),
        implementation_version=str(payload.get("implementation_version", EXECUTION_IMPLEMENTATION_VERSION)),
        metadata=dict(payload.get("metadata") or {}),
    )


def paper_portfolio_snapshot_v1_to_dict(snapshot: PaperPortfolioSnapshotV1) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "snapshot_id": snapshot.snapshot_id,
        "captured_at_ns": snapshot.captured_at_ns,
        "cash_minor": snapshot.cash_minor,
        "equity_minor": snapshot.equity_minor,
        "currency": snapshot.currency,
        "price_scale": snapshot.price_scale,
        "positions": [
            {
                "instrument_id": pos.instrument_id,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "market_value_minor": pos.market_value_minor,
            }
            for pos in snapshot.positions
        ],
        "open_orders": [
            {
                "order_id": order.order_id,
                "instrument_id": order.instrument_id,
                "side": order.side,
                "quantity": order.quantity,
                "opportunity_id": order.opportunity_id,
            }
            for order in snapshot.open_orders
        ],
        "reserved_cash_minor": snapshot.reserved_cash_minor,
        "exposure": _exposure_to_dict(snapshot.exposure),
        "realized_pnl_minor": snapshot.realized_pnl_minor,
        "unrealized_pnl_minor": snapshot.unrealized_pnl_minor,
        "start_of_day_equity_minor": snapshot.start_of_day_equity_minor,
        "peak_equity_minor": snapshot.peak_equity_minor,
        "scenario_id": snapshot.scenario_id,
        "mode": snapshot.mode,
        "metadata": dict(snapshot.metadata),
    }


def paper_portfolio_snapshot_v1_from_dict(payload: dict[str, Any]) -> PaperPortfolioSnapshotV1:
    positions = tuple(
        PaperPositionSnapshot(
            instrument_id=str(item["instrument_id"]),
            symbol=str(item.get("symbol", "UNKNOWN")),
            quantity=int(item["quantity"]),
            market_value_minor=int(item["market_value_minor"]),
        )
        for item in payload.get("positions", ())
    )
    open_orders = tuple(
        PaperOpenOrderSnapshot(
            order_id=str(item["order_id"]),
            instrument_id=str(item["instrument_id"]),
            side=str(item["side"]),
            quantity=int(item["quantity"]),
            opportunity_id=item.get("opportunity_id"),
        )
        for item in payload.get("open_orders", ())
    )
    return PaperPortfolioSnapshotV1(
        snapshot_id=str(payload["snapshot_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        captured_at_ns=int(payload["captured_at_ns"]),
        cash_minor=int(payload["cash_minor"]),
        equity_minor=int(payload["equity_minor"]),
        currency=str(payload.get("currency", "USD")),
        price_scale=int(payload.get("price_scale", 100)),
        positions=positions,
        open_orders=open_orders,
        reserved_cash_minor=int(payload.get("reserved_cash_minor", 0)),
        exposure=_exposure_from_dict(payload.get("exposure")),
        realized_pnl_minor=int(payload.get("realized_pnl_minor", 0)),
        unrealized_pnl_minor=int(payload.get("unrealized_pnl_minor", 0)),
        start_of_day_equity_minor=payload.get("start_of_day_equity_minor"),
        peak_equity_minor=payload.get("peak_equity_minor"),
        scenario_id=payload.get("scenario_id"),
        mode=str(payload.get("mode", "ACTUAL_LIVE")),
        metadata=dict(payload.get("metadata") or {}),
    )


def risk_decision_v1_to_dict(decision: RiskDecisionV1) -> dict[str, Any]:
    return {
        "schema_version": decision.schema_version,
        "risk_decision_id": decision.risk_decision_id,
        "trade_proposal_id": decision.trade_proposal_id,
        "opportunity_id": decision.opportunity_id,
        "execution_policy_id": decision.execution_policy_id,
        "portfolio_snapshot_id": decision.portfolio_snapshot_id,
        "decision_time_ns": decision.decision_time_ns,
        "requested_quantity": decision.requested_quantity,
        "requested_notional_minor": decision.requested_notional_minor,
        "approved_quantity": decision.approved_quantity,
        "approved_notional_minor": decision.approved_notional_minor,
        "decision": decision.decision.value,
        "reason_codes": [code.value for code in decision.reason_codes],
        "pre_trade_exposure": _exposure_to_dict(decision.pre_trade_exposure),
        "post_trade_exposure": _exposure_to_dict(decision.post_trade_exposure),
        "lineage_refs": [contract_reference_to_dict(ref) for ref in decision.lineage_refs],
        "metadata": dict(decision.metadata),
    }


def risk_decision_v1_from_dict(payload: dict[str, Any]) -> RiskDecisionV1:
    return RiskDecisionV1(
        risk_decision_id=str(payload["risk_decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        trade_proposal_id=str(payload["trade_proposal_id"]),
        opportunity_id=str(payload["opportunity_id"]),
        execution_policy_id=str(payload["execution_policy_id"]),
        portfolio_snapshot_id=str(payload["portfolio_snapshot_id"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        requested_quantity=int(payload["requested_quantity"]),
        requested_notional_minor=int(payload["requested_notional_minor"]),
        approved_quantity=int(payload["approved_quantity"]),
        approved_notional_minor=int(payload["approved_notional_minor"]),
        decision=RiskDecisionKind(str(payload["decision"])),
        reason_codes=tuple(RiskReasonCode(str(v)) for v in payload.get("reason_codes", ())),
        pre_trade_exposure=_exposure_from_dict(payload.get("pre_trade_exposure")),
        post_trade_exposure=_exposure_from_dict(payload.get("post_trade_exposure")),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "execution_policy_v1_from_dict",
    "execution_policy_v1_to_dict",
    "paper_portfolio_snapshot_v1_from_dict",
    "paper_portfolio_snapshot_v1_to_dict",
    "risk_decision_v1_from_dict",
    "risk_decision_v1_to_dict",
    "trade_proposal_v1_from_dict",
    "trade_proposal_v1_to_dict",
]
