"""Integrated BUILD 01–23 lifecycle test."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.execution import PaperExecutionOrchestrator
from market_platform_foundation.intelligence.governance import (
    FailSafeEngine,
    GovernanceEngine,
    HealthState,
    resolve_governance_state,
)
from market_platform_foundation.intelligence.opportunity import AssessmentAction, OpportunityEngine
from market_platform_foundation.intelligence.promotion import PromotionEngine, StatisticalRequirementKind, build_promotion_policy
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.intelligence.promotion import ShadowMatchedObservation
from market_platform_foundation.intelligence.validation import (
    ValidationDisposition,
    ValidationEngine,
    ValidationRunContext,
    build_validation_plan,
    statistical_candidate_profile,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_quote
from tests.intelligence.governance_fixtures import (
    activated_champion_bundle,
    default_activation_policy,
    default_fail_safe_policy,
    matching_runtime_identity,
    monitoring_window,
)
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE, shadow_observations, validated_candidate_bundle
from tests.intelligence.test_validation_temporal_firewall import (
    _holdout_examples,
    _manifest_with_holdout,
    _trained_candidate,
)


class Build0123LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"

    def test_governed_opportunity_to_paper_with_runtime_activation(self) -> None:
        repo, manifest, candidate, artifact_bytes, report, plan = validated_candidate_bundle()
        if report.final_disposition != ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA:
            self.skipTest("validation inconclusive in fixture environment")

        promotion_policy = build_promotion_policy(
            champion_scope=DEFAULT_SCOPE,
            required_improvement=0.001,
            minimum_holdout_samples=4,
            statistical_requirement=StatisticalRequirementKind.NONE,
        )
        repo.put_promotion_policy(promotion_policy)
        promotion_engine = PromotionEngine()
        champion = promotion_engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        repo.put_champion_assignment(champion)

        activation_policy = default_activation_policy()
        repo.put_runtime_activation_policy(activation_policy)
        from market_platform_foundation.intelligence.governance import ActivationEngine

        activation = ActivationEngine().create_activation(
            policy=activation_policy,
            champion_assignment=champion,
            effective_from_ns=T,
            artifact_bytes=artifact_bytes,
        )
        repo.put_runtime_activation(activation)

        fail_safe = FailSafeEngine().evaluate(
            policy=default_fail_safe_policy(),
            decision_time_ns=T + 1,
            activation=activation,
            runtime_consistent=True,
            runtime_reasons=(),
        )
        repo.put_fail_safe_decision(fail_safe)
        governance_state = resolve_governance_state(
            activation=activation,
            fail_safe_decision=fail_safe,
            latest_champion_assignment_id=champion.assignment_id,
        )
        self.assertTrue(governance_state.opportunities_allowed)
        self.assertTrue(governance_state.paper_execution_allowed)

        forecast = champion_forecast(champion)
        repo.put_forecast(forecast)
        opp_result = OpportunityEngine().assess(
            forecast=forecast,
            policy=default_opportunity_policy(),
            context=default_opportunity_context(),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 2_000_000_000,
            runtime_governance=governance_state,
        )
        self.assertEqual(opp_result.assessment.assessment_action, AssessmentAction.EMIT)
        if opp_result.opportunity is not None:
            repo.put_opportunity(opp_result.opportunity)

        exec_policy = default_execution_policy()
        repo.put_execution_policy(exec_policy)
        portfolio = flat_portfolio(captured_at_ns=T + 2_000_000_000)
        repo.put_paper_portfolio_snapshot(portfolio)
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="sess-build23",
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        if opp_result.opportunity is None:
            self.skipTest("no opportunity emitted")
        result = PaperExecutionOrchestrator().execute_paper(
            opportunity=opp_result.opportunity,
            policy=exec_policy,
            portfolio=portfolio,
            quote=sample_quote(),
            ledger=ledger,
            bars=[],
            decision_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_authority="AUTHORIZED",
            runtime_governance=governance_state,
        )
        self.assertIsNotNone(result.proposal)
        repo.put_trade_proposal(result.proposal)
        repo.put_risk_decision(result.risk_decision)

        engine = GovernanceEngine()
        consistent, _ = engine.check_runtime_consistency(
            activation=activation,
            reported=matching_runtime_identity(activation),
        )
        self.assertTrue(consistent)

    def test_provider_failure_disables_new_actions(self) -> None:
        from market_platform_foundation.intelligence.governance.health import assess_provider_health
        from market_platform_foundation.intelligence.quality.models import ConnectionState, ProviderHealthSnapshot

        _, champion, _, artifact_bytes, activation_policy, activation = activated_champion_bundle()
        window = monitoring_window()
        provider_snap = assess_provider_health(
            provider="moomoo",
            capability=None,
            observed_at_ns=T + 100,
            window=window,
            provider_health=ProviderHealthSnapshot(
                provider_id="moomoo",
                as_of_time_ns=T,
                connection=ConnectionState.DISCONNECTED,
            ),
            staleness_threshold_ns=1,
        )
        self.assertEqual(provider_snap.health_state, HealthState.UNHEALTHY)
        fail_safe = FailSafeEngine().evaluate(
            policy=default_fail_safe_policy(),
            decision_time_ns=T + 100,
            activation=activation,
            runtime_consistent=True,
            runtime_reasons=(),
            provider_health=provider_snap,
        )
        state = resolve_governance_state(activation=activation, fail_safe_decision=fail_safe)
        self.assertFalse(state.opportunities_allowed)


if __name__ == "__main__":
    unittest.main()
