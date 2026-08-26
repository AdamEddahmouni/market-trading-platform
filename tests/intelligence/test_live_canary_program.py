"""BUILD 30 supervised live canary operations tests."""

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
    BUILD30_KNOWN_LIMITATIONS,
    HumanApprovalSource,
    IncidentSeverity,
    IncidentType,
    KillSwitchStore,
    LiveExecutionLedger,
    MockBrokerTransport,
    ProgramAccounting,
    ProgramDisposition,
    ProgramGovernanceState,
    SessionDisposition,
    authorize_canary_from_human_approval,
    build_default_canary_policy,
    build_default_program_policy,
    build_reconciliation_checkpoint,
    create_incident,
    evaluate_checkpoint_clean,
    evaluate_program_active,
    evaluate_session_end_gate,
    evaluate_session_start_gate,
    get_program_operational_status,
    incident_blocks_submits,
    prepare_canary_authorization_preview,
    record_human_canary_approval,
    record_resume_approval,
    resolve_incident,
    run_mock_incident_lifecycle,
    run_mock_program_lifecycle,
    validate_program_policy_constraints,
)
from market_platform_foundation.intelligence.live_execution_safety.types import KillSwitchState
from tests.intelligence.execution_fixtures import sample_opportunity

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT = "fp-canary-test"


def _proposal_and_risk(*, qty: int = 1, price: int = 25_00) -> tuple[TradeProposalV1, RiskDecisionV1]:
    proposal = TradeProposalV1(
        proposal_id="tp-program-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="opp-program-1",
        execution_policy_id="ep-1",
        instrument_id="inst-aapl",
        side="BUY",
        requested_quantity=qty,
        requested_notional_minor=qty * price,
        reference_price_minor=price,
        proposal_time_ns=T,
        expires_at_ns=T + 600_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-program-1"),
        metadata={"buying_power_minor": 1_000_000_00, "model_confidence": 0.99},
    )
    risk = RiskDecisionV1(
        risk_decision_id="risk-program-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="tp-program-1",
        opportunity_id="opp-program-1",
        execution_policy_id="ep-1",
        portfolio_snapshot_id="port-1",
        decision_time_ns=T,
        requested_quantity=qty,
        requested_notional_minor=qty * price,
        approved_quantity=qty,
        approved_notional_minor=qty * price,
        decision=RiskDecisionKind.APPROVE,
        reason_codes=(RiskReasonCode.RISK_APPROVED,),
        pre_trade_exposure=ExposureSnapshot(gross_exposure_minor=0, net_exposure_minor=0),
    )
    return proposal, risk


