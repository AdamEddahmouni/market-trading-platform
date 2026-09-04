"""BUILD 20 champion-challenger promotion governance tests."""

from __future__ import annotations

import copy
import unittest

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.promotion import (
    ChallengerLifecycleState,
    ChampionAssignmentReason,
    ChampionScopeV1,
    ComplexityPolicy,
    ComplexityPolicyKind,
    EligibilityDisposition,
    GuardrailRule,
    MetricDirection,
    PromotionDecisionKind,
    PromotionEngine,
    PromotionError,
    PromotionReasonCode,
    ShadowMatchedObservation,
    StatisticalRequirementKind,
    assess_promotion_eligibility,
    build_promotion_policy,
    build_shadow_evidence_manifest,
    promotion_policy_v1_from_dict,
    promotion_policy_v1_to_dict,
    required_improvement_for_complexity,
)
from market_platform_foundation.intelligence.research_experiments.types import ComplexityBudget as ExpComplexityBudget
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.intelligence.validation import (
    ContaminationDisposition,
    HoldoutMetricResult,
    KnowledgeAssessmentStatus,
    ValidationDisposition,
    ValidationReportV1,
)
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.promotion_fixtures import (
    DEFAULT_SCOPE,
    bootstrap_control_champion,
    default_promotion_policy,
    shadow_observations,
    shadow_promotion_policy,
    validated_candidate_bundle,
)


class PromotionPolicyTests(unittest.TestCase):
    def test_policy_round_trip(self) -> None:
        policy = default_promotion_policy()
        restored = promotion_policy_v1_from_dict(promotion_policy_v1_to_dict(policy))
        self.assertEqual(policy.promotion_policy_id, restored.promotion_policy_id)

    def test_policy_id_deterministic(self) -> None:
        policy_a = default_promotion_policy()
        policy_b = default_promotion_policy()
        self.assertEqual(policy_a.promotion_policy_id, policy_b.promotion_policy_id)

    def test_semantic_change_changes_policy_id(self) -> None:
        base = default_promotion_policy(required_improvement=0.001)
        changed = default_promotion_policy(required_improvement=0.01)
        self.assertNotEqual(base.promotion_policy_id, changed.promotion_policy_id)


class EligibilityTests(unittest.TestCase):
    def test_validated_clean_candidate_eligible(self) -> None:
        _repo, _manifest, candidate, artifact_bytes, report, _plan = validated_candidate_bundle()
        policy = default_promotion_policy()
        assessment = assess_promotion_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            candidate_artifact_bytes=artifact_bytes,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.ELIGIBLE)

    def test_inconclusive_ineligible(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "final_disposition", ValidationDisposition.INCONCLUSIVE)
        policy = default_promotion_policy()
        assessment = assess_promotion_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=mutated,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.INELIGIBLE)
        self.assertIn(PromotionReasonCode.VALIDATION_NOT_ELIGIBLE, assessment.reason_codes)

    def test_contaminated_ineligible(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "contamination_disposition", ContaminationDisposition.CONTAMINATED)
        object.__setattr__(mutated, "final_disposition", ValidationDisposition.INVALID_CONTAMINATED)
        assessment = assess_promotion_eligibility(
            policy=default_promotion_policy(),
            candidate=candidate,
            validation_report=mutated,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.INELIGIBLE)
        self.assertIn(PromotionReasonCode.CONTAMINATION_NOT_CLEAN, assessment.reason_codes)

    def test_unknown_contamination_ineligible(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "contamination_disposition", ContaminationDisposition.UNKNOWN)
        assessment = assess_promotion_eligibility(
            policy=default_promotion_policy(),
            candidate=candidate,
            validation_report=mutated,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.INELIGIBLE)

    def test_knowledge_firewall_fail_ineligible(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "knowledge_assessment_status", KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF)
        assessment = assess_promotion_eligibility(
            policy=default_promotion_policy(),
            candidate=candidate,
            validation_report=mutated,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.INELIGIBLE)
        self.assertIn(PromotionReasonCode.TEMPORAL_KNOWLEDGE_NOT_CLEAN, assessment.reason_codes)

    def test_artifact_hash_mismatch_ineligible(self) -> None:
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "candidate_artifact_hashes", ("wrong-hash",))
        assessment = assess_promotion_eligibility(
            policy=default_promotion_policy(),
            candidate=candidate,
            validation_report=mutated,
        )
        self.assertEqual(assessment.disposition, EligibilityDisposition.INELIGIBLE)
        self.assertIn(PromotionReasonCode.ARTIFACT_INTEGRITY_FAILED, assessment.reason_codes)


