"""Deterministic execution identities (BUILD 22)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.common import ContractReference, contract_reference_to_dict
from ..contracts.trade_proposal import TradeProposalV1
from .types import ExecutionPolicyV1, PaperPortfolioSnapshotV1, RiskDecisionKind


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def execution_policy_identity_payload(policy: ExecutionPolicyV1) -> dict[str, Any]:
    return {
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
    }


def derive_execution_policy_id(policy: ExecutionPolicyV1) -> str:
    return _sha256_prefix("EXECPOL", execution_policy_identity_payload(policy))


def portfolio_snapshot_identity_payload(snapshot: PaperPortfolioSnapshotV1) -> dict[str, Any]:
    positions = sorted(
        [
            {
                "instrument_id": pos.instrument_id,
                "quantity": pos.quantity,
                "market_value_minor": pos.market_value_minor,
            }
            for pos in snapshot.positions
        ],
        key=lambda row: row["instrument_id"],
    )
    open_orders = sorted(
        [
            {
                "order_id": order.order_id,
                "instrument_id": order.instrument_id,
                "side": order.side,
                "quantity": order.quantity,
                "opportunity_id": order.opportunity_id,
            }
            for order in snapshot.open_orders
        ],
        key=lambda row: row["order_id"],
    )
    return {
        "captured_at_ns": snapshot.captured_at_ns,
        "cash_minor": snapshot.cash_minor,
        "equity_minor": snapshot.equity_minor,
        "currency": snapshot.currency,
        "price_scale": snapshot.price_scale,
        "positions": positions,
        "open_orders": open_orders,
        "reserved_cash_minor": snapshot.reserved_cash_minor,
        "realized_pnl_minor": snapshot.realized_pnl_minor,
        "unrealized_pnl_minor": snapshot.unrealized_pnl_minor,
        "start_of_day_equity_minor": snapshot.start_of_day_equity_minor,
        "mode": snapshot.mode,
        "scenario_id": snapshot.scenario_id,
    }


def derive_portfolio_snapshot_id(snapshot: PaperPortfolioSnapshotV1) -> str:
    return _sha256_prefix("PAPSNAP", portfolio_snapshot_identity_payload(snapshot))


def derive_trade_proposal_id(
    *,
    opportunity_id: str,
    execution_policy_id: str,
    instrument_id: str,
    side: str,
    requested_quantity: int,
    reference_price_minor: int,
    proposal_time_ns: int,
) -> str:
    payload = {
        "opportunity_id": opportunity_id,
        "execution_policy_id": execution_policy_id,
        "instrument_id": instrument_id,
        "side": side,
        "requested_quantity": requested_quantity,
        "reference_price_minor": reference_price_minor,
        "proposal_time_ns": proposal_time_ns,
    }
    return _sha256_prefix("TPROP", payload)


def derive_risk_decision_id(
    *,
    trade_proposal: TradeProposalV1,
    execution_policy_id: str,
    portfolio_snapshot_id: str,
    decision_time_ns: int,
) -> str:
    payload = {
        "trade_proposal_id": trade_proposal.proposal_id,
        "opportunity_id": trade_proposal.opportunity_id,
        "execution_policy_id": execution_policy_id,
        "portfolio_snapshot_id": portfolio_snapshot_id,
        "decision_time_ns": decision_time_ns,
        "requested_quantity": trade_proposal.requested_quantity,
        "reference_price_minor": trade_proposal.reference_price_minor,
    }
    return _sha256_prefix("RISK", payload)


def derive_paper_order_idempotency_key(risk_decision_id: str) -> str:
    return _sha256_prefix("PAPERIDEM", {"risk_decision_id": risk_decision_id})


__all__ = [
    "derive_execution_policy_id",
    "derive_paper_order_idempotency_key",
    "derive_portfolio_snapshot_id",
    "derive_risk_decision_id",
    "derive_trade_proposal_id",
    "execution_policy_identity_payload",
    "portfolio_snapshot_identity_payload",
]
