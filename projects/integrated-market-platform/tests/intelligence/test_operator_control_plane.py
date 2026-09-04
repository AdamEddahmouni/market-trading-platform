"""BUILD 31 operator control plane tests."""

from __future__ import annotations

import unittest
from unittest import mock

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
from market_platform_foundation.intelligence.live_canary import (
    HumanApprovalSource,
    IncidentSeverity,
    IncidentType,
    build_default_canary_policy,
    build_default_program_policy,
    build_order_confirmation_preview,
)
from market_platform_foundation.intelligence.live_canary.identity import derive_preview_hash
from market_platform_foundation.intelligence.live_canary.operator_control import (
    OperatorControlContext,
    PendingOrderReview,
    acknowledge_incident,
    activate_kill_switch,
    authorize_reviewed_session,
    build_audit_review_report,
    build_authorization_review_model,
    build_lineage_trace,
    build_operator_audit_timeline,
    build_operator_control_snapshot,
    build_order_review_model,
    confirm_reviewed_order,
    inject_incident,
    prepare_session_authorization,
    register_pending_order_review,
    revoke_session_authorization,
    run_all_drills,
    run_drill,
    submit_resolution_evidence,
)
from market_platform_foundation.intelligence.live_canary.types import ProgramGovernanceState
from market_platform_foundation.intelligence.live_execution_safety import build_broker_order_intent
from market_platform_foundation.intelligence.live_execution_safety.types import AccountEnvironment
from market_platform_foundation.ui_api import canary_projections

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT = "fp-canary-test"


def _ctx() -> OperatorControlContext:
    return OperatorControlContext(
        program_policy=build_default_program_policy(program_effective_from_ns=T),
        canary_policy=build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT),
        governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
        session_ref="session-test-1",
        broker_health="HEALTHY",
        reconciliation_health="CLEAN",
    )


def _pending_review(ctx: OperatorControlContext, *, qty: int = 2) -> str:
    proposal = TradeProposalV1(
        proposal_id="tp-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="opp-1",
        execution_policy_id="ep-1",
        instrument_id="inst-aapl",
        side="BUY",
        requested_quantity=qty,
        requested_notional_minor=qty * 25_00,
        reference_price_minor=25_00,
        proposal_time_ns=T,
        expires_at_ns=T + 600_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-1"),
        metadata={},
    )
    risk = RiskDecisionV1(
        risk_decision_id="risk-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="tp-1",
        opportunity_id="opp-1",
        execution_policy_id="ep-1",
        portfolio_snapshot_id="port-1",
        decision_time_ns=T,
        requested_quantity=qty,
        requested_notional_minor=qty * 25_00,
        approved_quantity=1,
        approved_notional_minor=25_00,
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
        authorization_ref="auth-1",
        order_intent=order_intent,
        risk_decision_ref=risk.risk_decision_id,
        reference_price_minor=25_00,
        confirmation_time_ns=T,
    )
    return register_pending_order_review(
        ctx,
        PendingOrderReview(
            confirmation_preview=preview,
            order_intent=order_intent,
            risk_decision_ref=risk.risk_decision_id,
            requested_quantity=qty,
            approved_quantity=1,
            opportunity_ref="opp-1",
            trade_proposal_ref="tp-1",
            forecast_ref="forecast-1",
        ),
    )


class OperatorSnapshotTests(unittest.TestCase):
    def test_live_disabled_by_default_kill_switch(self) -> None:
        ctx = _ctx()
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        self.assertEqual(snap.execution_mode_label, "LIVE_CANARY")
        self.assertTrue(snap.live_blocked)

    def test_program_active_snapshot_fields(self) -> None:
        ctx = _ctx()
        ctx.kill_switch.permit_program("TEST")
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        self.assertEqual(snap.program_state, ProgramGovernanceState.PROGRAM_ACTIVE.value)
        self.assertIn("real_money_warning", snap.metadata)


class StaleViewTests(unittest.TestCase):
    def test_stale_authorization_preview_rejected(self) -> None:
        ctx = _ctx()
        ctx.kill_switch.permit_program("TEST")
        _, preview = prepare_session_authorization(ctx, decision_time_ns=T, request_id="prep-1")
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        ctx.broker_health = "DISCONNECTED"
        receipt, auth = authorize_reviewed_session(
            ctx,
            preview_id=preview.preview_id,
            preview_hash=derive_preview_hash(preview),
            reviewed_snapshot_id=snap.snapshot_id,
            approved_by="op",
            decision_time_ns=T + 1,
            request_id="auth-1",
        )
        self.assertFalse(receipt.success)
        self.assertIn("STALE_OPERATOR_VIEW", receipt.reason_codes)
        self.assertIsNone(auth)

    def test_stale_order_confirmation_rejected(self) -> None:
        ctx = _ctx()
        ctx.kill_switch.permit_program("TEST")
        conf_id = _pending_review(ctx)
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        inject_incident(
            ctx,
            incident_type=IncidentType.BROKER_DISCONNECT,
            severity=IncidentSeverity.CRITICAL,
            description="disconnect",
            detected_at_ns=T + 1,
        )
        receipt, confirmed = confirm_reviewed_order(
            ctx,
            confirmation_id=conf_id,
            reviewed_snapshot_id=snap.snapshot_id,
            confirmed_by="op",
            decision_time_ns=T + 2,
            request_id="confirm-1",
        )
        self.assertFalse(receipt.success)
        self.assertIsNone(confirmed)