class ChallengerRegistrationTests(unittest.TestCase):
    def test_valid_registration_deterministic(self) -> None:
        engine = PromotionEngine()
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        policy = default_promotion_policy()
        champion = bootstrap_control_champion(engine, candidate)
        reg_a = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        reg_b = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T + 1,
        )
        self.assertEqual(reg_a.challenger_registration_id, reg_b.challenger_registration_id)

    def test_different_champion_changes_identity(self) -> None:
        engine = PromotionEngine()
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        policy = default_promotion_policy()
        champion_a = bootstrap_control_champion(engine, candidate, effective_from_ns=T)
        champion_b = bootstrap_control_champion(engine, candidate, effective_from_ns=T + 1)
        reg_a = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion_a,
            registered_at_ns=T,
        )
        reg_b = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion_b,
            registered_at_ns=T,
        )
        self.assertNotEqual(reg_a.challenger_registration_id, reg_b.challenger_registration_id)

    def test_ineligible_registration_raises(self) -> None:
        engine = PromotionEngine()
        _repo, _manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle()
        champion = bootstrap_control_champion(engine, candidate)
        mutated = copy.deepcopy(report)
        object.__setattr__(mutated, "final_disposition", ValidationDisposition.INCONCLUSIVE)
        with self.assertRaises(PromotionError):
            engine.register_challenger(
                policy=default_promotion_policy(),
                candidate=candidate,
                validation_report=mutated,
                current_champion=champion,
                registered_at_ns=T,
            )


class ShadowEvidenceTests(unittest.TestCase):
    def _manifest_from_rows(self, rows, **kwargs):
        observations = tuple(ShadowMatchedObservation(**row) for row in rows)
        return build_shadow_evidence_manifest(
            challenger_registration_id="CHREG-test",
            champion_assignment_id="CHAMP-test",
            promotion_policy_id="PROMPOL-test",
            evidence_tier=EvidenceTier.OBSERVED_REPLAY,
            matched_observations=observations,
            **kwargs,
        )

    def test_same_evidence_order_shuffled_same_id(self) -> None:
        rows = shadow_observations(4)
        manifest_a = self._manifest_from_rows(rows)
        manifest_b = self._manifest_from_rows(list(reversed(rows)))
        self.assertEqual(manifest_a.shadow_evidence_id, manifest_b.shadow_evidence_id)

    def test_minimum_sample_boundary(self) -> None:
        rows = shadow_observations(4)
        manifest = self._manifest_from_rows(rows)
        self.assertEqual(manifest.sample_count, 4)

    def test_settlement_incomplete_raises(self) -> None:
        rows = shadow_observations(4)
        rows[0]["settled"] = False
        with self.assertRaises(PromotionError):
            self._manifest_from_rows(rows)


class PromotionDecisionTests(unittest.TestCase):
    def test_promote_when_criteria_met(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.001)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        self.assertEqual(decision.decision, PromotionDecisionKind.PROMOTE)
        self.assertIn(PromotionReasonCode.PROMOTION_CRITERIA_MET, decision.reason_codes)

    def test_retain_when_metric_fails(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.5)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        self.assertEqual(decision.decision, PromotionDecisionKind.RETAIN_CHAMPION)

    def test_same_inputs_same_decision_id(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.001)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision_a = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        decision_b = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        self.assertEqual(decision_a.promotion_decision_id, decision_b.promotion_decision_id)

    def test_champion_changed_mid_challenge_invalid(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.001)
        champion_a = bootstrap_control_champion(engine, candidate, effective_from_ns=T)
        champion_b = bootstrap_control_champion(engine, candidate, effective_from_ns=T + 100)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion_a,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion_b,
            experiment=manifest,
        )
        self.assertEqual(decision.decision, PromotionDecisionKind.INVALID)
        self.assertIn(PromotionReasonCode.CHAMPION_CHANGED, decision.reason_codes)

    def test_insufficient_shadow_inconclusive(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = shadow_promotion_policy(minimum_shadow_samples=10)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            shadow_evidence=None,
            experiment=manifest,
        )
        self.assertEqual(decision.decision, PromotionDecisionKind.INCONCLUSIVE)


