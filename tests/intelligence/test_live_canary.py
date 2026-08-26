"""BUILD 29 limited live canary tests."""

from __future__ import annotations

import unittest

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
    BUILD29_KNOWN_LIMITATIONS,
    AuthorizationError,
    CanaryDisposition,
    HumanApprovalSource,
    LiveExecutionLedger,
    MockBrokerTransport,
    build_default_canary_policy,
    build_live_portfolio_snapshot,
    build_order_confirmation_preview,
    confirm_order,
    consume_authorization,
    derive_preview_hash,
    disable_authorization,
    effective_canary_quantity_cap,
    evaluate_canary_live_gate,
    evaluate_pre_canary_reconciliation,
    expire_authorization,
    is_authorization_submittable,
    prepare_canary_authorization_preview,
    record_human_canary_approval,
    authorize_canary_from_human_approval,
    run_mock_canary_lifecycle,
    validate_policy_constraints,
)
from market_platform_foundation.intelligence.live_execution_safety import (
    AccountEnvironment,
    KillSwitchState,
    LiveAuthorizationState,
    LiveGateDecisionKind,
    LiveGateReasonCode,
    build_broker_execution_health,
    build_broker_order_intent,
    build_production_kill_switch,
    build_reconciliation_snapshot,
    build_test_inactive_kill_switch,
    inventory_by_broker,
    certify_broker,
)
from market_platform_foundation.intelligence.live_canary.runner import build_canary_kill_switch_permit
from tests.intelligence.execution_fixtures import sample_opportunity

T = 1_700_000_000_000_000_000
BROKER = "tradier.paper"
ACCOUNT = "fp-canary-test"


