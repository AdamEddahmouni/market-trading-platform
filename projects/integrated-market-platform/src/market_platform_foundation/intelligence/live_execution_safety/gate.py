"""Live execution gate — deterministic multi-gate fail-closed evaluator (BUILD 28)."""

from __future__ import annotations

from ..contracts.opportunity import OpportunityV1
from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import RiskDecisionKind, RiskDecisionV1
from ..governance.types import RuntimeGovernanceState
from .identity import derive_gate_decision_id, derive_payload_hash
from .order_intent import validate_intent_not_expired, validate_opportunity_not_expired
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerCapabilityCertificationV1,
    BrokerCertificationDisposition,
    BrokerExecutionHealthV1,
    BrokerOrderIntentV1,
    BrokerReconciliationSnapshotV1,
    KillSwitchState,
    LiveAuthorizationState,
    LiveExecutionAuthorizationV1,
    LiveExecutionGateDecisionV1,
    LiveExecutionKillSwitchV1,
    LiveGateDecisionKind,
    LiveGateReasonCode,
    ReconciliationHealthState,
)

# BUILD 28 production: live submit is always forbidden even if all gates pass.
BUILD28_PRODUCTION_FORBID_LIVE_SUBMIT = True


def _blocked(
    *,
    decision_time_ns: int,
    broker: str,
    account_environment: AccountEnvironment,
    reason_codes: tuple[LiveGateReasonCode, ...],
    runtime_activation_ref: str | None = None,
    authorization_ref: str | None = None,
    broker_certification_ref: str | None = None,
    opportunity_ref: str | None = None,
    trade_proposal_ref: str | None = None,
    risk_decision_ref: str | None = None,
    broker_health_ref: str | None = None,
    kill_switch_ref: str | None = None,
    requested_order_intent_hash: str | None = None,
    decision: LiveGateDecisionKind = LiveGateDecisionKind.BLOCK,
) -> LiveExecutionGateDecisionV1:
    payload = {
        "decision_time_ns": decision_time_ns,
        "broker": broker,
        "account_environment": account_environment.value,
        "decision": decision.value,
        "reason_codes": [code.value for code in reason_codes],
    }
    return LiveExecutionGateDecisionV1(
        gate_decision_id=derive_gate_decision_id(payload),
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        decision_time_ns=decision_time_ns,
        runtime_activation_ref=runtime_activation_ref,
        authorization_ref=authorization_ref,
        broker_certification_ref=broker_certification_ref,
        opportunity_ref=opportunity_ref,
        trade_proposal_ref=trade_proposal_ref,
        risk_decision_ref=risk_decision_ref,
        broker_health_ref=broker_health_ref,
        kill_switch_ref=kill_switch_ref,
        broker=broker,
        account_environment=account_environment,
        requested_order_intent_hash=requested_order_intent_hash,
        decision=decision,
        reason_codes=reason_codes,
    )


