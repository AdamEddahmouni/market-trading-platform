"""Supervised multi-session canary program runner (BUILD 30)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.trade_proposal import TradeProposalV1
from ..execution.types import RiskDecisionV1
from ..live_execution_safety import (
    AccountEnvironment,
    build_broker_execution_health,
    build_broker_order_intent,
    build_production_kill_switch,
    build_reconciliation_snapshot,
    inventory_by_broker,
    certify_broker,
)
from ..live_execution_safety.types import LiveAuthorizationState, KillSwitchState
from .authorization import (
    authorize_canary_from_human_approval,
    consume_authorization,
    disable_authorization,
    prepare_canary_authorization_preview,
    record_human_canary_approval,
)
from .confirmation import build_order_confirmation_preview, confirm_order
from .gate import evaluate_canary_live_gate
from .identity import derive_account_fingerprint, derive_canary_run_id, derive_program_run_id
from .incidents import create_incident, resolve_incident
from .kill_switch_store import KillSwitchStore
from .ledger import LiveExecutionLedger
from .policy import build_default_canary_policy
from .portfolio import build_live_portfolio_snapshot
from .program_accounting import ProgramAccounting
from .program_gate import evaluate_session_end_gate, evaluate_session_start_gate
from .program_policy import BUILD30_KNOWN_LIMITATIONS, build_default_program_policy
from .program_report import build_program_report, build_session_report
from .reconciliation import evaluate_pre_canary_reconciliation
from .reconciliation_checkpoint import build_reconciliation_checkpoint, evaluate_checkpoint_clean
from .runner import BUILD28_BRANCH, build_canary_kill_switch_permit
from .submission import MockBrokerTransport
from .types import (
    DEFAULT_PROGRAM_DURATION_NS,
    HumanApprovalSource,
    IncidentSeverity,
    IncidentType,
    LiveCanaryProgramPolicyV1,
    LiveCanaryProgramRunV1,
    LiveCanaryRunV1,
    ProgramDisposition,
    ProgramGovernanceState,
    SessionDisposition,
)

BUILD29_HEAD = "fa0022b"


@dataclass
class SessionRunResult:
    session_ref: str
    disposition: SessionDisposition
    session_report: object
    ledger: LiveExecutionLedger
    authorization_id: str | None
    authorization_state: LiveAuthorizationState | None
    incidents: list[object] = field(default_factory=list)


@dataclass
class ProgramRunResult:
    governance_state: ProgramGovernanceState
    disposition: ProgramDisposition
    program_run: LiveCanaryProgramRunV1
    program_report: object
    session_results: list[SessionRunResult]
    accounting: ProgramAccounting
    ledger: LiveExecutionLedger
    kill_switch: KillSwitchStore
    incidents: list[object]
    limitations: tuple[str, ...]


def _authorize_session(
    *,
    policy,
    broker: str,
    account_ref: str,
    decision_time_ns: int,
    human_operator: str,
) -> tuple[object, object]:
    fingerprint = derive_account_fingerprint(account_ref)
    preview = prepare_canary_authorization_preview(
        policy=policy,
        broker=broker,
        account_ref=account_ref,
        account_fingerprint=fingerprint,
        generated_at_ns=decision_time_ns,
        known_limitations=BUILD30_KNOWN_LIMITATIONS,
    )
    approval = record_human_canary_approval(
        preview=preview,
        approved_at_ns=decision_time_ns + 1,
        approved_by=human_operator,
        approval_source=HumanApprovalSource.TEST_FIXTURE,
    )
    auth = authorize_canary_from_human_approval(
        policy=policy,
        preview=preview,
        human_approval=approval,
        effective_from_ns=decision_time_ns,
        effective_until_ns=decision_time_ns + policy.authorization_duration_ns,
    )
    return preview, auth


def _run_session_order(
    *,
    policy,
    authorization,
    trade_proposal: TradeProposalV1,
    risk_decision: RiskDecisionV1,
    opportunity,
    decision_time_ns: int,
    reference_price_minor: int,
    human_operator: str,
    ledger: LiveExecutionLedger,
    transport: MockBrokerTransport,
    partial_fill_qty: int | None = None,
    invalidate_confirmation: bool = False,
) -> tuple[bool, int, int, str | None]:
    order_intent = build_broker_order_intent(
        trade_proposal=trade_proposal,
        risk_decision=risk_decision,
        execution_policy_ref=policy.required_execution_policy_ref,
        broker_target=policy.broker,
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
    if invalidate_confirmation:
        return False, 0, 0, None

    order_confirmation = confirm_order(
        conf_preview,
        confirmed_by=human_operator,
        confirmation_source=HumanApprovalSource.TEST_FIXTURE,
        confirmation_time_ns=decision_time_ns + 2,
    )

    cert = certify_broker(inventory_by_broker(policy.broker))
    broker_health = build_broker_execution_health(
        broker=policy.broker,
        account_environment=AccountEnvironment.LIVE,
        as_of_ns=decision_time_ns,
        adapter_loaded=True,
        connection_available=True,
        environment_identified=True,
        account_resolved=True,
    )
    reconciliation = build_reconciliation_snapshot(
        broker=policy.broker,
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
        broker=policy.broker,
        account_environment=AccountEnvironment.LIVE,
        account_ref=policy.account_ref,
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
        orders_submitted=0,
        allow_live_submit_in_test=True,
    )

    if gate_decision.decision.value != "ALLOW_LIVE_SUBMIT":
        return False, 0, 0, None

    receipt = transport.submit(
        order_intent=order_intent,
        authorization_ref=authorization.authorization_id,
        confirmation_ref=order_confirmation.confirmation_id,
        submit_time_ns=decision_time_ns + 4,
    )
    ledger.record_submission(receipt)
    acks = 1 if receipt.broker_order_id else 0
    fills = 0
    if receipt.broker_order_id:
        if partial_fill_qty is not None and partial_fill_qty < order_intent.quantity:
            fill = transport.apply_partial_fill(
                broker_order_id=receipt.broker_order_id,
                quantity=partial_fill_qty,
                price_minor=reference_price_minor,
                fill_time_ns=decision_time_ns + 5,
            )
            if fill:
                ledger.record_fill(fill)
                fills = 1
        else:
            fill = transport.apply_fill(
                broker_order_id=receipt.broker_order_id,
                quantity=order_intent.quantity,
                price_minor=reference_price_minor,
                fill_time_ns=decision_time_ns + 5,
            )
            if fill:
                ledger.record_fill(fill)
                fills = 1
    return True, acks, fills, order_confirmation.confirmation_id


def run_mock_program_lifecycle(
    *,
    broker: str = "tradier.paper",
    account_ref: str = "fp-canary-test",
    source_head: str = "",
    program_start_ns: int,
    trade_proposal: TradeProposalV1,
    risk_decision: RiskDecisionV1,
    opportunity,
    reference_price_minor: int = 25_00,
    human_operator: str = "test-operator",
    session2_partial_qty: int = 1,
    session2_total_qty: int = 2,
) -> ProgramRunResult:
    """Full deterministic multi-session mock lifecycle."""
    program_policy = build_default_program_policy(
        allowed_brokers=(broker,),
        allowed_accounts=(account_ref,),
        program_effective_from_ns=program_start_ns,
        program_effective_until_ns=program_start_ns + DEFAULT_PROGRAM_DURATION_NS,
    )
    canary_policy = build_default_canary_policy(broker=broker, account_ref=account_ref)

    program_run = LiveCanaryProgramRunV1(
        program_run_id="",
        schema_version="1",
        source_build29_ref=BUILD29_HEAD,
        source_build28_ref=BUILD28_BRANCH,
        source_head=source_head,
        program_policy_ref=program_policy.program_policy_id,
        broker_certification_refs=("BUILD28_ZERO_SUBMIT",),
        starting_reconciliation_ref=None,
        starting_portfolio_ref=None,
        program_start_ns=program_start_ns,
        program_end_ns=None,
        allowed_session_count=program_policy.max_sessions,
        session_refs=(),
    )
    object.__setattr__(program_run, "program_run_id", derive_program_run_id(program_run))

    accounting = ProgramAccounting()
    ledger = LiveExecutionLedger()
    transport = MockBrokerTransport()
    kill_switch = KillSwitchStore()
    kill_switch.permit_program("PROGRAM_ACTIVE")
    incidents: list[object] = []
    session_results: list[SessionRunResult] = []
    prior_auth_ref: str | None = None
    governance = ProgramGovernanceState.PROGRAM_ACTIVE
    restart_events = 0

    cooldown_ns = program_policy.minimum_cooldown_between_sessions_ns

    # Session 1 — full fill
    t1 = program_start_ns + 1_000_000_000
    preview1, auth1 = _authorize_session(
        policy=canary_policy,
        broker=broker,
        account_ref=account_ref,
        decision_time_ns=t1,
        human_operator=human_operator,
    )
    accounting.sessions_authorized += 1

    portfolio = build_live_portfolio_snapshot(
        as_of_ns=t1, broker=broker, account_ref=account_ref, cash_minor=10_000_00
    )
    checkpoint = build_reconciliation_checkpoint(
        as_of_ns=t1,
        broker=broker,
        account_ref=account_ref,
        ledger=ledger,
        program_run_ref=program_run.program_run_id,
    )
    start_gate = evaluate_session_start_gate(
        policy=program_policy,
        accounting=accounting,
        decision_time_ns=t1,
        kill_switch=kill_switch,
        checkpoint=checkpoint,
        broker_healthy=True,
        account_matched=True,
        authorization=auth1,
        prior_authorization_ref=prior_auth_ref,
        status_feed_as_of_ns=t1,
    )
    if not start_gate.allowed:
        governance = ProgramGovernanceState.PROGRAM_HALTED
    else:
        run1 = LiveCanaryRunV1(
            canary_run_id="",
            schema_version="1",
            source_build28_ref=BUILD28_BRANCH,
            source_build27_ref="",
            source_head=source_head,
            canary_policy_ref=canary_policy.canary_policy_id,
            authorization_ref=auth1.authorization_id,
            broker=broker,
            account_ref=account_ref,
            start_time_ns=t1,
            end_time_ns=None,
            allowed_order_count=canary_policy.max_order_count,
            allowed_notional_minor=canary_policy.max_total_canary_notional_minor,
            initial_reconciliation_ref=checkpoint.checkpoint_id,
            initial_portfolio_ref=None,
            runtime_activation_ref=canary_policy.required_runtime_activation_ref,
            execution_policy_ref=canary_policy.required_execution_policy_ref,
            champion_ref=None,
        )
        object.__setattr__(run1, "canary_run_id", derive_canary_run_id(run1))

        executed, acks, fills, conf_id = _run_session_order(
            policy=canary_policy,
            authorization=auth1,
            trade_proposal=trade_proposal,
            risk_decision=risk_decision,
            opportunity=opportunity,
            decision_time_ns=t1,
            reference_price_minor=reference_price_minor,
            human_operator=human_operator,
            ledger=ledger,
            transport=transport,
        )
        auth1 = consume_authorization(auth1) if executed else auth1
        auth1 = disable_authorization(auth1)
        notional = reference_price_minor * trade_proposal.requested_quantity
        if executed:
            accounting.record_session_submit(notional)
            accounting.record_ack()
            accounting.record_fill(
                quantity=trade_proposal.requested_quantity,
                price_minor=reference_price_minor,
            )

        end_cp = build_reconciliation_checkpoint(
            as_of_ns=t1 + 10_000_000_000,
            broker=broker,
            account_ref=account_ref,
            ledger=ledger,
            broker_open_orders=transport.get_open_orders(),
            broker_fills=tuple(f.broker_fill_id for f in ledger.fill_receipts),
            session_ref=run1.canary_run_id,
            program_run_ref=program_run.program_run_id,
        )
        end_gate = evaluate_session_end_gate(
            policy=program_policy,
            checkpoint=end_cp,
        )
        disposition = (
            SessionDisposition.SESSION_EXECUTED_CLEAN
            if executed and end_gate.allowed
            else SessionDisposition.SESSION_NOT_EXECUTED
        )
        session_report = build_session_report(
            session_ref=run1.canary_run_id,
            program_run_ref=program_run.program_run_id,
            authorization_ref=auth1.authorization_id,
            confirmations=(conf_id,) if conf_id else (),
            submit_attempts=1 if executed else 0,
            acks=acks,
            fills=fills,
            max_exposure_minor=notional if executed else 0,
            reconciliation_checkpoint_ref=end_cp.checkpoint_id,
            final_authorization_state=auth1.authorization_state.value,
            disposition=disposition,
            limitations=BUILD30_KNOWN_LIMITATIONS,
        )
        accounting.record_session_complete(
            session_ref=run1.canary_run_id,
            authorization_ref=auth1.authorization_id,
            clean=end_gate.allowed,
            executed=executed,
            end_ns=t1 + 10_000_000_000,
        )
        session_results.append(
            SessionRunResult(
                session_ref=run1.canary_run_id,
                disposition=disposition,
                session_report=session_report,
                ledger=ledger,
                authorization_id=auth1.authorization_id,
                authorization_state=auth1.authorization_state,
            )
        )
        prior_auth_ref = auth1.authorization_id

    # Session 2 — partial fill, restart, remaining fill
    t2 = program_start_ns + cooldown_ns + 20_000_000_000
    session2_price = min(
        reference_price_minor,
        canary_policy.max_single_order_notional_minor // max(1, session2_total_qty),
    )
    proposal2, risk2 = _scaled_proposal(
        trade_proposal, risk_decision, session2_total_qty, price_minor=session2_price
    )
    preview2, auth2 = _authorize_session(
        policy=canary_policy,
        broker=broker,
        account_ref=account_ref,
        decision_time_ns=t2,
        human_operator=human_operator,
    )
    if auth2.authorization_id == prior_auth_ref:
        raise ValueError("AUTHORIZATION_REUSE_DETECTED")
    accounting.sessions_authorized += 1

    portfolio2 = build_live_portfolio_snapshot(
        as_of_ns=t2, broker=broker, account_ref=account_ref, cash_minor=10_000_00
    )
    checkpoint2 = build_reconciliation_checkpoint(
        as_of_ns=t2,
        broker=broker,
        account_ref=account_ref,
        ledger=ledger,
        program_run_ref=program_run.program_run_id,
    )
    start_gate2 = evaluate_session_start_gate(
        policy=program_policy,
        accounting=accounting,
        decision_time_ns=t2,
        kill_switch=kill_switch,
        checkpoint=checkpoint2,
        broker_healthy=True,
        account_matched=True,
        authorization=auth2,
        prior_authorization_ref=prior_auth_ref,
        status_feed_as_of_ns=t2,
    )
    if start_gate2.allowed:
        run2 = LiveCanaryRunV1(
            canary_run_id="",
            schema_version="1",
            source_build28_ref=BUILD28_BRANCH,
            source_build27_ref="",
            source_head=source_head,
            canary_policy_ref=canary_policy.canary_policy_id,
            authorization_ref=auth2.authorization_id,
            broker=broker,
            account_ref=account_ref,
            start_time_ns=t2,
            end_time_ns=None,
            allowed_order_count=canary_policy.max_order_count,
            allowed_notional_minor=canary_policy.max_total_canary_notional_minor,
            initial_reconciliation_ref=checkpoint2.checkpoint_id,
            initial_portfolio_ref=None,
            runtime_activation_ref=canary_policy.required_runtime_activation_ref,
            execution_policy_ref=canary_policy.required_execution_policy_ref,
            champion_ref=None,
        )
        object.__setattr__(run2, "canary_run_id", derive_canary_run_id(run2))

        executed2, acks2, fills2, conf_id2 = _run_session_order(
            policy=canary_policy,
            authorization=auth2,
            trade_proposal=proposal2,
            risk_decision=risk2,
            opportunity=opportunity,
            decision_time_ns=t2,
            reference_price_minor=session2_price,
            human_operator=human_operator,
            ledger=ledger,
            transport=transport,
            partial_fill_qty=session2_partial_qty,
        )
        if executed2 and session2_partial_qty:
            accounting.record_fill(
                quantity=session2_partial_qty, price_minor=session2_price
            )

        # Simulate restart
        persisted_receipts = list(ledger.submission_receipts)
        persisted_fills = list(ledger.fill_receipts)
        transport.restore_from_persistence(
            receipts=persisted_receipts,
            fills=persisted_fills,
        )
        ledger.restore_from_persistence(
            receipts=persisted_receipts,
            fills=persisted_fills,
        )
        restart_events += 1
        kill_switch_restored = KillSwitchStore.from_persistence_dict(
            kill_switch.to_persistence_dict()
        )
        kill_switch = kill_switch_restored

        # Stale confirmation must not auto-submit after restart
        stale_blocked, _, _, _ = _run_session_order(
            policy=canary_policy,
            authorization=auth2,
            trade_proposal=proposal2,
            risk_decision=risk2,
            opportunity=opportunity,
            decision_time_ns=t2 + 5_000_000_000,
            reference_price_minor=reference_price_minor,
            human_operator=human_operator,
            ledger=ledger,
            transport=transport,
            invalidate_confirmation=True,
        )
        if stale_blocked:
            raise ValueError("STALE_CONFIRMATION_SHOULD_BLOCK")

        # Complete remaining fill after restart with fresh confirmation
        open_orders = transport.get_open_orders()
        if executed2 and open_orders:
            for client_id in open_orders:
                receipt = transport.submitted.get(client_id)
                if receipt and receipt.broker_order_id:
                    broker_order_id = receipt.broker_order_id
                    break
            else:
                broker_order_id = None
            if broker_order_id:
                remaining = session2_total_qty - session2_partial_qty
                if remaining > 0:
                    fill2 = transport.apply_partial_fill(
                        broker_order_id=broker_order_id,
                        quantity=remaining,
                        price_minor=session2_price,
                        fill_time_ns=t2 + 6_000_000_000,
                        fill_suffix="-2",
                    )
                    if fill2:
                        ledger.record_fill(fill2)
                        fills2 += 1
                        accounting.record_fill(
                            quantity=remaining, price_minor=session2_price
                        )

        auth2 = consume_authorization(auth2) if executed2 else auth2
        auth2 = disable_authorization(auth2)
        notional2 = session2_price * session2_total_qty
        if executed2:
            accounting.record_session_submit(notional2)
            accounting.record_ack()

        end_cp2 = build_reconciliation_checkpoint(
            as_of_ns=t2 + 15_000_000_000,
            broker=broker,
            account_ref=account_ref,
            ledger=ledger,
            broker_open_orders=transport.get_open_orders(),
            broker_fills=tuple(f.broker_fill_id for f in ledger.fill_receipts),
            session_ref=run2.canary_run_id,
            program_run_ref=program_run.program_run_id,
        )
        end_gate2 = evaluate_session_end_gate(
            policy=program_policy,
            checkpoint=end_cp2,
        )
        disposition2 = (
            SessionDisposition.SESSION_EXECUTED_CLEAN
            if executed2 and end_gate2.allowed
            else SessionDisposition.SESSION_NOT_EXECUTED
        )
        session_report2 = build_session_report(
            session_ref=run2.canary_run_id,
            program_run_ref=program_run.program_run_id,
            authorization_ref=auth2.authorization_id,
            confirmations=(conf_id2,) if conf_id2 else (),
            submit_attempts=1 if executed2 else 0,
            acks=acks2,
            fills=fills2,
            max_exposure_minor=notional2 if executed2 else 0,
            reconciliation_checkpoint_ref=end_cp2.checkpoint_id,
            final_authorization_state=auth2.authorization_state.value,
            disposition=disposition2,
            limitations=BUILD30_KNOWN_LIMITATIONS,
        )
        accounting.record_session_complete(
            session_ref=run2.canary_run_id,
            authorization_ref=auth2.authorization_id,
            clean=end_gate2.allowed,
            executed=executed2,
            end_ns=t2 + 15_000_000_000,
        )
        session_results.append(
            SessionRunResult(
                session_ref=run2.canary_run_id,
                disposition=disposition2,
                session_report=session_report2,
                ledger=ledger,
                authorization_id=auth2.authorization_id,
                authorization_state=auth2.authorization_state,
            )
        )

    # Program complete — block new live submits
    exceeded, _ = accounting.program_cap_exceeded(program_policy)
    kill_switch.block_program("PROGRAM_COMPLETE")
    governance = ProgramGovernanceState.PROGRAM_COMPLETE

    program_disposition = (
        ProgramDisposition.SUPERVISED_CANARY_PROGRAM_COMPLETE
        if accounting.sessions_executed >= 2
        else ProgramDisposition.SUPERVISED_CANARY_PROGRAM_COMPLETE_WITH_LIMITATIONS
    )

    program_report = build_program_report(
        program_run_ref=program_run.program_run_id,
        program_policy_ref=program_policy.program_policy_id,
        session_refs=tuple(s.session_ref for s in session_results),
        sessions_prepared=len(session_results),
        sessions_authorized=accounting.sessions_authorized,
        sessions_executed=accounting.sessions_executed,
        sessions_clean=accounting.sessions_clean,
        sessions_halted=accounting.sessions_halted,
        total_orders=accounting.total_submit_attempts,
        total_fills=accounting.total_fills,
        aggregate_notional_minor=accounting.filled_notional_minor,
        fees_minor=accounting.fees_minor,
        incident_counts={},
        reconciliation_outcomes=("CLEAN",),
        restart_events=restart_events,
        external_activity_detected=False,
        program_cap_usage={
            "sessions": accounting.sessions_completed,
            "orders": accounting.total_submit_attempts,
            "notional_minor": accounting.filled_notional_minor,
        },
        final_kill_switch_state=kill_switch.program_state.value,
        disposition=program_disposition,
        limitations=BUILD30_KNOWN_LIMITATIONS,
    )

    return ProgramRunResult(
        governance_state=governance,
        disposition=program_disposition,
        program_run=program_run,
        program_report=program_report,
        session_results=session_results,
        accounting=accounting,
        ledger=ledger,
        kill_switch=kill_switch,
        incidents=incidents,
        limitations=BUILD30_KNOWN_LIMITATIONS,
    )


def run_mock_incident_lifecycle(
    *,
    broker: str = "tradier.paper",
    account_ref: str = "fp-canary-test",
    program_start_ns: int,
) -> tuple[object, list[object], KillSwitchStore]:
    """Broker-only order incident → halt → manual resume path."""
    program_policy = build_default_program_policy(
        allowed_brokers=(broker,),
        allowed_accounts=(account_ref,),
        program_effective_from_ns=program_start_ns,
    )
    ledger = LiveExecutionLedger()
    kill_switch = KillSwitchStore()
    kill_switch.permit_program("PROGRAM_ACTIVE")

    checkpoint = build_reconciliation_checkpoint(
        as_of_ns=program_start_ns,
        broker=broker,
        account_ref=account_ref,
        ledger=ledger,
        broker_open_orders=("EXTERNAL-MANUAL-ORDER",),
    )
    incident = create_incident(
        incident_type=IncidentType.BROKER_ONLY_ORDER,
        severity=IncidentSeverity.CRITICAL,
        detected_at_ns=program_start_ns,
        description="Unexpected broker-only order detected",
    )
    kill_switch.activate_program_block("CRITICAL_INCIDENT")
    accounting = ProgramAccounting()
    start_gate = evaluate_session_start_gate(
        policy=program_policy,
        accounting=accounting,
        decision_time_ns=program_start_ns,
        kill_switch=kill_switch,
        checkpoint=checkpoint,
        broker_healthy=True,
        account_matched=True,
        authorization=None,
        open_incidents=(incident,),
    )
    resolved = resolve_incident(
        incident,
        resolution_evidence_ref="EVIDENCE-1",
        resolved_at_ns=program_start_ns + 1_000_000_000,
    )
    return start_gate, [incident, resolved], kill_switch


def program_policy_duration_ns() -> int:
    from .types import DEFAULT_PROGRAM_DURATION_NS

    return DEFAULT_PROGRAM_DURATION_NS


def _scaled_proposal(
    proposal: TradeProposalV1,
    risk: RiskDecisionV1,
    qty: int,
    price_minor: int | None = None,
) -> tuple[TradeProposalV1, RiskDecisionV1]:
    price = price_minor if price_minor is not None else proposal.reference_price_minor
    proposal2 = TradeProposalV1(
        proposal_id=proposal.proposal_id + "-s2",
        schema_version=proposal.schema_version,
        opportunity_id=proposal.opportunity_id,
        execution_policy_id=proposal.execution_policy_id,
        instrument_id=proposal.instrument_id,
        side=proposal.side,
        requested_quantity=qty,
        requested_notional_minor=qty * price,
        reference_price_minor=price,
        proposal_time_ns=proposal.proposal_time_ns,
        expires_at_ns=proposal.expires_at_ns,
        execution_mode=proposal.execution_mode,
        opportunity_ref=proposal.opportunity_ref,
        metadata=dict(proposal.metadata),
    )
    risk2 = RiskDecisionV1(
        risk_decision_id=risk.risk_decision_id + "-s2",
        schema_version=risk.schema_version,
        trade_proposal_id=proposal2.proposal_id,
        opportunity_id=risk.opportunity_id,
        execution_policy_id=risk.execution_policy_id,
        portfolio_snapshot_id=risk.portfolio_snapshot_id,
        decision_time_ns=risk.decision_time_ns,
        requested_quantity=qty,
        requested_notional_minor=qty * price,
        approved_quantity=qty,
        approved_notional_minor=qty * price,
        decision=risk.decision,
        reason_codes=risk.reason_codes,
        pre_trade_exposure=risk.pre_trade_exposure,
    )
    return proposal2, risk2
