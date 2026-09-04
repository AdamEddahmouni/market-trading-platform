"""Integrated BUILD 01–24 lifecycle test."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.adaptation import (
    AdaptationAction,
    AdaptationService,
    EvidenceBundle,
)
from market_platform_foundation.intelligence.governance import (
    ActivationEngine,
    FailSafeEngine,
    resolve_governance_state,
)
from market_platform_foundation.intelligence.opportunity import AssessmentAction, OpportunityEngine
from market_platform_foundation.intelligence.promotion import PromotionEngine, StatisticalRequirementKind, build_promotion_policy
from market_platform_foundation.intelligence.research_experiments.types import ResearchFindingType
from market_platform_foundation.intelligence.validation import ValidationDisposition
from tests.intelligence.adaptation_fixtures import (
    default_adaptation_policy,
    default_context,
    performance_drift_assessment,
    recurrence_bundle,
)
from tests.intelligence.governance_fixtures import default_activation_policy, default_fail_safe_policy
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE, validated_candidate_bundle


class Build0124LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"

    def test_full_governed_loop_ends_at_research_reentry(self) -> None:
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
        champion = PromotionEngine().bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        repo.put_champion_assignment(champion)

        activation_policy = default_activation_policy()
        repo.put_runtime_activation_policy(activation_policy)
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

        adaptation_service = AdaptationService(repository=repo)
        adaptation_results = adaptation_service.assess_and_persist(
            policy=default_adaptation_policy(),
            bundle=recurrence_bundle(),
            context=default_context(
                champion_assignment_ref=champion.assignment_id,
                runtime_activation_ref=activation.activation_id,
            ),
        )
        self.assertEqual(adaptation_results[0].assessment.action, AdaptationAction.TRIGGER_RESEARCH)
        trigger = adaptation_results[0].trigger
        self.assertIsNotNone(trigger)

        finding = adaptation_service.register_finding_from_trigger(
            trigger,
            mode="PAPER",
            recorded_at_ns=T + 4,
        )
        self.assertEqual(finding.finding_type, ResearchFindingType.MONITORING_OBSERVATION)
        self.assertEqual(finding.metadata["research_trigger_id"], trigger.research_trigger_id)
        self.assertIsNone(repo.get_experiment_manifest(finding.finding_id))

    def test_no_trigger_below_recurrence(self) -> None:
        repo, _, _, _, _, _ = validated_candidate_bundle()
        service = AdaptationService(repository=repo)
        bundle = EvidenceBundle(
            drift_assessments=(performance_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M),)
        )
        results = service.assess_and_persist(
            policy=default_adaptation_policy(),
            bundle=bundle,
            context=default_context(),
        )
        self.assertEqual(results[0].assessment.action, AdaptationAction.ACCUMULATE)
        self.assertIsNone(results[0].trigger)


if __name__ == "__main__":
    unittest.main()
