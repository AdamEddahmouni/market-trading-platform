"""BUILD 33 supervised production pilot tests."""

from __future__ import annotations

import unittest
from unittest import mock

from market_platform_foundation.intelligence.live_canary import (
    build_default_canary_policy,
    build_default_program_policy,
)
from market_platform_foundation.intelligence.live_canary.kill_switch_store import KillSwitchStore
from market_platform_foundation.intelligence.live_canary.operator_control import OperatorControlContext
from market_platform_foundation.intelligence.live_canary.program_accounting import ProgramAccounting
from market_platform_foundation.intelligence.live_canary.supervised_production_pilot import (
    PilotAccounting,
    PilotGovernanceState,
    ProviderDivergenceStatus,
    ProviderSelectionTracker,
    assess_provider_divergence,
    broker_auto_failover_prohibited,
    build_broker_redundancy_assessment,
    build_default_pilot_policy,
    build_default_pilot_qualification_spec,
    build_default_provider_redundancy_policy,
    build_operational_pilot_checkpoint,
    build_pilot_operational_review,
    build_runbook_exercise_spec,
    build_sustained_pilot_qualification_report,
    can_transition_pilot_state,
    critical_divergence_blocks_opportunity,
    derive_pilot_policy_id,
    evaluate_pilot_active,
    evaluate_pilot_session_gate,
    execute_planned_maintenance,
    missed_checkpoint_detected,
    pilot_expired_blocks_session,
    pilot_policy_authorizes_order,
    pilot_ready_implies_trading_authority,
    pit_safe_candidate,
    review_disposition_authorizes_trading,
    run_all_runbook_exercises,
    run_ambiguous_broker_safety_fixture,
    run_maintenance_fixture,
    run_multi_provider_pilot_fixture,
    run_operational_incident_fixture,
    run_runbook_exercise,
    transition_pilot_state,
    validate_pilot_policy_constraints,
)
from market_platform_foundation.intelligence.live_canary.supervised_production_pilot.provider_selection import (
    ProviderCandidateHealthV1,
)
from market_platform_foundation.intelligence.live_canary.types import ProgramGovernanceState
from market_platform_foundation.ui_api import canary_projections

T = 1_700_000_000_000_000_000
BUILD32_REF = "ce49004c1388afc4895dd6d595ccb1b063757441"


def _ctx() -> OperatorControlContext:
    ctx = OperatorControlContext(
        program_policy=build_default_program_policy(program_effective_from_ns=T),
        canary_policy=build_default_canary_policy(broker="tradier.paper", account_ref="fp-pilot"),
        governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
        session_ref="session-pilot-1",
        broker_health="HEALTHY",
        reconciliation_health="CLEAN",
    )
    ctx.kill_switch.permit_program("PILOT_TEST")
    return ctx


