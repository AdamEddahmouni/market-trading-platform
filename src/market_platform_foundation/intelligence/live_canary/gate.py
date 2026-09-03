"""Canary live execution gate — extends BUILD 28 with canary-specific checks (BUILD 29)."""

from __future__ import annotations

from ..contracts.opportunity import OpportunityV1
from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import RiskDecisionKind, RiskDecisionV1
from ..live_execution_safety.gate import _blocked
from ..live_execution_safety.identity import derive_gate_decision_id, derive_payload_hash
from ..live_execution_safety.types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerCapabilityCertificationV1,
    BrokerExecutionHealthV1,
    BrokerOrderIntentV1,
    BrokerOrderStateKind,
    BrokerReconciliationSnapshotV1,
    KillSwitchState,
    LiveExecutionAuthorizationV1,
    LiveExecutionGateDecisionV1,
    LiveExecutionKillSwitchV1,
    LiveGateDecisionKind,
    LiveGateReasonCode,
    ReconciliationHealthState,
)
from .authorization import AUTHORIZED_STATES, is_authorization_submittable
from .confirmation import validate_confirmation_for_intent
from .policy import effective_canary_quantity_cap
from .types import LiveCanaryPolicyV1, LiveOrderConfirmationV1


def evaluate_canary_live_gate(
    *,
    decision_time_ns: int,
    policy: LiveCanaryPolicyV1,
    broker: str,
    account_environment: AccountEnvironment,
    account_ref: str,
    runtime_activation_ref: str | None,
    runtime_allows_live: bool,
    authorization: LiveExecutionAuthorizationV1 | None,
    broker_certification: BrokerCapabilityCertificationV1 | None,
    opportunity: OpportunityV1 | None,
    trade_proposal: TradeProposalV1 | None,
    risk_decision: RiskDecisionV1 | None,
    order_intent: BrokerOrderIntentV1 | None,
    order_confirmation: LiveOrderConfirmationV1 | None,
    broker_health: BrokerExecutionHealthV1 | None,
    reconciliation: BrokerReconciliationSnapshotV1 | None,
    kill_switch: LiveExecutionKillSwitchV1,
    canary_kill_switch: LiveExecutionKillSwitchV1 | None = None,
    used_client_order_ids: frozenset[str] | None = None,
    orders_submitted: int = 0,
    ambiguous_client_order_ids: frozenset[str] | None = None,
    allow_live_submit_in_test: bool = False,
    persistence_healthy: bool = True,
    telemetry_evaluator_ok: bool = True,
    recovered_runtime_blocked: bool = False,
) -> LiveExecutionGateDecisionV1:
    """Evaluate canary gates; live submit only when all gates pass and test flag set."""
    common = {
        "decision_time_ns": decision_time_ns,
        "broker": broker,
        "account_environment": account_environment,
        "kill_switch_ref": kill_switch.kill_switch_id,
    }

    # Global kill switch always blocks unless canary permit is active.
    if kill_switch.state == KillSwitchState.ACTIVE_BLOCK:
        if canary_kill_switch is None or canary_kill_switch.state == KillSwitchState.ACTIVE_BLOCK:
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

    if account_ref != policy.account_ref:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.ACCOUNT_MISMATCH,),
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
        )

    if authorization.authorization_state not in AUTHORIZED_STATES:
        if authorization.authorization_state.value == "CONSUMED":
            reason = (LiveGateReasonCode.CANARY_AUTHORIZATION_CONSUMED,)
        elif authorization.authorization_state.value == "REVOKED":
            reason = (LiveGateReasonCode.CANARY_AUTHORIZATION_REVOKED,)
        else:
            reason = (LiveGateReasonCode.CANARY_AUTHORIZATION_NOT_AUTHORIZED,)
        return _blocked(
            **common,
            reason_codes=reason,
            authorization_ref=authorization.authorization_id,
        )

    submittable, auth_reason = is_authorization_submittable(
        authorization, decision_time_ns=decision_time_ns, orders_submitted=orders_submitted
    )
    if not submittable:
        if auth_reason == "EXPIRED":
            return _blocked(
                **common,
                reason_codes=(LiveGateReasonCode.AUTHORIZATION_EXPIRED,),
                authorization_ref=authorization.authorization_id,
            )
        if auth_reason == "ORDER_COUNT_EXHAUSTED":
            return _blocked(
                **common,
                reason_codes=(LiveGateReasonCode.CANARY_ORDER_COUNT_EXCEEDED,),
                authorization_ref=authorization.authorization_id,
            )
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.CANARY_AUTHORIZATION_NOT_AUTHORIZED,),
            authorization_ref=authorization.authorization_id,
        )

    if authorization.broker != broker:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.AUTHORIZATION_SCOPE_MISMATCH,),
            authorization_ref=authorization.authorization_id,
        )

    if broker_certification is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_NOT_CERTIFIED,),
            authorization_ref=authorization.authorization_id,
        )

    if opportunity is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            authorization_ref=authorization.authorization_id,
        )

    if trade_proposal is None or risk_decision is None or order_intent is None:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            authorization_ref=authorization.authorization_id,
        )

    if risk_decision.decision not in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE}:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    if order_intent.quantity != risk_decision.approved_quantity:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RISK_NOT_APPROVED,),
            risk_decision_ref=risk_decision.risk_decision_id,
        )

    ref_price = trade_proposal.reference_price_minor
    capped_qty = effective_canary_quantity_cap(
        policy=policy,
        risk_approved_quantity=risk_decision.approved_quantity,
        reference_price_minor=ref_price,
        account_buying_power_minor=trade_proposal.metadata.get("buying_power_minor"),
        model_confidence=trade_proposal.metadata.get("model_confidence"),
    )
    if capped_qty < order_intent.quantity:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.CANARY_NOTIONAL_CAP_EXCEEDED,),
            authorization_ref=authorization.authorization_id,
        )

    notional = order_intent.quantity * ref_price
    if notional > policy.max_single_order_notional_minor:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.CANARY_NOTIONAL_CAP_EXCEEDED,),
        )

    if policy.allow_margin is False and trade_proposal.metadata.get("uses_margin"):
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.CANARY_MARGIN_NOT_ALLOWED,),
        )

    if policy.allow_short is False and order_intent.side not in policy.allowed_sides:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.CANARY_SHORT_NOT_ALLOWED,),
        )

    if order_intent.side not in policy.allowed_sides:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.SIDE_NOT_ALLOWED,),
        )

    if order_intent.instrument_id not in policy.allowed_instruments:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.INSTRUMENT_NOT_ALLOWED,),
        )

    if policy.require_manual_order_confirmation:
        ok, conf_reason = validate_confirmation_for_intent(
            order_confirmation,
            order_intent=order_intent,
            authorization_ref=authorization.authorization_id,
            decision_time_ns=decision_time_ns,
        )
        if not ok:
            if conf_reason == "MISSING":
                return _blocked(
                    **common,
                    reason_codes=(LiveGateReasonCode.CANARY_ORDER_CONFIRMATION_MISSING,),
                    authorization_ref=authorization.authorization_id,
                )
            if conf_reason == "EXPIRED":
                return _blocked(
                    **common,
                    reason_codes=(LiveGateReasonCode.CANARY_ORDER_CONFIRMATION_EXPIRED,),
                )
            return _blocked(
                **common,
                reason_codes=(LiveGateReasonCode.CANARY_ORDER_CONFIRMATION_MISMATCH,),
            )

    if broker_health is not None and broker_health.disposition != ReconciliationHealthState.HEALTHY:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BROKER_UNHEALTHY,),
            broker_health_ref=broker_health.health_id,
        )

    if reconciliation is not None and reconciliation.health_state != ReconciliationHealthState.HEALTHY:
        if reconciliation.broker_only:
            return _blocked(
                **common,
                reason_codes=(LiveGateReasonCode.EXTERNAL_BROKER_ACTIVITY,),
            )
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RECONCILIATION_UNHEALTHY,),
        )

    if ambiguous_client_order_ids and order_intent.client_order_id in ambiguous_client_order_ids:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.AMBIGUOUS_SUBMISSION_BLOCK,),
        )

    if not persistence_healthy:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.PERSISTENCE_UNHEALTHY,),
            authorization_ref=authorization.authorization_id,
        )

    if not telemetry_evaluator_ok:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.OBSERVABILITY_DEGRADED,),
            authorization_ref=authorization.authorization_id,
        )

    if recovered_runtime_blocked:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.RECOVERED_RUNTIME_BLOCKED,),
            authorization_ref=authorization.authorization_id,
        )

    if used_client_order_ids and order_intent.client_order_id in used_client_order_ids:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.DUPLICATE_CLIENT_ORDER_ID,),
        )

    intent_hash = derive_payload_hash({"intent_id": order_intent.broker_order_intent_id})

    if not allow_live_submit_in_test:
        return _blocked(
            **common,
            reason_codes=(LiveGateReasonCode.BUILD28_LIVE_SUBMIT_FORBIDDEN,),
            authorization_ref=authorization.authorization_id,
            requested_order_intent_hash=intent_hash,
        )

    return LiveExecutionGateDecisionV1(
        gate_decision_id=derive_gate_decision_id({"decision": "ALLOW_LIVE_SUBMIT", "intent_hash": intent_hash}),
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        decision_time_ns=decision_time_ns,
        runtime_activation_ref=runtime_activation_ref,
        authorization_ref=authorization.authorization_id,
        broker_certification_ref=broker_certification.certification_id,
        opportunity_ref=opportunity.opportunity_id,
        trade_proposal_ref=order_intent.trade_proposal_ref,
        risk_decision_ref=risk_decision.risk_decision_id,
        broker_health_ref=broker_health.health_id if broker_health else None,
        kill_switch_ref=kill_switch.kill_switch_id,
        broker=broker,
        account_environment=account_environment,
        requested_order_intent_hash=intent_hash,
        decision=LiveGateDecisionKind.ALLOW_LIVE_SUBMIT,
        reason_codes=(),
    )
