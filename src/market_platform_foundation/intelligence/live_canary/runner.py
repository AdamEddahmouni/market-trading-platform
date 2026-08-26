"""Mock canary lifecycle runner (BUILD 29)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import RiskDecisionKind, RiskDecisionV1, RiskReasonCode, ExposureSnapshot
from ..live_execution_safety import (
    AccountEnvironment,
    build_broker_execution_health,
    build_broker_order_intent,
    build_production_kill_switch,
    build_reconciliation_snapshot,
    inventory_by_broker,
    certify_broker,
)
from ..live_execution_safety.types import LiveAuthorizationState, LiveExecutionKillSwitchV1, KillSwitchState
from .authorization import (
    authorize_canary_from_human_approval,
    consume_authorization,
    disable_authorization,
    prepare_canary_authorization_preview,
    record_human_canary_approval,
)
from .confirmation import build_order_confirmation_preview, confirm_order
from .gate import evaluate_canary_live_gate
from .identity import derive_account_fingerprint, derive_canary_run_id
from .ledger import LiveExecutionLedger
from .policy import BUILD29_KNOWN_LIMITATIONS, build_default_canary_policy
from .portfolio import build_live_portfolio_snapshot
from .reconciliation import evaluate_pre_canary_reconciliation
from .report import build_canary_qualification_report
from .submission import MockBrokerTransport
from .types import (
    CanaryDisposition,
    CanaryGovernanceState,
    HumanApprovalSource,
    LiveCanaryRunV1,
)

BUILD28_BRANCH = "cloud/build-28-live-execution-safety-gate"
BUILD27_HEAD = "6f278aaf2f7d741d8669861b907b3a7fd3db4995"


@dataclass
class CanaryRunResult:
    governance_state: CanaryGovernanceState
    disposition: CanaryDisposition
    report: object
    ledger: LiveExecutionLedger
    authorization_state: LiveAuthorizationState | None
    gate_allowed: bool
    limitations: tuple[str, ...]


def build_canary_kill_switch_permit(*, effective_from_ns: int) -> LiveExecutionKillSwitchV1:
    """Narrow canary permit — global kill switch remains ACTIVE_BLOCK."""
    from ..live_execution_safety.kill_switch import BUILD28_KILL_SWITCH_SCOPE
    from ..live_execution_safety.identity import derive_kill_switch_id
    from ..live_execution_safety.types import LIVE_EXECUTION_SAFETY_SCHEMA_VERSION

    ks = LiveExecutionKillSwitchV1(
        kill_switch_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope=f"{BUILD28_KILL_SWITCH_SCOPE}_CANARY_PERMIT",
        state=KillSwitchState.INACTIVE,
        reason="BUILD29_NARROW_CANARY_PERMIT",
        effective_from_ns=effective_from_ns,
        source="BUILD29_CANARY_SCOPE",
        lineage={"canary_scoped": True},
    )
    object.__setattr__(ks, "kill_switch_id", derive_kill_switch_id(ks))
    return ks


def run_mock_canary_lifecycle(
    *,
    broker: str = "tradier.paper",
    account_ref: str = "fp-canary-test",
    source_head: str = "",
    source_build28_ref: str = "",
    decision_time_ns: int,
    opportunity,
    trade_proposal: TradeProposalV1,
    risk_decision: RiskDecisionV1,
    reference_price_minor: int = 100_00,
    human_operator: str = "test-operator",
    simulate_fill: bool = True,
) -> CanaryRunResult:
    """Full mock canary lifecycle — no real network."""
    policy = build_default_canary_policy(broker=broker, account_ref=account_ref)
    portfolio = build_live_portfolio_snapshot(
        as_of_ns=decision_time_ns,
        broker=broker,
        account_ref=account_ref,
        cash_minor=10_000_00,
    )
    fingerprint = derive_account_fingerprint(account_ref)

    preview = prepare_canary_authorization_preview(
        policy=policy,
        broker=broker,
        account_ref=account_ref,
        account_fingerprint=fingerprint,
        generated_at_ns=decision_time_ns,
        known_limitations=BUILD29_KNOWN_LIMITATIONS,
    )

    human_approval = record_human_canary_approval(
        preview=preview,
        approved_at_ns=decision_time_ns + 1,
        approved_by=human_operator,
        approval_source=HumanApprovalSource.TEST_FIXTURE,
    )

    effective_until = decision_time_ns + policy.authorization_duration_ns
    authorization = authorize_canary_from_human_approval(
        policy=policy,
        preview=preview,
        human_approval=human_approval,
        effective_from_ns=decision_time_ns,
        effective_until_ns=effective_until,
    )

    pre_recon = evaluate_pre_canary_reconciliation(
        policy=policy,
        account_ref=account_ref,
        account_environment=AccountEnvironment.LIVE,
        broker_healthy=True,
        as_of_ns=decision_time_ns,
        portfolio=portfolio,
    )
    if not pre_recon.passed:
        report = build_canary_qualification_report(
            canary_run=_make_run(policy, authorization.authorization_id, decision_time_ns, source_head, source_build28_ref),
            authorization_ref=authorization.authorization_id,
            disposition=CanaryDisposition.CANARY_INVALID_RECONCILIATION,
            errors=pre_recon.reason_codes,
            limitations=BUILD29_KNOWN_LIMITATIONS,
        )
        return CanaryRunResult(
            governance_state=CanaryGovernanceState.CANARY_HALTED,
            disposition=CanaryDisposition.CANARY_INVALID_RECONCILIATION,
            report=report,
            ledger=LiveExecutionLedger(),
            authorization_state=authorization.authorization_state,
            gate_allowed=False,
            limitations=BUILD29_KNOWN_LIMITATIONS,
        )

    order_intent = build_broker_order_intent(
        trade_proposal=trade_proposal,
        risk_decision=risk_decision,
        execution_policy_ref=policy.required_execution_policy_ref,
        broker_target=broker,
        account_environment=AccountEnvironment.LIVE,
        decision_time_ns=decision_time_ns,
    )
    object.__setattr__(order_intent, "mode", "LIVE_CANARY")

    conf_preview = build_order_confirmation_preview(
        authorization_ref=authorization.authorization_id,
        order_intent=order_intent,
        risk_decision_ref=risk_decision.risk_decision_id,
        reference_price_minor=reference_price_minor,
        confirmation_time_ns=decision_time_ns,
    )
    order_confirmation = confirm_order(
        conf_preview,
        confirmed_by=human_operator,
        confirmation_source=HumanApprovalSource.TEST_FIXTURE,
        confirmation_time_ns=decision_time_ns + 2,
    )

    cert = certify_broker(inventory_by_broker(broker))
    broker_health = build_broker_execution_health(
        broker=broker,
        account_environment=AccountEnvironment.LIVE,
        as_of_ns=decision_time_ns,
        adapter_loaded=True,
        connection_available=True,
        environment_identified=True,
        account_resolved=True,
    )
    reconciliation = build_reconciliation_snapshot(
        broker=broker,
        account_environment=AccountEnvironment.LIVE,
        as_of_ns=decision_time_ns,
        local_open_intents=(),
        broker_open_orders=(),
    )

    global_ks = build_production_kill_switch(effective_from_ns=decision_time_ns)
    canary_ks = build_canary_kill_switch_permit(effective_from_ns=decision_time_ns)

    gate_decision = evaluate_canary_live_gate(
        decision_time_ns=decision_time_ns + 3,
        policy=policy,
        broker=broker,
        account_environment=AccountEnvironment.LIVE,
        account_ref=account_ref,
        runtime_activation_ref=policy.required_runtime_activation_ref,
        runtime_allows_live=True,
        authorization=authorization,
        broker_certification=cert,
        opportunity=opportunity,
        trade_proposal=trade_proposal,
        risk_decision=risk_decision,
        order_intent=order_intent,
        order_confirmation=order_confirmation,
        broker_health=broker_health,
        reconciliation=reconciliation,
        kill_switch=global_ks,
        canary_kill_switch=canary_ks,
        allow_live_submit_in_test=True,
    )

    ledger = LiveExecutionLedger()
    disposition = CanaryDisposition.CANARY_NOT_EXECUTED
    acks = 0
    fills = 0

    if gate_decision.decision.value == "ALLOW_LIVE_SUBMIT":
        transport = MockBrokerTransport()
        receipt = transport.submit(
            order_intent=order_intent,
            authorization_ref=authorization.authorization_id,
            confirmation_ref=order_confirmation.confirmation_id,
            submit_time_ns=decision_time_ns + 4,
        )
        ledger.record_submission(receipt)
        acks = 1 if receipt.broker_order_id else 0
        if simulate_fill and receipt.broker_order_id:
            fill = transport.apply_fill(
                broker_order_id=receipt.broker_order_id,
                quantity=order_intent.quantity,
                price_minor=reference_price_minor,
                fill_time_ns=decision_time_ns + 5,
            )
            if fill:
                ledger.record_fill(fill)
                fills = 1
        disposition = CanaryDisposition.CANARY_EXECUTED_CLEAN
        authorization = consume_authorization(authorization)
    else:
        disposition = CanaryDisposition.CANARY_NOT_EXECUTED

    authorization = disable_authorization(authorization)
    run = _make_run(policy, authorization.authorization_id, decision_time_ns, source_head, source_build28_ref)
    report = build_canary_qualification_report(
        canary_run=run,
        authorization_ref=authorization.authorization_id,
        opportunities_observed=1,
        orders_confirmed=1,
        submit_attempts=ledger.orders_submitted,
        acks=acks,
        fills=fills,
        real_notional_minor=ledger.total_notional_minor,
        reconciliation_health=reconciliation.health_state.value,
        broker_health=broker_health.disposition.value,
        authorization_lifecycle=("PREPARED", "AUTHORIZED", "CONSUMED", "DISABLED"),
        disposition=disposition,
        limitations=BUILD29_KNOWN_LIMITATIONS,
    )

    return CanaryRunResult(
        governance_state=CanaryGovernanceState.CANARY_COMPLETE,
        disposition=disposition,
        report=report,
        ledger=ledger,
        authorization_state=authorization.authorization_state,
        gate_allowed=gate_decision.decision.value == "ALLOW_LIVE_SUBMIT",
        limitations=BUILD29_KNOWN_LIMITATIONS,
    )


def _make_run(
    policy,
    authorization_ref: str | None,
    start_time_ns: int,
    source_head: str,
    source_build28_ref: str,
) -> LiveCanaryRunV1:
    run = LiveCanaryRunV1(
        canary_run_id="",
        schema_version="1",
        source_build28_ref=source_build28_ref,
        source_build27_ref=BUILD27_HEAD,
        source_head=source_head,
        canary_policy_ref=policy.canary_policy_id,
        authorization_ref=authorization_ref,
        broker=policy.broker,
        account_ref=policy.account_ref,
        start_time_ns=start_time_ns,
        end_time_ns=None,
        allowed_order_count=policy.max_order_count,
        allowed_notional_minor=policy.max_total_canary_notional_minor,
        initial_reconciliation_ref=None,
        initial_portfolio_ref=None,
        runtime_activation_ref=policy.required_runtime_activation_ref,
        execution_policy_ref=policy.required_execution_policy_ref,
        champion_ref=None,
    )
    object.__setattr__(run, "canary_run_id", derive_canary_run_id(run))
    return run