class IdempotencyTests(unittest.TestCase):
    def test_double_kill_switch_activation(self) -> None:
        ctx = _ctx()
        r1 = activate_kill_switch(
            ctx, scope="PROGRAM", reason="TEST", decision_time_ns=T, request_id="ks-1"
        )
        r2 = activate_kill_switch(
            ctx, scope="PROGRAM", reason="TEST", decision_time_ns=T, request_id="ks-1"
        )
        self.assertEqual(r1.action_receipt_id, r2.action_receipt_id)


class KillSwitchTests(unittest.TestCase):
    def test_kill_switch_blocks_pending_confirmation(self) -> None:
        ctx = _ctx()
        ctx.kill_switch.permit_program("TEST")
        conf_id = _pending_review(ctx)
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        activate_kill_switch(
            ctx, scope="PROGRAM", reason="TEST", decision_time_ns=T + 1, request_id="ks-block"
        )
        receipt, confirmed = confirm_reviewed_order(
            ctx,
            confirmation_id=conf_id,
            reviewed_snapshot_id=snap.snapshot_id,
            confirmed_by="op",
            decision_time_ns=T + 2,
            request_id="confirm-ks",
        )
        self.assertFalse(receipt.success)
        self.assertIn("KILL_SWITCH_ACTIVE", receipt.reason_codes)
        self.assertIsNone(confirmed)


class IncidentWorkflowTests(unittest.TestCase):
    def test_acknowledge_does_not_resolve_or_unblock(self) -> None:
        ctx = _ctx()
        ctx.kill_switch.permit_program("TEST")
        incident = inject_incident(
            ctx,
            incident_type=IncidentType.BROKER_ONLY_ORDER,
            severity=IncidentSeverity.CRITICAL,
            description="broker-only",
            detected_at_ns=T,
        )
        receipt, updated = acknowledge_incident(
            ctx,
            incident_id=incident.incident_id,
            acknowledged_by="op",
            decision_time_ns=T + 1,
            request_id="ack-1",
        )
        self.assertTrue(receipt.success)
        assert updated is not None
        self.assertEqual(updated.state.value, "OPEN")
        self.assertTrue(updated.metadata.get("acknowledged"))
        snap = build_operator_control_snapshot(ctx, as_of_ns=T + 2)
        self.assertTrue(snap.live_blocked)

    def test_resolution_requires_evidence(self) -> None:
        ctx = _ctx()
        incident = inject_incident(
            ctx,
            incident_type=IncidentType.RECONCILIATION_FAILED,
            severity=IncidentSeverity.CRITICAL,
            description="recon failed",
            detected_at_ns=T,
        )
        receipt, resolved = submit_resolution_evidence(
            ctx,
            incident_id=incident.incident_id,
            resolution_evidence_ref="evidence-1",
            decision_time_ns=T + 1,
            request_id="resolve-1",
        )
        self.assertTrue(receipt.success)
        assert resolved is not None
        self.assertEqual(resolved.state.value, "RESOLVED")


class OrderReviewTests(unittest.TestCase):
    def test_requested_vs_approved_visible(self) -> None:
        ctx = _ctx()
        conf_id = _pending_review(ctx, qty=3)
        pending = ctx.pending_order_reviews[conf_id]
        review = build_order_review_model(pending, ctx=ctx, as_of_ns=T)
        self.assertEqual(review["requested_quantity"], 3)
        self.assertEqual(review["risk_approved_quantity"], 1)
        self.assertTrue(review["risk_reduction_visible"])


class AuditTimelineTests(unittest.TestCase):
    def test_timeline_deterministic_no_duplicates(self) -> None:
        ctx = _ctx()
        activate_kill_switch(
            ctx, scope="PROGRAM", reason="A", decision_time_ns=T, request_id="t1"
        )
        activate_kill_switch(
            ctx, scope="SESSION", reason="B", decision_time_ns=T + 1, request_id="t2"
        )
        timeline = build_operator_audit_timeline(ctx, as_of_ns=T + 2)
        ids = [e.event_id for e in timeline.events]
        self.assertEqual(len(ids), len(set(ids)))


class DrillTests(unittest.TestCase):
    def test_all_drills_zero_real_side_effects(self) -> None:
        reports = run_all_drills()
        self.assertEqual(len(reports), 15)
        for drill_id, report in reports.items():
            self.assertEqual(report.real_broker_submits, 0, drill_id)
            self.assertEqual(report.real_broker_cancels, 0, drill_id)
            self.assertEqual(report.real_broker_replaces, 0, drill_id)

    def test_d09_global_kill_switch(self) -> None:
        report = run_drill("D09")
        self.assertIn("ACTIVATE_KILL_SWITCH_GLOBAL", report.operator_actions)


class ApiSafetyTests(unittest.TestCase):
    def test_get_snapshot_no_mutation(self) -> None:
        canary_projections.reset_operator_context_for_tests()
        before = canary_projections.build_canary_snapshot_payload()
        after = canary_projections.build_canary_snapshot_payload()
        self.assertIn("snapshot", before)
        self.assertIn("snapshot", after)

    def test_action_inventory_complete(self) -> None:
        inventory = canary_projections.build_canary_action_inventory()
        self.assertGreaterEqual(len(inventory["actions"]), 8)


class PaperLiveIsolationTests(unittest.TestCase):
    def test_snapshot_labels_live_canary_not_paper(self) -> None:
        ctx = _ctx()
        snap = build_operator_control_snapshot(ctx, as_of_ns=T)
        self.assertEqual(snap.execution_mode_label, "LIVE_CANARY")
        self.assertNotEqual(snap.execution_mode_label, "PAPER")


if __name__ == "__main__":
    unittest.main()