def _proposal_and_risk(*, qty: int = 1, price: int = 100_00) -> tuple[TradeProposalV1, RiskDecisionV1]:
    proposal = TradeProposalV1(
        proposal_id="tp-canary-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="opp-canary-1",
        execution_policy_id="ep-1",
        instrument_id="inst-aapl",
        side="BUY",
        requested_quantity=qty,
        requested_notional_minor=qty * price,
        reference_price_minor=price,
        proposal_time_ns=T,
        expires_at_ns=T + 600_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-canary-1"),
        metadata={"buying_power_minor": 1_000_000_00, "model_confidence": 0.99},
    )
    risk = RiskDecisionV1(
        risk_decision_id="risk-canary-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="tp-canary-1",
        opportunity_id="opp-canary-1",
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


class LiveCanaryPolicyTests(unittest.TestCase):
    def test_default_policy_absolute_caps(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        self.assertEqual(policy.max_order_count, 1)
        self.assertFalse(policy.allow_margin)
        self.assertFalse(policy.allow_short)
        self.assertFalse(policy.allow_outside_rth)
        self.assertIn("US_EQUITY", policy.allowed_asset_classes)
        self.assertEqual(validate_policy_constraints(policy), ())

    def test_account_equity_cannot_increase_cap(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        cap = effective_canary_quantity_cap(
            policy=policy,
            risk_approved_quantity=100,
            reference_price_minor=100_00,
            account_buying_power_minor=10_000_000_00,
            model_confidence=0.99,
        )
        policy_cap = policy.max_single_order_notional_minor // 100_00
        self.assertEqual(cap, policy_cap)


class AuthorizationLifecycleTests(unittest.TestCase):
    def test_two_phase_authorization(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview = prepare_canary_authorization_preview(
            policy=policy,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T,
            known_limitations=BUILD29_KNOWN_LIMITATIONS,
        )
        self.assertTrue(preview.preview_id.startswith("CANPREV-"))
        approval = record_human_canary_approval(
            preview=preview,
            approved_at_ns=T + 1,
            approved_by="operator",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        auth = authorize_canary_from_human_approval(
            policy=policy,
            preview=preview,
            human_approval=approval,
            effective_from_ns=T,
            effective_until_ns=T + 3_600_000_000_000,
        )
        self.assertEqual(auth.authorization_state, LiveAuthorizationState.AUTHORIZED)

    def test_preview_mismatch_blocks_authorization(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview = prepare_canary_authorization_preview(
            policy=policy,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T,
        )
        bad_preview = prepare_canary_authorization_preview(
            policy=policy,
            broker=BROKER,
            account_ref=ACCOUNT,
            account_fingerprint="ACCTFP-test",
            generated_at_ns=T + 99,
        )
        approval = record_human_canary_approval(
            preview=preview,
            approved_at_ns=T,
            approved_by="op",
            approval_source=HumanApprovalSource.TEST_FIXTURE,
        )
        with self.assertRaises(AuthorizationError):
            authorize_canary_from_human_approval(
                policy=policy,
                preview=bad_preview,
                human_approval=approval,
                effective_from_ns=T,
                effective_until_ns=T + 1,
            )

    def test_authorization_expired_consumed_revoked(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview = prepare_canary_authorization_preview(
            policy=policy,
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
            policy=policy,
            preview=preview,
            human_approval=approval,
            effective_from_ns=T,
            effective_until_ns=T + 1000,
        )
        ok, reason = is_authorization_submittable(auth, decision_time_ns=T + 2000, orders_submitted=0)
        self.assertFalse(ok)
        self.assertEqual(reason, "EXPIRED")
        consumed = consume_authorization(auth)
        self.assertEqual(consumed.authorization_state, LiveAuthorizationState.CONSUMED)
        expired = expire_authorization(auth)
        self.assertEqual(expired.authorization_state, LiveAuthorizationState.EXPIRED)
        disabled = disable_authorization(auth)
        self.assertEqual(disabled.authorization_state, LiveAuthorizationState.DISABLED)


class OrderConfirmationTests(unittest.TestCase):
    def test_exact_confirmation_required(self) -> None:
        proposal, risk = _proposal_and_risk()
        intent = build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        preview = build_order_confirmation_preview(
            authorization_ref="auth-1",
            order_intent=intent,
            risk_decision_ref=risk.risk_decision_id,
            reference_price_minor=100_00,
            confirmation_time_ns=T,
        )
        confirmed = confirm_order(
            preview,
            confirmed_by="operator",
            confirmation_source=HumanApprovalSource.TEST_FIXTURE,
            confirmation_time_ns=T,
        )
        from market_platform_foundation.intelligence.live_canary.confirmation import validate_confirmation_for_intent

        ok, _ = validate_confirmation_for_intent(
            confirmed,
            order_intent=intent,
            authorization_ref="auth-1",
            decision_time_ns=T + 1,
        )
        self.assertTrue(ok)

    def test_quantity_change_invalidates_confirmation(self) -> None:
        proposal, risk = _proposal_and_risk(qty=1)
        intent = build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        preview = build_order_confirmation_preview(
            authorization_ref="auth-1",
            order_intent=intent,
            risk_decision_ref=risk.risk_decision_id,
            reference_price_minor=100_00,
            confirmation_time_ns=T,
        )
        confirmed = confirm_order(
            preview,
            confirmed_by="operator",
            confirmation_source=HumanApprovalSource.TEST_FIXTURE,
            confirmation_time_ns=T,
        )
        proposal2, risk2 = _proposal_and_risk(qty=2)
        intent2 = build_broker_order_intent(
            trade_proposal=proposal2,
            risk_decision=risk2,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        from market_platform_foundation.intelligence.live_canary.confirmation import validate_confirmation_for_intent

        ok, reason = validate_confirmation_for_intent(
            confirmed,
            order_intent=intent2,
            authorization_ref="auth-1",
            decision_time_ns=T + 1,
        )
        self.assertFalse(ok)
        self.assertIn(reason, ("QUANTITY_CHANGED", "INTENT_MISMATCH"))


class PreCanaryReconciliationTests(unittest.TestCase):
    def test_flat_clean_account_passes(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        portfolio = build_live_portfolio_snapshot(
            as_of_ns=T, broker=BROKER, account_ref=ACCOUNT, cash_minor=10_000_00
        )
        result = evaluate_pre_canary_reconciliation(
            policy=policy,
            account_ref=ACCOUNT,
            account_environment=AccountEnvironment.LIVE,
            broker_healthy=True,
            as_of_ns=T,
            portfolio=portfolio,
        )
        self.assertTrue(result.passed)

    def test_unexpected_position_blocks(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        portfolio = build_live_portfolio_snapshot(
            as_of_ns=T,
            broker=BROKER,
            account_ref=ACCOUNT,
            cash_minor=10_000_00,
            positions=({"instrument_id": "inst-aapl", "quantity": 5, "price_minor": 100_00},),
        )
        result = evaluate_pre_canary_reconciliation(
            policy=policy,
            account_ref=ACCOUNT,
            account_environment=AccountEnvironment.LIVE,
            broker_healthy=True,
            as_of_ns=T,
            portfolio=portfolio,
        )
        self.assertFalse(result.passed)
        self.assertIn("FLAT_START_VIOLATION", result.reason_codes)

    def test_wrong_account_blocks(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        portfolio = build_live_portfolio_snapshot(
            as_of_ns=T, broker=BROKER, account_ref="wrong", cash_minor=10_000_00
        )
        result = evaluate_pre_canary_reconciliation(
            policy=policy,
            account_ref="wrong",
            account_environment=AccountEnvironment.LIVE,
            broker_healthy=True,
            as_of_ns=T,
            portfolio=portfolio,
        )
        self.assertFalse(result.passed)
        self.assertIn("ACCOUNT_MISMATCH", result.reason_codes)


class CanaryGateTests(unittest.TestCase):
    def _authorized_auth(self):
        policy = build_default_canary_policy(broker=BROKER, account_ref=ACCOUNT)
        preview = prepare_canary_authorization_preview(
            policy=policy,
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
        return policy, authorize_canary_from_human_approval(
            policy=policy,
            preview=preview,
            human_approval=approval,
            effective_from_ns=T,
            effective_until_ns=T + 3_600_000_000_000,
        )

    def test_missing_confirmation_blocks(self) -> None:
        policy, auth = self._authorized_auth()
        proposal, risk = _proposal_and_risk(qty=1, price=20_00)
        opp = sample_opportunity(opportunity_id="opp-canary-1")
        intent = build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        cert = certify_broker(inventory_by_broker(BROKER))
        decision = evaluate_canary_live_gate(
            decision_time_ns=T,
            policy=policy,
            broker=BROKER,
            account_environment=AccountEnvironment.LIVE,
            account_ref=ACCOUNT,
            runtime_activation_ref="rt",
            runtime_allows_live=True,
            authorization=auth,
            broker_certification=cert,
            opportunity=opp,
            trade_proposal=proposal,
            risk_decision=risk,
            order_intent=intent,
            order_confirmation=None,
            broker_health=build_broker_execution_health(
                broker=BROKER, account_environment=AccountEnvironment.LIVE, as_of_ns=T
            ),
            reconciliation=build_reconciliation_snapshot(
                broker=BROKER,
                account_environment=AccountEnvironment.LIVE,
                as_of_ns=T,
                local_open_intents=(),
                broker_open_orders=(),
            ),
            kill_switch=build_production_kill_switch(effective_from_ns=T),
            canary_kill_switch=build_canary_kill_switch_permit(effective_from_ns=T),
            allow_live_submit_in_test=True,
        )
        self.assertEqual(decision.decision, LiveGateDecisionKind.BLOCK)
        self.assertIn(LiveGateReasonCode.CANARY_ORDER_CONFIRMATION_MISSING, decision.reason_codes)


class SubmissionTests(unittest.TestCase):
    def test_ambiguous_submit_blocks_resubmit(self) -> None:
        proposal, risk = _proposal_and_risk()
        intent = build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target=BROKER,
            account_environment=AccountEnvironment.LIVE,
            decision_time_ns=T,
        )
        transport = MockBrokerTransport(simulate_ambiguous=True)
        receipt = transport.submit(
            order_intent=intent,
            authorization_ref="auth-1",
            confirmation_ref="conf-1",
            submit_time_ns=T,
        )
        self.assertEqual(receipt.submission_state.value, "SUBMISSION_STATUS_UNKNOWN")
        self.assertTrue(transport.resubmit_blocked(intent.client_order_id))

    def test_unexpected_fill_raises(self) -> None:
        ledger = LiveExecutionLedger()
        from market_platform_foundation.intelligence.live_canary.types import LiveFillReceiptV1

        fill = LiveFillReceiptV1(
            fill_receipt_id="FILLREC-test",
            schema_version="1",
            broker_order_id="unknown",
            client_order_id="cl-1",
            broker_fill_id="bf-1",
            fill_time_ns=T,
            quantity=1,
            price_minor=100_00,
            fees_minor=0,
            liquidity_metadata={},
            source="MOCK",
        )
        with self.assertRaises(ValueError):
            ledger.record_fill(fill)


class MockCanaryLifecycleTests(unittest.TestCase):
    def test_full_mock_lifecycle(self) -> None:
        proposal, risk = _proposal_and_risk(qty=1, price=20_00)
        opp = sample_opportunity(opportunity_id="opp-canary-1")
        result = run_mock_canary_lifecycle(
            broker=BROKER,
            account_ref=ACCOUNT,
            decision_time_ns=T,
            opportunity=opp,
            trade_proposal=proposal,
            risk_decision=risk,
            reference_price_minor=20_00,
        )
        self.assertTrue(result.gate_allowed)
        self.assertEqual(result.disposition, CanaryDisposition.CANARY_EXECUTED_CLEAN)
        self.assertEqual(result.authorization_state, LiveAuthorizationState.DISABLED)
        self.assertEqual(result.ledger.orders_submitted, 1)
        self.assertEqual(len(result.ledger.fill_receipts), 1)

    def test_auto_disable_after_canary(self) -> None:
        proposal, risk = _proposal_and_risk(qty=1, price=20_00)
        opp = sample_opportunity(opportunity_id="opp-canary-1")
        result = run_mock_canary_lifecycle(
            broker=BROKER,
            account_ref=ACCOUNT,
            decision_time_ns=T,
            opportunity=opp,
            trade_proposal=proposal,
            risk_decision=risk,
            reference_price_minor=20_00,
        )
        self.assertEqual(result.authorization_state, LiveAuthorizationState.DISABLED)


class SecretRedactionTests(unittest.TestCase):
    def test_preview_uses_fingerprint_not_full_account(self) -> None:
        policy = build_default_canary_policy(broker=BROKER, account_ref="1234567890123456")
        from market_platform_foundation.intelligence.live_canary.identity import derive_account_fingerprint

        fp = derive_account_fingerprint("1234567890123456")
        preview = prepare_canary_authorization_preview(
            policy=policy,
            broker=BROKER,
            account_ref="1234567890123456",
            account_fingerprint=fp,
            generated_at_ns=T,
        )
        self.assertNotIn("1234567890123456", preview.account_fingerprint)
        self.assertTrue(preview.account_fingerprint.startswith("ACCTFP-"))


if __name__ == "__main__":
    unittest.main()
