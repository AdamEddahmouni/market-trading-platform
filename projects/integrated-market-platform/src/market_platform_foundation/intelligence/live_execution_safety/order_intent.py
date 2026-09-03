"""Broker order intent construction from governed trade artifacts (BUILD 28)."""

from __future__ import annotations

from ..contracts.opportunity import OpportunityV1
from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import RiskDecisionKind, RiskDecisionV1
from .identity import derive_broker_order_intent_id, derive_client_order_id
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerOrderIntentV1,
)


def approved_quantity_from_risk(risk: RiskDecisionV1) -> int:
    if risk.decision == RiskDecisionKind.REJECT:
        raise ValueError("RISK_NOT_APPROVED")
    if risk.decision == RiskDecisionKind.FAIL_CLOSED:
        raise ValueError("RISK_FAIL_CLOSED")
    return risk.approved_quantity


def build_broker_order_intent(
    *,
    trade_proposal: TradeProposalV1,
    risk_decision: RiskDecisionV1,
    execution_policy_ref: str,
    broker_target: str,
    account_environment: AccountEnvironment,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    stop_price_minor: int | None = None,
    time_in_force: str = "DAY",
    decision_time_ns: int,
) -> BrokerOrderIntentV1:
    """Build broker-neutral order intent using risk-approved quantity exactly."""
    if risk_decision.trade_proposal_id != trade_proposal.proposal_id:
        raise ValueError("RISK_PROPOSAL_MISMATCH")
    approved_qty = approved_quantity_from_risk(risk_decision)
    if approved_qty <= 0:
        raise ValueError("APPROVED_QUANTITY_INVALID")
    client_order_id = derive_client_order_id(
        risk_decision_id=risk_decision.risk_decision_id,
        trade_proposal_id=trade_proposal.proposal_id,
        broker=broker_target,
        account_environment=account_environment.value,
    )
    identity_payload = {
        "trade_proposal_id": trade_proposal.proposal_id,
        "risk_decision_id": risk_decision.risk_decision_id,
        "broker": broker_target,
        "account_environment": account_environment.value,
        "instrument_id": trade_proposal.instrument_id,
        "side": trade_proposal.side,
        "quantity": approved_qty,
        "order_type": order_type,
        "limit_price_minor": limit_price_minor,
        "client_order_id": client_order_id,
    }
    intent_id = derive_broker_order_intent_id(identity_payload)
    return BrokerOrderIntentV1(
        broker_order_intent_id=intent_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        trade_proposal_ref=trade_proposal.proposal_id,
        risk_decision_ref=risk_decision.risk_decision_id,
        execution_policy_ref=execution_policy_ref,
        instrument_id=trade_proposal.instrument_id,
        side=trade_proposal.side,
        quantity=approved_qty,
        order_type=order_type,
        limit_price_minor=limit_price_minor,
        stop_price_minor=stop_price_minor,
        time_in_force=time_in_force,
        client_order_id=client_order_id,
        expires_at_ns=trade_proposal.expires_at_ns,
        mode="DRY_RUN",
        broker_target=broker_target,
        account_environment=account_environment,
        lineage={
            "opportunity_id": trade_proposal.opportunity_id,
            "decision_time_ns": decision_time_ns,
        },
    )


def validate_intent_not_expired(intent: BrokerOrderIntentV1, *, decision_time_ns: int) -> None:
    if decision_time_ns >= intent.expires_at_ns:
        raise ValueError("ORDER_INTENT_EXPIRED")


def validate_opportunity_not_expired(opportunity: OpportunityV1, *, decision_time_ns: int) -> None:
    if opportunity.valid_until_ns is not None and decision_time_ns >= opportunity.valid_until_ns:
        raise ValueError("OPPORTUNITY_EXPIRED")
