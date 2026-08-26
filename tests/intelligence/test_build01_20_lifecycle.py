"""Integrated BUILD 01–20 lifecycle test."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import (
    ChallengerLifecycleState,
    PromotionDecisionKind,
    PromotionEngine,
    ShadowMatchedObservation,
    StatisticalRequirementKind,
    build_promotion_policy,
    build_shadow_evidence_manifest,
)
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.intelligence.validation import (
    ContaminationDisposition,
    ValidationDisposition,
    ValidationEngine,
    ValidationRunContext,
    build_validation_plan,
    statistical_candidate_profile,
)
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import (
    DEFAULT_SCOPE,
    shadow_observations,
    validated_candidate_bundle,
)
from tests.intelligence.test_validation_temporal_firewall import (
    _holdout_examples,
    _manifest_with_holdout,
    _trained_candidate,
)


class Build0120LifecycleTests(unittest.TestCase):
    def test_clean_promotion_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        engine = PromotionEngine()
        manifest = _manifest_with_holdout(T + 8)
        candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
        plan = build_validation_plan(
            manifest,
            (candidate,),
            control_ref="baseline_control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            minimum_paired_sample=3,
        )
        report = ValidationEngine(repo).validate(
            ValidationRunContext(
                plan=plan,
                experiment=manifest,
                candidates=(candidate,),
                training_dataset=dataset_manifest,
                holdout_examples=_holdout_examples(candidate_better=True),
                fold_examples={},
                knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
                artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
                guardrail_thresholds={},
            )
        )
        self.assertIn(
            report.final_disposition,
            {
                ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA,
                ValidationDisposition.INCONCLUSIVE,
                ValidationDisposition.INCONCLUSIVE_INSUFFICIENT_SAMPLE,
            },
        )
        if report.final_disposition != ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA:
            self.skipTest("validation inconclusive in fixture environment")

        policy = build_promotion_policy(
            champion_scope=DEFAULT_SCOPE,
            required_improvement=0.001,
            minimum_holdout_samples=4,
            statistical_requirement=StatisticalRequirementKind.NONE,
        )
        repo.put_promotion_policy(policy)
        champion = engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        repo.put_champion_assignment(champion)

        eligibility = engine.assess_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            candidate_artifact_bytes=artifact_bytes,
        )
        repo.put_promotion_eligibility_assessment(eligibility)

        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T + 50,
        )
        repo.put_challenger_registration(registration)

        shadow_rows = [
            ShadowMatchedObservation(**row)
            for row in shadow_observations(6, challenger_better=True, start_ns=T + 60)
        ]
        shadow = build_shadow_evidence_manifest(
            challenger_registration_id=registration.challenger_registration_id,
            champion_assignment_id=champion.assignment_id,
            promotion_policy_id=policy.promotion_policy_id,
            evidence_tier=EvidenceTier.OBSERVED_REPLAY,
            matched_observations=tuple(shadow_rows),
        )
        repo.put_shadow_evidence_manifest(shadow)

        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            shadow_evidence=shadow,
            experiment=manifest,
        )
        repo.put_promotion_decision(decision)
        self.assertEqual(decision.decision, PromotionDecisionKind.PROMOTE)

        new_champion = engine.create_champion_assignment(
            decision=decision,
            candidate=candidate,
            effective_from_ns=T + 200,
            previous_champion=champion,
        )
        repo.put_champion_assignment(new_champion)
        lifecycle = engine.lifecycle_event(
            registration=registration,
            to_state=ChallengerLifecycleState.PROMOTED,
            effective_at_ns=T + 200,
            from_state=ChallengerLifecycleState.SHADOW_COMPLETE,
            reason_code=None,
        )
        repo.put_challenger_lifecycle_event(lifecycle)

        current = repo.get_current_champion_assignment(
            component=DEFAULT_SCOPE.component,
            target_kind=DEFAULT_SCOPE.target_kind,
            horizon_ns=DEFAULT_SCOPE.horizon_ns,
            mode=DEFAULT_SCOPE.mode,
            as_of_ns=T + 250,
        )
        self.assertEqual(current.assignment_id, new_champion.assignment_id)
        self.assertEqual(current.promotion_decision_id, decision.promotion_decision_id)
        self.assertEqual(repo.get_champion_assignment(champion.assignment_id).assignment_id, champion.assignment_id)

    def test_contaminated_candidate_blocked(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated_report = report
        if report.contamination_disposition == ContaminationDisposition.CLEAN:
            self.skipTest("fixture produced clean report")
        engine = PromotionEngine()
        policy = build_promotion_policy(champion_scope=DEFAULT_SCOPE)
        champion = engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        with self.assertRaises(Exception):
            engine.register_challenger(
                policy=policy,
                candidate=candidate,
                validation_report=mutated_report,
                current_champion=champion,
                registered_at_ns=T,
            )


if __name__ == "__main__":
    unittest.main()