class ComplexityPenaltyTests(unittest.TestCase):
    def test_higher_complexity_requires_larger_margin(self) -> None:
        policy = ComplexityPolicy(
            kind=ComplexityPolicyKind.TIERED_MARGIN,
            base_required_improvement=0.005,
            minor_complexity_additional_margin=0.005,
            major_complexity_additional_margin=0.01,
        )
        same = required_improvement_for_complexity(
            policy,
            champion_complexity=ExpComplexityBudget.SAME_COMPLEXITY,
            challenger_complexity=ExpComplexityBudget.SAME_COMPLEXITY,
        )
        major = required_improvement_for_complexity(
            policy,
            champion_complexity=ExpComplexityBudget.SAME_COMPLEXITY,
            challenger_complexity=ExpComplexityBudget.MAJOR_COMPLEXITY_INCREASE,
        )
        self.assertLess(same, major)

    def test_complexity_penalty_retains_champion(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = build_promotion_policy(
            champion_scope=DEFAULT_SCOPE,
            required_improvement=0.001,
            minimum_holdout_samples=4,
            statistical_requirement=StatisticalRequirementKind.NONE,
            complexity_policy=ComplexityPolicy(
                kind=ComplexityPolicyKind.TIERED_MARGIN,
                base_required_improvement=0.001,
                minor_complexity_additional_margin=0.0,
                major_complexity_additional_margin=0.5,
            ),
        )
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        major_manifest = copy.deepcopy(manifest)
        object.__setattr__(major_manifest, "complexity_budget", ExpComplexityBudget.MAJOR_COMPLEXITY_INCREASE)
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=major_manifest,
            champion_complexity=ExpComplexityBudget.SAME_COMPLEXITY,
        )
        self.assertEqual(decision.decision, PromotionDecisionKind.RETAIN_CHAMPION)
        self.assertIn(PromotionReasonCode.COMPLEXITY_NOT_JUSTIFIED, decision.reason_codes)


class ChampionAssignmentTests(unittest.TestCase):
    def test_bootstrap_explicit(self) -> None:
        engine = PromotionEngine()
        _repo, _manifest, candidate, _artifact_bytes, _report, _plan = validated_candidate_bundle()
        assignment = engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        self.assertEqual(assignment.assignment_reason, ChampionAssignmentReason.BOOTSTRAP)
        self.assertIsNone(assignment.promotion_decision_id)

    def test_promote_creates_assignment(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.001)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        assignment = engine.create_champion_assignment(
            decision=decision,
            candidate=candidate,
            effective_from_ns=T + 200,
            previous_champion=champion,
        )
        self.assertEqual(assignment.previous_assignment_id, champion.assignment_id)
        self.assertEqual(assignment.promotion_decision_id, decision.promotion_decision_id)

    def test_retain_does_not_create_assignment_via_engine_guard(self) -> None:
        engine = PromotionEngine()
        _repo, manifest, candidate, _artifact_bytes, report, _plan = validated_candidate_bundle(candidate_better=True)
        policy = default_promotion_policy(required_improvement=0.5)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
        )
        decision = engine.evaluate_promotion(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            experiment=manifest,
        )
        with self.assertRaises(PromotionError):
            engine.create_champion_assignment(
                decision=decision,
                candidate=candidate,
                effective_from_ns=T + 200,
                previous_champion=champion,
            )


class PromotionPersistenceTests(unittest.TestCase):
    def test_promotion_policy_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        policy = default_promotion_policy()
        first = repo.put_promotion_policy(policy)
        second = repo.put_promotion_policy(policy)
        self.assertEqual(first, RepositoryPutResult.INSERTED)
        self.assertEqual(second, RepositoryPutResult.ALREADY_PRESENT)

    def test_promotion_policy_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        policy = default_promotion_policy()
        repo.put_promotion_policy(policy)
        mutated = copy.deepcopy(policy)
        object.__setattr__(mutated, "metadata", {"changed": True})
        with self.assertRaises(RepositoryConflictError):
            repo.put_promotion_policy(mutated)

    def test_current_champion_lookup(self) -> None:
        repo = InMemoryIntelligenceRepository()
        engine = PromotionEngine()
        _repo, _manifest, candidate, _artifact_bytes, _report, _plan = validated_candidate_bundle()
        assignment_a = engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        assignment_b = engine.bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T + 100,
        )
        repo.put_champion_assignment(assignment_a)
        repo.put_champion_assignment(assignment_b)
        current = repo.get_current_champion_assignment(
            component=DEFAULT_SCOPE.component,
            target_kind=DEFAULT_SCOPE.target_kind,
            horizon_ns=DEFAULT_SCOPE.horizon_ns,
            mode=DEFAULT_SCOPE.mode,
            as_of_ns=T + 150,
        )
        self.assertEqual(current.assignment_id, assignment_b.assignment_id)


class ShadowSafetyTests(unittest.TestCase):
    def test_no_execution_authority_in_promotion_engine(self) -> None:
        source = PromotionEngine.evaluate_promotion.__doc__ or ""
        self.assertNotIn("TradeProposal", source)
        self.assertNotIn("broker", source.lower())


if __name__ == "__main__":
    unittest.main()