class ProgramPolicyTests(unittest.TestCase):
    def test_default_program_policy_caps(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        self.assertEqual(policy.max_sessions, 3)
        self.assertTrue(policy.require_fresh_authorization_per_session)
        self.assertTrue(policy.require_order_confirmation)
        self.assertTrue(policy.invalidate_confirmation_on_restart)
        self.assertEqual(validate_program_policy_constraints(policy), ())

    def test_program_policy_deterministic_id(self) -> None:
        p1 = build_default_program_policy(program_effective_from_ns=T)
        p2 = build_default_program_policy(program_effective_from_ns=T)
        self.assertEqual(p1.program_policy_id, p2.program_policy_id)


class ProgramCapTests(unittest.TestCase):
    def test_cumulative_caps_block_later_session(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        accounting.total_submit_attempts = policy.max_program_order_count
        exceeded, reason = accounting.program_cap_exceeded(policy)
        self.assertTrue(exceeded)
        self.assertEqual(reason, "ORDER_COUNT")

    def test_success_does_not_raise_caps(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        accounting.filled_notional_minor = policy.max_program_live_notional_minor - 1
        accounting.sessions_executed = 2
        self.assertEqual(policy.max_program_live_notional_minor, 75_00)
        self.assertEqual(policy.max_program_order_count, 3)


class AuthorizationIsolationTests(unittest.TestCase):
    def test_session_authorizations_are_distinct(self) -> None:
        canary = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview1 = prepare_canary_authorization_preview(
            policy=canary,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T,
        )
        approval1 = record_human_canary_approval(
            preview=preview1,
            approved_at_ns=T,
            approved_by="op",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        auth1 = authorize_canary_from_human_approval(
            policy=canary,
            preview=preview1,
            human_approval=approval1,
            effective_from_ns=T,
            effective_until_ns=T + 1_000_000_000,
        )
        preview2 = prepare_canary_authorization_preview(
            policy=canary,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T + 100,
        )
        approval2 = record_human_canary_approval(
            preview=preview2,
            approved_at_ns=T + 100,
            approved_by="op",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        auth2 = authorize_canary_from_human_approval(
            policy=canary,
            preview=preview2,
            human_approval=approval2,
            effective_from_ns=T + 100,
            effective_until_ns=T + 2_000_000_000,
        )
        self.assertNotEqual(auth1.authorization_id, auth2.authorization_id)

    def test_prior_authorization_blocks_reuse(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        canary = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview = prepare_canary_authorization_preview(
            policy=canary,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T,
        )
        approval = record_human_canary_approval(
            preview=preview,
            approved_at_ns=T,
            approved_by="op",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        auth = authorize_canary_from_human_approval(
            policy=canary,
            preview=preview,
            human_approval=approval,
            effective_from_ns=T,
            effective_until_ns=T + 1_000_000_000,
        )
        ledger = LiveExecutionLedger()
        checkpoint = build_reconciliation_checkpoint(
            as_of_ns=T, broker=BROKER, account_ref=ACCOUNT, ledger=ledger
        )
        kill = KillSwitchStore()
        kill.permit_program("ACTIVE")
        gate = evaluate_session_start_gate(
            policy=policy,
            accounting=accounting,
            decision_time_ns=T,
            kill_switch=kill,
            checkpoint=checkpoint,
            broker_healthy=True,
            account_matched=True,
            authorization=auth,
            prior_authorization_ref=auth.authorization_id,
            status_feed_as_of_ns=T,
        )
        self.assertFalse(gate.allowed)
        self.assertIn("SESSION_AUTHORIZATION_MISMATCH", gate.reason_codes)


class CooldownTests(unittest.TestCase):
    def test_cooldown_blocks_session_start(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        accounting.last_session_end_ns = T
        accounting.sessions_completed = 1
        kill = KillSwitchStore()
        kill.permit_program("ACTIVE")
        ledger = LiveExecutionLedger()
        checkpoint = build_reconciliation_checkpoint(
            as_of_ns=T + 1, broker=BROKER, account_ref=ACCOUNT, ledger=ledger
        )
        gate = evaluate_session_start_gate(
            policy=policy,
            accounting=accounting,
            decision_time_ns=T + 1,
            kill_switch=kill,
            checkpoint=checkpoint,
            broker_healthy=True,
            account_matched=True,
            authorization=None,
            status_feed_as_of_ns=T + 1,
        )
        self.assertFalse(gate.allowed)
        self.assertIn("PROGRAM_COOLDOWN_ACTIVE", gate.reason_codes)

    def test_cooldown_expiry_does_not_auto_start(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        accounting.last_session_end_ns = T
        accounting.sessions_completed = 1
        after_cooldown = T + policy.minimum_cooldown_between_sessions_ns + 1
        self.assertTrue(accounting.cooldown_satisfied(policy, after_cooldown))
        # Eligibility only — still requires fresh authorization
        gate = evaluate_program_active(
            policy=policy,
            accounting=accounting,
            decision_time_ns=after_cooldown,
            kill_switch=KillSwitchStore(),
        )
        self.assertFalse(gate.allowed)  # kill switch blocks by default


class ReconciliationCheckpointTests(unittest.TestCase):
    def test_clean_checkpoint_passes(self) -> None:
        ledger = LiveExecutionLedger()
        cp = build_reconciliation_checkpoint(
            as_of_ns=T, broker=BROKER, account_ref=ACCOUNT, ledger=ledger
        )
        result = evaluate_checkpoint_clean(cp)
        self.assertTrue(result.passed)

    def test_broker_only_order_fails(self) -> None:
        ledger = LiveExecutionLedger()
        cp = build_reconciliation_checkpoint(
            as_of_ns=T,
            broker=BROKER,
            account_ref=ACCOUNT,
            ledger=ledger,
            broker_open_orders=("EXTERNAL-ORDER",),
        )
        result = evaluate_checkpoint_clean(cp)
        self.assertFalse(result.passed)
        self.assertIn("BROKER_ONLY_ORDER", result.reason_codes)

    def test_session_end_requires_clean_checkpoint(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        ledger = LiveExecutionLedger()
        dirty = build_reconciliation_checkpoint(
            as_of_ns=T,
            broker=BROKER,
            account_ref=ACCOUNT,
            ledger=ledger,
            broker_open_orders=("UNKNOWN",),
        )
        gate = evaluate_session_end_gate(policy=policy, checkpoint=dirty)
        self.assertFalse(gate.allowed)


class IncidentTests(unittest.TestCase):
    def test_critical_incident_blocks_submits(self) -> None:
        incident = create_incident(
            incident_type=IncidentType.BROKER_ONLY_ORDER,
            severity=IncidentSeverity.CRITICAL,
            detected_at_ns=T,
            description="test",
        )
        self.assertTrue(incident_blocks_submits(incident))

    def test_incident_resolution_persists(self) -> None:
        incident = create_incident(
            incident_type=IncidentType.RECONCILIATION_FAILED,
            severity=IncidentSeverity.CRITICAL,
            detected_at_ns=T,
            description="test",
        )
        resolved = resolve_incident(
            incident,
            resolution_evidence_ref="EVID-1",
            resolved_at_ns=T + 1,
        )
        self.assertEqual(resolved.state.value, "RESOLVED")
        self.assertEqual(resolved.resolution_evidence_ref, "EVID-1")

    def test_manual_resume_required_after_critical(self) -> None:
        approval = record_resume_approval(
            incident_refs=("INC-1",),
            resolution_evidence_ref="EVID-1",
            reconciliation_checkpoint_ref="CP-1",
            program_run_ref="RUN-1",
            approved_at_ns=T,
            approved_by="operator",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        self.assertTrue(approval.resume_approval_id.startswith("RESUME-"))


class PartialFillRestartTests(unittest.TestCase):
    def test_partial_fill_restart_completes_exactly(self) -> None:
        transport = MockBrokerTransport()
        proposal, risk = _proposal_and_risk(qty=2, price=25_00)
        from market_platform_foundation.intelligence.live_execution_safety import (
            AccountEnvironment,
            build_broker_order_intent,
        )

        intent = build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        receipt = transport.submit(
            order_intent=intent,
            authorization_ref="auth-1",
            confirmation_ref="conf-1",
            submit_time_ns=T,
        )
        self.assertIsNotNone(receipt.broker_order_id)
        ledger = LiveExecutionLedger()
        ledger.record_submission(receipt)
        partial = transport.apply_partial_fill(
            broker_order_id=receipt.broker_order_id,
            quantity=1,
            price_minor=25_00,
            fill_time_ns=T + 1,
        )
        if partial:
            ledger.record_fill(partial)

        persisted_r = list(ledger.submission_receipts)
        persisted_f = list(ledger.fill_receipts)
        transport.restore_from_persistence(receipts=persisted_r, fills=persisted_f)
        ledger2 = LiveExecutionLedger()
        ledger2.restore_from_persistence(receipts=persisted_r, fills=persisted_f)

        remaining = transport.apply_partial_fill(
            broker_order_id=receipt.broker_order_id,
            quantity=1,
            price_minor=25_00,
            fill_time_ns=T + 2,
            fill_suffix="-final",
        )
        if remaining:
            ledger2.record_fill(remaining)

        total_qty = sum(f.quantity for f in ledger2.fill_receipts)
        self.assertEqual(total_qty, 2)
        fill_ids = [f.broker_fill_id for f in ledger2.fill_receipts]
        self.assertEqual(len(fill_ids), len(set(fill_ids)))


class DuplicateFillTests(unittest.TestCase):
    def test_duplicate_fill_deduplicates(self) -> None:
        ledger = LiveExecutionLedger()
        from market_platform_foundation.intelligence.live_canary.types import (
            BrokerSubmissionReceiptV1,
            LiveFillReceiptV1,
            SubmissionState,
        )

        receipt = BrokerSubmissionReceiptV1(
            submission_receipt_id="SUBREC-test",
            schema_version="1",
            order_intent_ref="intent-1",
            authorization_ref="auth-1",
            confirmation_ref="conf-1",
            client_order_id="cl-1",
            broker=BROKER,
            account_ref=ACCOUNT,
            submit_attempt_time_ns=T,
            payload_hash="h",
            transport_result="ACK",
            broker_order_id="BRK-1",
            ack_time_ns=T,
            raw_response_hash="r",
            submission_state=SubmissionState.ACKNOWLEDGED,
            metadata={"order_quantity": 1},
        )
        ledger.record_submission(receipt)
        fill = LiveFillReceiptV1(
            fill_receipt_id="FILLREC-1",
            schema_version="1",
            broker_order_id="BRK-1",
            client_order_id="cl-1",
            broker_fill_id="bf-1",
            fill_time_ns=T,
            quantity=1,
            price_minor=25_00,
            fees_minor=0,
            liquidity_metadata={},
            source="MOCK",
        )
        ledger.record_fill(fill)
        ledger.record_fill(fill)
        self.assertEqual(len(ledger.fill_receipts), 1)


class KillSwitchPersistenceTests(unittest.TestCase):
    def test_kill_switch_survives_restart(self) -> None:
        ks = KillSwitchStore()
        ks.activate_program_block("INCIDENT")
        restored = KillSwitchStore.from_persistence_dict(ks.to_persistence_dict())
        self.assertEqual(restored.program_state, KillSwitchState.ACTIVE_BLOCK)

    def test_unknown_state_defaults_block(self) -> None:
        ks = KillSwitchStore.from_persistence_dict({"bad": "data"})
        self.assertEqual(ks.global_state, KillSwitchState.ACTIVE_BLOCK)


class ProgramExpiryTests(unittest.TestCase):
    def test_expired_program_blocks(self) -> None:
        policy = build_default_program_policy(
            program_effective_from_ns=T,
            program_effective_until_ns=T + 1000,
        )
        accounting = ProgramAccounting()
        gate = evaluate_program_active(
            policy=policy,
            accounting=accounting,
            decision_time_ns=T + 2000,
            kill_switch=KillSwitchStore(),
        )
        self.assertFalse(gate.allowed)
        self.assertIn("PROGRAM_EXPIRED", gate.reason_codes)


class NoAdaptationTests(unittest.TestCase):
    def test_no_model_training_during_program(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.fusion.calibrators.CalibrationTrainer.fit"
        ) as fit_mock:
            proposal, risk = _proposal_and_risk()
            opp = sample_opportunity(opportunity_id="opp-program-1")
            run_mock_program_lifecycle(
                program_start_ns=T,
                trade_proposal=proposal,
                risk_decision=risk,
                opportunity=opp,
            )
            fit_mock.assert_not_called()


class FullProgramLifecycleTests(unittest.TestCase):
    def test_full_multi_session_mock_lifecycle(self) -> None:
        proposal, risk = _proposal_and_risk(qty=1, price=25_00)
        opp = sample_opportunity(opportunity_id="opp-program-1")
        result = run_mock_program_lifecycle(
            program_start_ns=T,
            trade_proposal=proposal,
            risk_decision=risk,
            opportunity=opp,
            reference_price_minor=25_00,
            session2_partial_qty=1,
            session2_total_qty=2,
        )
        self.assertEqual(result.governance_state, ProgramGovernanceState.PROGRAM_COMPLETE)
        self.assertEqual(len(result.session_results), 2)
        self.assertEqual(result.accounting.total_fills, 3)
        self.assertEqual(result.kill_switch.program_state, KillSwitchState.ACTIVE_BLOCK)
        auth_ids = [
            s.authorization_id for s in result.session_results if s.authorization_id
        ]
        self.assertEqual(len(auth_ids), len(set(auth_ids)))

    def test_incident_lifecycle_blocks_then_resolves(self) -> None:
        gate, incidents, ks = run_mock_incident_lifecycle(
            program_start_ns=T,
        )
        self.assertFalse(gate.allowed)
        self.assertEqual(ks.program_state, KillSwitchState.ACTIVE_BLOCK)
        self.assertEqual(incidents[1].state.value, "RESOLVED")


class ProgramStatusTests(unittest.TestCase):
    def test_operational_status_read_only(self) -> None:
        policy = build_default_program_policy(program_effective_from_ns=T)
        accounting = ProgramAccounting()
        status = get_program_operational_status(
            governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
            policy=policy,
            accounting=accounting,
            kill_switch=KillSwitchStore(),
            decision_time_ns=T,
        )
        self.assertEqual(status.program_state, "PROGRAM_ACTIVE")
        self.assertGreater(status.remaining_program_sessions, 0)


if __name__ == "__main__":
    unittest.main()
