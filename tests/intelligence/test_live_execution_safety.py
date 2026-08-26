"""BUILD 28 live execution safety gate tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.live_execution_safety import (
    BUILD28_KNOWN_LIMITATIONS,
    BROKER_INVENTORY,
    AccountEnvironment,
    BrokerCertificationDisposition,
    KillSwitchState,
    LiveAuthorizationState,
    LiveGateDecisionKind,
    LiveGateReasonCode,
    LiveSafetyDisposition,
    REQUIRED_SCENARIOS,
    ScenarioStatus,
    build_broker_order_intent,
    build_design_only_authorization,
    build_live_execution_safety_spec,
    build_production_kill_switch,
    build_test_inactive_kill_switch,
    certify_all_brokers,
    derive_client_order_id,
    derive_payload_hash,
    evaluate_live_execution_gate,
    inventory_by_broker,
    live_execution_safety_spec_v1_to_dict,
    production_authorization_absent,
    run_all_scenarios,
    run_live_execution_safety_certification,
    run_scenario,
    translate_broker_payload,
    validate_tick_lot,
    verify_build27_integrity,
    DryRunExecutionAdapter,
    ZeroSubmitGuard,
)
from market_platform_foundation.intelligence.execution.types import RiskDecisionKind, RiskDecisionV1, RiskReasonCode, ExposureSnapshot
from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.contracts.trade_proposal import TradeProposalV1
from market_platform_foundation.intelligence.contracts.common import ContractKind, ContractReference
from tests.intelligence.execution_fixtures import sample_opportunity

BUILD27_HEAD = "6f278aaf2f7d741d8669861b907b3a7fd3db4995"
BUILD26_HEAD = "8812720989244d08a436a73cc0a27595538c7f21"
BUILD25_HEAD = "15e7a4f6fc88e5a1c90c6bc3b1b4f8c3a861d2f2"
T = 1_700_000_000_000_000_000


class LiveExecutionSafetySpecTests(unittest.TestCase):
    def test_spec_identity_deterministic(self) -> None:
        s1 = build_live_execution_safety_spec(
            source_build27_ref=BUILD27_HEAD,
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD27_HEAD,
        )
        s2 = build_live_execution_safety_spec(
            source_build27_ref=BUILD27_HEAD,
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD27_HEAD,
        )
        self.assertEqual(s1.spec_id, s2.spec_id)
        self.assertTrue(s1.spec_id.startswith("LESSPEC-"))

    def test_spec_certification_mode_zero_submit(self) -> None:
        spec = build_live_execution_safety_spec(
            source_build27_ref=BUILD27_HEAD,
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD27_HEAD,
        )
        payload = live_execution_safety_spec_v1_to_dict(spec)
        self.assertEqual(payload["certification_mode"], "ZERO_SUBMIT")


class BrokerInventoryTests(unittest.TestCase):
    def test_inventory_covers_tradier_and_moomoo(self) -> None:
        brokers = {e.broker for e in BROKER_INVENTORY}
        self.assertIn("tradier.paper", brokers)
        self.assertIn("moomoo.paper", brokers)
        self.assertIn("ibkr.observational", brokers)

    def test_no_broker_live_certified(self) -> None:
        for entry in BROKER_INVENTORY:
            self.assertNotEqual(entry.current_status.value, "LIVE_CERTIFIED")


class AuthorizationTests(unittest.TestCase):
    def test_production_authorization_absent(self) -> None:
        self.assertIsNone(production_authorization_absent())

    def test_design_only_never_enabled(self) -> None:
        auth = build_design_only_authorization(
            broker="tradier.paper",
            account_ref="fp-test",
            effective_from_ns=T,
            effective_until_ns=T + 1,
        )
        self.assertIn(
            auth.authorization_state,
            {LiveAuthorizationState.DISABLED, LiveAuthorizationState.NOT_AUTHORIZED, LiveAuthorizationState.DESIGN_ONLY},
        )


class KillSwitchTests(unittest.TestCase):
    def test_production_kill_switch_active_block(self) -> None:
        ks = build_production_kill_switch(effective_from_ns=T)
        self.assertEqual(ks.state, KillSwitchState.ACTIVE_BLOCK)


class ClientOrderIdTests(unittest.TestCase):
    def test_deterministic_client_order_id(self) -> None:
        ids = {
            derive_client_order_id(
                risk_decision_id="risk-1",
                trade_proposal_id="prop-1",
                broker="tradier.paper",
                account_environment="SANDBOX",
            )
            for _ in range(50)
        }
        self.assertEqual(len(ids), 1)
        self.assertLessEqual(len(next(iter(ids))), 32)


class GateTests(unittest.TestCase):
    def test_kill_switch_blocks_even_with_test_auth(self) -> None:
        from market_platform_foundation.intelligence.live_execution_safety.authorization import (
            build_test_enabled_authorization_fixture,
        )
        from market_platform_foundation.intelligence.live_execution_safety.certification import certify_broker

        entry = inventory_by_broker("tradier.paper")
        assert entry is not None
        cert = certify_broker(entry)
        auth = build_test_enabled_authorization_fixture(
            broker="tradier.paper",
            account_ref="fp",
            effective_from_ns=T - 1,
            effective_until_ns=T + 1,
        )
        decision = evaluate_live_execution_gate(
            decision_time_ns=T,
            broker="tradier.paper",
            account_environment=AccountEnvironment.SANDBOX,
            runtime_activation_ref="rt",
            runtime_allows_live=True,
            authorization=auth,
            broker_certification=cert,
            opportunity=None,
            trade_proposal=None,
            risk_decision=None,
            order_intent=None,
            broker_health=None,
            reconciliation=None,
            kill_switch=build_production_kill_switch(effective_from_ns=T),
            production_config=True,
        )
        self.assertEqual(decision.decision, LiveGateDecisionKind.BLOCK)
        self.assertIn(LiveGateReasonCode.KILL_SWITCH_ACTIVE, decision.reason_codes)


class DryRunTransportTests(unittest.TestCase):
    def _intent(self):
        proposal = TradeProposalV1(
            proposal_id="tp-1",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            opportunity_id="opp-1",
            execution_policy_id="ep-1",
            instrument_id="inst-aapl",
            side="BUY",
            requested_quantity=10,
            requested_notional_minor=150_000,
            reference_price_minor=150_00,
            proposal_time_ns=T,
            expires_at_ns=T + 60_000_000_000,
            execution_mode="PAPER",
            opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-1"),
        )
        risk = RiskDecisionV1(
            risk_decision_id="risk-1",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            trade_proposal_id="tp-1",
            opportunity_id="opp-1",
            execution_policy_id="ep-1",
            portfolio_snapshot_id="port-1",
            decision_time_ns=T,
            requested_quantity=10,
            requested_notional_minor=150_000,
            approved_quantity=8,
            approved_notional_minor=120_000,
            decision=RiskDecisionKind.REDUCE,
            reason_codes=(RiskReasonCode.SIZE_REDUCED,),
            pre_trade_exposure=ExposureSnapshot(gross_exposure_minor=0, net_exposure_minor=0),
        )
        return build_broker_order_intent(
            trade_proposal=proposal,
            risk_decision=risk,
            execution_policy_ref="ep-1",
            broker_target="tradier.paper",
            account_environment=AccountEnvironment.SANDBOX,
            decision_time_ns=T,
        )

    def test_dry_run_never_submits(self) -> None:
        guard = ZeroSubmitGuard()
        adapter = DryRunExecutionAdapter(guard=guard)
        intent = self._intent()
        result = adapter.validate_and_record(intent, broker_symbol="AAPL", decision_time_ns=T)
        self.assertFalse(result.network_submit_performed)
        self.assertEqual(result.real_submit_count, 0)
        self.assertEqual(guard.real_submit_count, 0)

    def test_payload_hash_deterministic(self) -> None:
        intent = self._intent()
        _, h1 = translate_broker_payload(intent, broker_symbol="AAPL", decision_time_ns=T)
        _, h2 = translate_broker_payload(intent, broker_symbol="AAPL", decision_time_ns=T)
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("PAYLOAD-"))


class ScenarioTests(unittest.TestCase):
    def test_all_required_scenarios_pass(self) -> None:
        results = run_all_scenarios()
        failures = [r for r in results if r.status != ScenarioStatus.PASS]
        self.assertEqual(failures, [], msg=str(failures))

    def test_scenario_registry_complete(self) -> None:
        self.assertGreaterEqual(len(REQUIRED_SCENARIOS), 10)


class CertificationRunnerTests(unittest.TestCase):
    def test_full_certification_zero_submit(self) -> None:
        result = run_live_execution_safety_certification(
            source_build27_ref=BUILD27_HEAD,
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD27_HEAD,
        )
        self.assertEqual(result.real_submit_count, 0)
        self.assertEqual(result.real_cancel_count, 0)
        self.assertEqual(result.real_replace_count, 0)
        self.assertEqual(result.scenario_failures, ())
        self.assertIn(
            result.disposition,
            {
                LiveSafetyDisposition.PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS,
                LiveSafetyDisposition.PRELIVE_SAFETY_GATE_COMPLETE,
            },
        )
        self.assertEqual(result.metadata.get("live_authorization"), "NOT_AUTHORIZED")


class Build27IntegrityTests(unittest.TestCase):
    def test_build27_integrity_passes(self) -> None:
        result = verify_build27_integrity(expected_head=BUILD27_HEAD)
        self.assertEqual(result.status, "PASS")
        self.assertIn(
            result.disposition,
            {
                "PAPER_EXECUTION_QUALIFIED",
                "PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS",
                "INSUFFICIENT_PAPER_EXECUTION_EVIDENCE",
            },
        )


class TickLotTests(unittest.TestCase):
    def test_invalid_lot_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_tick_lot(quantity=3, limit_price_minor=100, lot_size=5)

    def test_invalid_tick_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_tick_lot(quantity=10, limit_price_minor=101, tick_size_minor=2)


class SecretSafetyTests(unittest.TestCase):
    def test_no_secrets_in_known_limitations(self) -> None:
        blob = " ".join(BUILD28_KNOWN_LIMITATIONS).lower()
        for token in ("password", "api_key", "secret", "token="):
            self.assertNotIn(token, blob)


class BrokerCertificationTests(unittest.TestCase):
    def test_certifications_zero_submit(self) -> None:
        certs = certify_all_brokers()
        self.assertGreater(len(certs), 0)
        for cert in certs:
            self.assertEqual(cert.certification_mode.value, "ZERO_SUBMIT")
            self.assertNotEqual(cert.disposition, BrokerCertificationDisposition.INVALID_EXECUTION_GATE)


if __name__ == "__main__":
    unittest.main()
