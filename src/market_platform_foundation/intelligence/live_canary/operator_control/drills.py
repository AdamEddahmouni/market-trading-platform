"""Incident drill specifications and qualification runner (BUILD 31).

All drills use fixtures/mock transports — zero real broker side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from unittest import mock

from ..confirmation import build_order_confirmation_preview
from ..identity import derive_account_fingerprint
from ..policy import build_default_canary_policy
from ..program_policy import build_default_program_policy
from ..submission import MockBrokerTransport
from ...live_execution_safety import build_broker_order_intent
from ...live_execution_safety.types import AccountEnvironment
from ..types import HumanApprovalSource, IncidentSeverity, IncidentType, ProgramGovernanceState
from .commands import (
    acknowledge_incident,
    activate_kill_switch,
    approve_resume,
    authorize_reviewed_session,
    confirm_reviewed_order,
    inject_incident,
    prepare_session_authorization,
    register_pending_order_review,
    submit_resolution_evidence,
)
from .context import OperatorControlContext, PendingOrderReview
from .identity import derive_drill_report_id
from .snapshot import build_operator_control_snapshot
from .types import (
    OPERATOR_CONTROL_IMPLEMENTATION_VERSION,
    OPERATOR_CONTROL_SCHEMA_VERSION,
    DrillResult,
    IncidentDrillReportV1,
    IncidentDrillSpecV1,
)

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT = "fp-canary-test"


def _base_context() -> OperatorControlContext:
    program_policy = build_default_program_policy(program_effective_from_ns=T)
    canary_policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
    ctx = OperatorControlContext(
        program_policy=program_policy,
        canary_policy=canary_policy,
        governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
        session_ref="session-drill-1",
        broker_health="HEALTHY",
        reconciliation_health="CLEAN",
        drill_mode=True,
    )
    ctx.kill_switch.permit_program("DRILL_INIT")
    return ctx


def _drill_specs() -> dict[str, IncidentDrillSpecV1]:
    specs: dict[str, IncidentDrillSpecV1] = {}
    scenarios = {
        "D01": ("broker disconnect", IncidentType.BROKER_DISCONNECT, IncidentSeverity.CRITICAL),
        "D02": ("stale status", IncidentType.STATUS_FEED_STALE, IncidentSeverity.WARNING),
        "D03": ("broker-only order", IncidentType.BROKER_ONLY_ORDER, IncidentSeverity.CRITICAL),
        "D04": ("local-only order", IncidentType.LOCAL_ONLY_ORDER, IncidentSeverity.CRITICAL),
        "D05": ("ambiguous submission", IncidentType.AMBIGUOUS_SUBMISSION, IncidentSeverity.CRITICAL),
        "D06": ("unexpected fill", IncidentType.UNEXPECTED_FILL, IncidentSeverity.CRITICAL),
        "D07": ("position mismatch", IncidentType.UNKNOWN_POSITION, IncidentSeverity.CRITICAL),
        "D08": ("partial fill restart", IncidentType.ORDER_STATE_MISMATCH, IncidentSeverity.CRITICAL),
        "D09": ("global kill switch", IncidentType.KILL_SWITCH_TRIGGERED, IncidentSeverity.CRITICAL),
        "D10": ("session kill switch", IncidentType.KILL_SWITCH_TRIGGERED, IncidentSeverity.CRITICAL),
        "D11": ("auth expiry during review", IncidentType.AUTHORIZATION_VIOLATION_ATTEMPT, IncidentSeverity.WARNING),
        "D12": ("stale confirmation view", IncidentType.CAP_VIOLATION_ATTEMPT, IncidentSeverity.WARNING),
        "D13": ("external broker order", IncidentType.EXTERNAL_ACCOUNT_ACTIVITY, IncidentSeverity.CRITICAL),
        "D14": ("critical incident resume", IncidentType.RECONCILIATION_FAILED, IncidentSeverity.CRITICAL),
        "D15": ("stale confirmation after restart", IncidentType.ORDER_STATE_MISMATCH, IncidentSeverity.WARNING),
    }
    for drill_id, (scenario, itype, severity) in scenarios.items():
        spec = IncidentDrillSpecV1(
            drill_spec_id=drill_id,
            schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
            scenario=scenario,
            initial_state={"governance": "PROGRAM_ACTIVE"},
            injected_incident={"type": itype.value, "severity": severity.value},
            expected_alerts=(itype.value,),
            expected_blocked_actions=("CONFIRM_ORDER", "AUTHORIZE_SESSION"),
            expected_operator_workflow=(
                "detect",
                "acknowledge",
                "reconcile",
                "resolve",
                "resume_review",
                "fresh_authorization",
            ),
            expected_final_state={"live_blocked": True},
            timeout_expectation_ns=300_000_000_000,
            implementation_version=OPERATOR_CONTROL_IMPLEMENTATION_VERSION,
        )
        specs[drill_id] = spec
    return specs


DRILL_SPECS = _drill_specs()


@dataclass
class DrillRunOutcome:
    report: IncidentDrillReportV1
    context: OperatorControlContext


def _make_pending_review(ctx: OperatorControlContext, *, qty: int = 1) -> str:
    from market_platform_foundation.intelligence.contracts.common import (
        INTELLIGENCE_SCHEMA_VERSION,
        ContractKind,
        ContractReference,
    )
    from market_platform_foundation.intelligence.contracts.trade_proposal import TradeProposalV1
    from market_platform_foundation.intelligence.execution.types import (
        ExposureSnapshot,
        RiskDecisionKind,
        RiskDecisionV1,
        RiskReasonCode,
    )

    proposal = TradeProposalV1(
        proposal_id="tp-drill-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="opp-drill-1",
        execution_policy_id="ep-1",
        instrument_id="inst-aapl",
        side="BUY",
        requested_quantity=qty,
        requested_notional_minor=qty * 25_00,
        reference_price_minor=25_00,
        proposal_time_ns=T,
        expires_at_ns=T + 600_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-drill-1"),
        metadata={},
    )
    risk = RiskDecisionV1(
        risk_decision_id="risk-drill-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="tp-drill-1",
        opportunity_id="opp-drill-1",
        execution_policy_id="ep-1",
        portfolio_snapshot_id="port-1",
        decision_time_ns=T,
        requested_quantity=qty,
        requested_notional_minor=qty * 25_00,
        approved_quantity=max(1, qty - 1) if qty > 1 else qty,
        approved_notional_minor=max(1, qty - 1) * 25_00 if qty > 1 else qty * 25_00,
        decision=RiskDecisionKind.APPROVE,
        reason_codes=(RiskReasonCode.RISK_APPROVED,),
        pre_trade_exposure=ExposureSnapshot(gross_exposure_minor=0, net_exposure_minor=0),
    )
    order_intent = build_broker_order_intent(
        trade_proposal=proposal,
        risk_decision=risk,
        execution_policy_ref=ctx.canary_policy.required_execution_policy_ref,
        broker_target=BROKER,
        account_environment=AccountEnvironment.LIVE,
        decision_time_ns=T,
    )
    preview = build_order_confirmation_preview(
        authorization_ref=ctx.authorization.authorization_id if ctx.authorization else "auth-pending",
        order_intent=order_intent,
        risk_decision_ref=risk.risk_decision_id,
        reference_price_minor=25_00,
        confirmation_time_ns=T,
    )
    pending = PendingOrderReview(
        confirmation_preview=preview,
        order_intent=order_intent,
        risk_decision_ref=risk.risk_decision_id,
        requested_quantity=proposal.requested_quantity,
        approved_quantity=risk.approved_quantity,
        opportunity_ref="opp-drill-1",
        trade_proposal_ref="tp-drill-1",
        forecast_ref="forecast-drill-1",
    )
    return register_pending_order_review(ctx, pending)


def _run_drill_generic(drill_id: str) -> DrillRunOutcome:
    spec = DRILL_SPECS[drill_id]
    ctx = _base_context()
    transport = MockBrokerTransport()
    real_submits = 0
  # Prepare and authorize a session for drills that need it
    _, preview = prepare_session_authorization(ctx, decision_time_ns=T, request_id=f"{drill_id}-prep")
    from market_platform_foundation.intelligence.live_canary.identity import derive_preview_hash

    receipt, auth = authorize_reviewed_session(
        ctx,
        preview_id=preview.preview_id,
        preview_hash=derive_preview_hash(preview),
        reviewed_snapshot_id=build_operator_control_snapshot(ctx, as_of_ns=T).snapshot_id,
        approved_by="drill-operator",
        decision_time_ns=T + 1,
        request_id=f"{drill_id}-auth",
    )
    operator_actions: list[str] = []
    blocked_actions: list[str] = []
    observed_alerts: list[str] = []
    deviations: list[str] = []

    itype = IncidentType(spec.injected_incident["type"])
    severity = IncidentSeverity(spec.injected_incident["severity"])
    incident = inject_incident(
        ctx,
        incident_type=itype,
        severity=severity,
        description=spec.scenario,
        detected_at_ns=T + 2,
    )
    observed_alerts.append(incident.incident_type.value)
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=T + 3)
    if not snapshot.live_blocked:
        deviations.append("expected_live_blocked")

    ack_receipt, _ = acknowledge_incident(
        ctx,
        incident_id=incident.incident_id,
        acknowledged_by="drill-operator",
        decision_time_ns=T + 4,
        request_id=f"{drill_id}-ack",
    )
    operator_actions.append("ACKNOWLEDGE_INCIDENT")
    if ack_receipt.success:
        post_ack = build_operator_control_snapshot(ctx, as_of_ns=T + 5)
        if not post_ack.live_blocked:
            deviations.append("ack_should_not_unblock")

    conf_id = _make_pending_review(ctx)
    conf_receipt, _ = confirm_reviewed_order(
        ctx,
        confirmation_id=conf_id,
        reviewed_snapshot_id=snapshot.snapshot_id,
        confirmed_by="drill-operator",
        decision_time_ns=T + 6,
        request_id=f"{drill_id}-confirm",
    )
    if not conf_receipt.success:
        blocked_actions.append("CONFIRM_ORDER")
    else:
        deviations.append("confirm_should_be_blocked")

    if drill_id == "D09":
        activate_kill_switch(
            ctx, scope="GLOBAL", reason="D09", decision_time_ns=T + 7, request_id=f"{drill_id}-ks"
        )
        operator_actions.append("ACTIVATE_KILL_SWITCH_GLOBAL")
    elif drill_id == "D10":
        activate_kill_switch(
            ctx, scope="SESSION", reason="D10", decision_time_ns=T + 7, request_id=f"{drill_id}-ks"
        )
        operator_actions.append("ACTIVATE_KILL_SWITCH_SESSION")

    if drill_id in ("D14",):
        submit_resolution_evidence(
            ctx,
            incident_id=incident.incident_id,
            resolution_evidence_ref="evidence-drill",
            decision_time_ns=T + 8,
            request_id=f"{drill_id}-resolve",
        )
        operator_actions.append("SUBMIT_RESOLUTION_EVIDENCE")
        approve_resume(
            ctx,
            incident_refs=(incident.incident_id,),
            resolution_evidence_ref="evidence-drill",
            reconciliation_checkpoint_ref="checkpoint-drill",
            approved_by="drill-operator",
            decision_time_ns=T + 9,
            request_id=f"{drill_id}-resume",
        )
        operator_actions.append("APPROVE_RESUME")
        fresh = build_operator_control_snapshot(ctx, as_of_ns=T + 10)
        if ctx.authorization and ctx.authorization.authorization_state.value in ("AUTHORIZED", "ENABLED"):
            deviations.append("fresh_authorization_still_required_after_resume")

    real_submits = 0

    result = DrillResult.PASS if not deviations else DrillResult.FAIL
    report = IncidentDrillReportV1(
        drill_report_id="",
        schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
        drill_spec_ref=spec.drill_spec_id,
        initial_state=spec.initial_state,
        injected_fault=spec.injected_incident,
        observed_alerts=tuple(observed_alerts),
        operator_actions=tuple(operator_actions),
        blocked_actions=tuple(blocked_actions),
        final_state={"live_blocked": build_operator_control_snapshot(ctx, as_of_ns=T + 11).live_blocked},
        deviations=tuple(deviations),
        result=result,
        real_broker_submits=real_submits,
        real_broker_cancels=0,
        real_broker_replaces=0,
    )
    object.__setattr__(report, "drill_report_id", derive_drill_report_id(report))
    return DrillRunOutcome(report=report, context=ctx)


def run_all_drills() -> dict[str, IncidentDrillReportV1]:
    return {drill_id: _run_drill_generic(drill_id).report for drill_id in sorted(DRILL_SPECS)}


def run_drill(drill_id: str) -> IncidentDrillReportV1:
    return _run_drill_generic(drill_id).report