class PilotPolicyTests(unittest.TestCase):
    def test_deterministic_policy_id(self) -> None:
        p1 = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        p2 = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        self.assertEqual(p1.pilot_policy_id, p2.pilot_policy_id)

    def test_human_controls_required(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        self.assertTrue(policy.human_session_authorization_required)
        self.assertTrue(policy.human_order_confirmation_required)
        self.assertTrue(policy.manual_resume_required)

    def test_pilot_caps(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        self.assertGreater(policy.max_pilot_sessions, 0)
        self.assertGreater(policy.max_pilot_orders, 0)


class PilotStateTests(unittest.TestCase):
    def test_valid_transitions(self) -> None:
        self.assertTrue(
            can_transition_pilot_state(PilotGovernanceState.PILOT_PREPARED, PilotGovernanceState.PILOT_READY)
        )
        state = transition_pilot_state(PilotGovernanceState.PILOT_PREPARED, PilotGovernanceState.PILOT_READY)
        self.assertEqual(state, PilotGovernanceState.PILOT_READY)

    def test_ready_not_trading_authority(self) -> None:
        self.assertFalse(pilot_ready_implies_trading_authority(PilotGovernanceState.PILOT_READY))

    def test_invalid_transition_raises(self) -> None:
        with self.assertRaises(ValueError):
            transition_pilot_state(PilotGovernanceState.PILOT_COMPLETE, PilotGovernanceState.PILOT_ACTIVE)


class ProviderRedundancyTests(unittest.TestCase):
    def test_deterministic_redundancy_policy_id(self) -> None:
        p1 = build_default_provider_redundancy_policy()
        p2 = build_default_provider_redundancy_policy()
        self.assertEqual(p1.provider_redundancy_policy_id, p2.provider_redundancy_policy_id)

    def test_primary_healthy_selection(self) -> None:
        policy = build_default_provider_redundancy_policy()
        tracker = ProviderSelectionTracker()
        candidates = (
            ProviderCandidateHealthV1("polygon", "HEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "HEALTHY", 1_000_000_000, T, T),
        )
        decision = tracker.select_provider(policy=policy, candidates=candidates, decision_time_ns=T)
        self.assertEqual(decision.selected_provider, "polygon")

    def test_transient_failure_no_switch(self) -> None:
        policy = build_default_provider_redundancy_policy()
        tracker = ProviderSelectionTracker(current_provider="polygon")
        candidates = (
            ProviderCandidateHealthV1("polygon", "UNHEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "HEALTHY", 1_000_000_000, T, T),
        )
        decision = tracker.select_provider(
            policy=policy, candidates=candidates, decision_time_ns=T + 5_000_000_000
        )
        self.assertEqual(decision.selected_provider, "polygon")

    def test_sustained_failure_failover(self) -> None:
        policy = build_default_provider_redundancy_policy()
        tracker = ProviderSelectionTracker(current_provider="polygon")
        tracker.primary_unhealthy_since_ns = T
        candidates = (
            ProviderCandidateHealthV1("polygon", "UNHEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "HEALTHY", 1_000_000_000, T, T),
        )
        decision = tracker.select_provider(
            policy=policy,
            candidates=candidates,
            decision_time_ns=T + policy.minimum_failure_duration_ns + 1,
        )
        self.assertEqual(decision.selected_provider, "finviz")

    def test_stale_fallback_rejected(self) -> None:
        policy = build_default_provider_redundancy_policy()
        tracker = ProviderSelectionTracker(current_provider="polygon")
        tracker.primary_unhealthy_since_ns = T
        candidates = (
            ProviderCandidateHealthV1("polygon", "UNHEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "HEALTHY", 999_999_999_999, T, T),
        )
        decision = tracker.select_provider(
            policy=policy,
            candidates=candidates,
            decision_time_ns=T + policy.minimum_failure_duration_ns + 1,
        )
        self.assertIsNone(decision.selected_provider)

    def test_both_unhealthy(self) -> None:
        policy = build_default_provider_redundancy_policy()
        tracker = ProviderSelectionTracker()
        tracker.primary_unhealthy_since_ns = T
        candidates = (
            ProviderCandidateHealthV1("polygon", "UNHEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "UNHEALTHY", 1_000_000_000, T, T),
        )
        decision = tracker.select_provider(
            policy=policy,
            candidates=candidates,
            decision_time_ns=T + policy.minimum_failure_duration_ns + 1,
        )
        self.assertIsNone(decision.selected_provider)

    def test_input_order_independence(self) -> None:
        policy = build_default_provider_redundancy_policy()
        c1 = (
            ProviderCandidateHealthV1("polygon", "HEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("finviz", "HEALTHY", 1_000_000_000, T, T),
        )
        c2 = (
            ProviderCandidateHealthV1("finviz", "HEALTHY", 1_000_000_000, T, T),
            ProviderCandidateHealthV1("polygon", "HEALTHY", 1_000_000_000, T, T),
        )
        d1 = ProviderSelectionTracker().select_provider(policy=policy, candidates=c1, decision_time_ns=T)
        d2 = ProviderSelectionTracker().select_provider(policy=policy, candidates=c2, decision_time_ns=T)
        self.assertEqual(d1.selected_provider, d2.selected_provider)


class ProviderDivergenceTests(unittest.TestCase):
    def test_normal_divergence(self) -> None:
        policy = build_default_provider_redundancy_policy()
        assessment = assess_provider_divergence(
            policy=policy,
            as_of_ns=T,
            instrument="AAPL",
            provider_a="polygon",
            provider_b="finviz",
            provider_a_value=100.0,
            provider_b_value=100.01,
        )
        self.assertEqual(assessment.status, ProviderDivergenceStatus.NORMAL.value)

    def test_critical_divergence_blocks(self) -> None:
        policy = build_default_provider_redundancy_policy()
        assessment = assess_provider_divergence(
            policy=policy,
            as_of_ns=T,
            instrument="AAPL",
            provider_a="polygon",
            provider_b="finviz",
            provider_a_value=100.0,
            provider_b_value=105.0,
        )
        self.assertTrue(critical_divergence_blocks_opportunity(assessment))


class BrokerFailoverTests(unittest.TestCase):
    def test_auto_failover_not_authorized(self) -> None:
        assessment = build_broker_redundancy_assessment()
        self.assertEqual(assessment.auto_failover_authorization, "NOT_AUTHORIZED")

    def test_ambiguous_broker_no_alternate_submit(self) -> None:
        self.assertEqual(run_ambiguous_broker_safety_fixture(), 0)
        blocked, reasons = broker_auto_failover_prohibited(
            primary_broker="tradier.paper",
            alternate_broker="ibkr.paper",
            ambiguous_submission=True,
        )
        self.assertTrue(blocked)
        self.assertIn("AUTO_BROKER_FAILOVER_NOT_AUTHORIZED", reasons)


class PilotCapTests(unittest.TestCase):
    def test_cumulative_cap_blocks(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        accounting = PilotAccounting()
        for _ in range(policy.max_pilot_sessions):
            accounting.record_session()
        exceeded, reason = accounting.pilot_cap_exceeded(policy)
        self.assertTrue(exceeded)
        self.assertEqual(reason, "PILOT_SESSION_LIMIT")

    def test_counters_cannot_reset(self) -> None:
        accounting = PilotAccounting()
        accounting.record_order(notional_minor=100)
        accounting.freeze_counters()
        with self.assertRaises(RuntimeError):
            accounting.record_order(notional_minor=100)


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_fields(self) -> None:
        cp = build_operational_pilot_checkpoint(
            pilot_run_ref="run-1",
            as_of_ns=T,
            pilot_state="PILOT_ACTIVE",
            provider_health_summary={"polygon": "HEALTHY"},
            selected_provider_state={"quotes": "polygon"},
            divergence_state="NORMAL",
            broker_health="HEALTHY",
            reconciliation_health="CLEAN",
        )
        self.assertTrue(cp.checkpoint_id.startswith("PILCHK-"))

    def test_missed_checkpoint(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        missed, reasons = missed_checkpoint_detected(
            policy=policy,
            last_checkpoint_ns=T,
            as_of_ns=T + policy.required_operational_checkpoint_interval_ns * 3,
            evaluator_ok=True,
        )
        self.assertTrue(missed)
        self.assertIn("CHECKPOINT_MISSED", reasons)


class RunbookTests(unittest.TestCase):
    def test_all_runbooks_exercised(self) -> None:
        reports = run_all_runbook_exercises()
        self.assertEqual(len(reports), 20)
        for rb_id, report in reports.items():
            self.assertEqual(report.result, "PASS", msg=rb_id)
            self.assertEqual(report.real_broker_submits, 0)

    def test_unsafe_actions_blocked(self) -> None:
        spec = build_runbook_exercise_spec("RB05")
        report = run_runbook_exercise(spec, attempted_unsafe=("switch_broker_and_resend",))
        self.assertEqual(report.unsafe_actions_blocked, ("switch_broker_and_resend",))


class MaintenanceTests(unittest.TestCase):
    def test_no_auto_resume(self) -> None:
        result = execute_planned_maintenance()
        self.assertFalse(result.auto_resume)
        self.assertFalse(result.auto_submit)

    def test_maintenance_fixture(self) -> None:
        fixture = run_maintenance_fixture()
        self.assertFalse(fixture["auto_resume"])
        self.assertFalse(fixture["auto_submit"])


class PilotGateTests(unittest.TestCase):
    def test_pilot_expiry_blocks(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        blocked, reasons = pilot_expired_blocks_session(
            policy=policy, decision_time_ns=policy.pilot_end_ns + 1
        )
        self.assertTrue(blocked)
        self.assertIn("PILOT_EXPIRED", reasons)

    def test_pilot_policy_does_not_authorize_order(self) -> None:
        self.assertFalse(pilot_policy_authorizes_order())

    def test_review_does_not_authorize(self) -> None:
        self.assertFalse(review_disposition_authorizes_trading("CONTINUE_PILOT"))


class NoAutonomyTests(unittest.TestCase):
    def test_pilot_gate_requires_authorization(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        program = build_default_program_policy(program_effective_from_ns=T)
        gate = evaluate_pilot_session_gate(
            pilot_policy=policy,
            program_policy=program,
            pilot_accounting=PilotAccounting(),
            program_accounting=ProgramAccounting(),
            decision_time_ns=T + 1,
            kill_switch=KillSwitchStore(),
            checkpoint=None,
            broker_healthy=True,
            account_matched=True,
            authorization=None,
        )
        self.assertFalse(gate.allowed)


class NoAdaptationTests(unittest.TestCase):
    def test_no_training_calls(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.live_canary.supervised_production_pilot.runner.transition_pilot_state",
            wraps=transition_pilot_state,
        ) as _wrapped:
            run_multi_provider_pilot_fixture()
        for forbidden in ("partial_fit", "fit", "promote", "train"):
            self.assertNotIn(forbidden, str(_wrapped.call_args_list))


class FullFixtureTests(unittest.TestCase):
    def test_multi_provider_fixture(self) -> None:
        result = run_multi_provider_pilot_fixture()
        self.assertGreaterEqual(len(result.checkpoints), 1)

    def test_operational_incident_fixture(self) -> None:
        result = run_operational_incident_fixture()
        self.assertTrue(result["new_submits_blocked"])
        self.assertTrue(result["fresh_authorization_still_required"])

    def test_qualification_report(self) -> None:
        policy = build_default_pilot_policy(source_build32_ref=BUILD32_REF, pilot_start_ns=T)
        spec = build_default_pilot_qualification_spec(pilot_policy_ref=policy.pilot_policy_id)
        report = build_sustained_pilot_qualification_report(
            qualification_spec=spec,
            pilot_run_ref="run-test",
            build33_source_ref="abc123",
            actual_observation_duration_ns=90 * 60 * 1_000_000_000,
        )
        self.assertEqual(len(report.runbook_exercise_results), 20)
        self.assertEqual(report.real_broker_side_effects_observed, 0)


class PITTests(unittest.TestCase):
    def test_pit_safe(self) -> None:
        c = ProviderCandidateHealthV1("polygon", "HEALTHY", 1_000, T, T)
        self.assertTrue(pit_safe_candidate(c, decision_time_ns=T + 1))

    def test_pit_violation(self) -> None:
        c = ProviderCandidateHealthV1("polygon", "HEALTHY", 1_000, T, T + 100)
        self.assertFalse(pit_safe_candidate(c, decision_time_ns=T))


class UIProjectionTests(unittest.TestCase):
    def test_pilot_payload(self) -> None:
        canary_projections.reset_operator_context_for_tests()
        payload = canary_projections.build_canary_pilot_payload()
        self.assertEqual(payload["authority_boundary"], "SUPERVISED_PRODUCTION_PILOT_READ_ONLY")
        self.assertTrue(payload["human_session_authorization_required"])
        self.assertEqual(payload["auto_broker_failover"], "NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