def evaluate_live_execution_gate(
    *,
    decision_time_ns: int,
    broker: str,
    account_environment: AccountEnvironment,
    runtime_activation_ref: str | None,
    runtime_allows_live: bool,
    authorization: LiveExecutionAuthorizationV1 | None,
    broker_certification: BrokerCapabilityCertificationV1 | None,
    opportunity: OpportunityV1 | None,
    trade_proposal: TradeProposalV1 | None,
    risk_decision: RiskDecisionV1 | None,
    order_intent: BrokerOrderIntentV1 | None,
    broker_health: BrokerExecutionHealthV1 | None,
    reconciliation: BrokerReconciliationSnapshotV1 | None,
    kill_switch: LiveExecutionKillSwitchV1,
    governance: RuntimeGovernanceState | None = None,
    used_client_order_ids: frozenset[str] | None = None,
    allow_dry_run_in_test: bool = False,
    production_config: bool = True,
) -> LiveExecutionGateDecisionV1:
    """Evaluate all independent gates; missing any gate blocks submission."""
    common = {
        "decision_time_ns": decision_time_ns,
        "broker": broker,
        "account_environment": account_environment,
        "kill_switch_ref": kill_switch.kill_switch_id,
    }

    if governance is not None and governance.scope_disabled:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RUNTIME_GOVERNANCE_DISABLED,),
            runtime_activation_ref=runtime_activation_ref,
        )

    if kill_switch.state == KillSwitchState.ACTIVE_BLOCK:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.KILL_SWITCH_ACTIVE,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id if authorization else None,
        )

    if account_environment == AccountEnvironment.UNKNOWN:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_ENVIRONMENT_UNKNOWN,),
            decision=LiveGateDecisionKind.FAIL_CLOSED,
        )

    if account_environment == AccountEnvironment.LIVE and production_config:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_ENVIRONMENT_LIVE_BLOCKED_BY_BUILD28,),
            decision=LiveGateDecisionKind.FAIL_CLOSED,
        )

    if not runtime_allows_live:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RUNTIME_NOT_LIVE_AUTHORIZED,),
            runtime_activation_ref=runtime_activation_ref,
        )

    if authorization is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.LIVE_AUTHORIZATION_MISSING,),
            runtime_activation_ref=runtime_activation_ref,
        )

    if authorization.authorization_state in {
        LiveAuthorizationState.DISABLED,
        LiveAuthorizationState.NOT_AUTHORIZED,
        LiveAuthorizationState.DESIGN_ONLY,
    }:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.LIVE_AUTHORIZATION_DISABLED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
        )

    if decision_time_ns < authorization.effective_from_ns or decision_time_ns >= authorization.effective_until_ns:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.AUTHORIZATION_EXPIRED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
        )

    if authorization.broker != broker:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.AUTHORIZATION_SCOPE_MISMATCH,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
        )

    if broker_certification is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_NOT_CERTIFIED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
        )

    if broker_certification.disposition not in {
        BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED,
        BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS,
    }:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_NOT_CERTIFIED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            broker_certification_ref=broker_certification.certification_id,
        )

    if opportunity is not None:
        try:
            validate_opportunity_not_expired(opportunity, decision_time_ns=decision_time_ns)
        except ValueError:
            return _blocked(
                **common,
                reason_codes=(LiveGateReasonCode.OPPORTUNITY_EXPIRED,),
                runtime_activation_ref=runtime_activation_ref,
                authorization_ref=authorization.authorization_id,
                opportunity_ref=opportunity.opportunity_id,
            )

    if trade_proposal is not None and decision_time_ns >= trade_proposal.expires_at_ns:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.PROPOSAL_EXPIRED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            trade_proposal_ref=trade_proposal.proposal_id,
        )

    if risk_decision is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            trade_proposal_ref=trade_proposal.proposal_id if trade_proposal else None,
        )

    if risk_decision.decision not in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE}:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    if order_intent is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    try:
        validate_intent_not_expired(order_intent, decision_time_ns=decision_time_ns)
    except ValueError:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.PROPOSAL_EXPIRED,),
            trade_proposal_ref=order_intent.trade_proposal_ref,
            risk_decision_ref=risk_decision.risk_decision_id,
            requested_order_intent_hash=derive_payload_hash({"intent_id": order_intent.broker_order_intent_id}),
        )

    if order_intent.instrument_id not in authorization.allowed_instruments:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.INSTRUMENT_NOT_ALLOWED,),
            authorization_ref=authorization.authorization_id,
            trade_proposal_ref=order_intent.trade_proposal_ref,
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    if order_intent.side not in authorization.allowed_sides:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.SIDE_NOT_ALLOWED,),
            authorization_ref=authorization.authorization_id,
            trade_proposal_ref=order_intent.trade_proposal_ref,
        )

    if order_intent.order_type not in authorization.allowed_order_types:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.ORDER_TYPE_NOT_ALLOWED,),
            authorization_ref=authorization.authorization_id,
            trade_proposal_ref=order_intent.trade_proposal_ref,
        )

    if order_intent.quantity != risk_decision.approved_quantity:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            risk_decision_ref=risk_decision.risk_decision_id,
            trade_proposal_ref=order_intent.trade_proposal_ref,
        )

    notional = order_intent.quantity * (trade_proposal.reference_price_minor if trade_proposal else 0)
    if notional > authorization.max_order_notional_minor:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.NOTIONAL_LIMIT_EXCEEDED,),
            authorization_ref=authorization.authorization_id,
        )

    if broker_health is not None and broker_health.disposition != ReconciliationHealthState.HEALTHY:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_UNHEALTHY,),
            broker_health_ref=broker_health.health_id,
        )

    if reconciliation is not None and reconciliation.health_state != ReconciliationHealthState.HEALTHY:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RECONCILIATION_UNHEALTHY,),
        )

    if used_client_order_ids and order_intent.client_order_id in used_client_order_ids:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.DUPLICATE_CLIENT_ORDER_ID,),
            trade_proposal_ref=order_intent.trade_proposal_ref,
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    intent_hash = derive_payload_hash({"intent_id": order_intent.broker_order_intent_id})

    if production_config or BUILD28_PRODUCTION_FORBID_LIVE_SUBMIT:
        if allow_dry_run_in_test and not production_config:
            return LiveExecutionGateDecisionV1(
                gate_decision_id=derive_gate_decision_id(
                    {"decision": "ALLOW_DRY_RUN", "intent_hash": intent_hash}
                ),
                schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
                decision_time_ns=decision_time_ns,
                runtime_activation_ref=runtime_activation_ref,
                authorization_ref=authorization.authorization_id,
                broker_certification_ref=broker_certification.certification_id,
                opportunity_ref=opportunity.opportunity_id if opportunity else None,
                trade_proposal_ref=order_intent.trade_proposal_ref,
                risk_decision_ref=risk_decision.risk_decision_id,
                broker_health_ref=broker_health.health_id if broker_health else None,
                kill_switch_ref=kill_switch.kill_switch_id,
                broker=broker,
                account_environment=account_environment,
                requested_order_intent_hash=intent_hash,
                decision=LiveGateDecisionKind.ALLOW_DRY_RUN,
                reason_codes=(LiveGateReasonCode.DRY_RUN_ALLOWED,),
            )
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BUILD28_LIVE_SUBMIT_FORBIDDEN,),
            runtime_activation_ref=runtime_activation_ref,
            authorization_ref=authorization.authorization_id,
            broker_certification_ref=broker_certification.certification_id,
            opportunity_ref=opportunity.opportunity_id if opportunity else None,
            trade_proposal_ref=order_intent.trade_proposal_ref,
            risk_decision_ref=risk_decision.risk_decision_id,
            broker_health_ref=broker_health.health_id if broker_health else None,
            requested_order_intent_hash=intent_hash,
            decision=LiveGateDecisionKind.BLOCK,
        )

    # Unreachable in BUILD 28 — ALLOW_LIVE_SUBMIT exists for future contract only.
    return _blocked(
        **common,
        reason_codes=(LiveGateReasonCode.BUILD28_LIVE_SUBMIT_FORBIDDEN,),
        decision=LiveGateDecisionKind.FAIL_CLOSED,
    )
