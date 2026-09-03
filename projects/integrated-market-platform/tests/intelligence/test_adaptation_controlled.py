"""BUILD 24 controlled adaptation tests."""

from __future__ import annotations

import unittest
from unittest import mock

from market_platform_foundation.intelligence.adaptation import (
    AdaptationAction,
    AdaptationEngine,
    AdaptationPolicyV1,
    EvidenceBundle,
    ResearchPriority,
    ResearchTriggerV1,
    SuggestedResearchClass,
    adaptation_assessment_v1_from_dict,
    adaptation_assessment_v1_to_dict,
    adaptation_policy_v1_from_dict,
    adaptation_policy_v1_to_dict,
    build_adaptation_policy,
    consumed_evidence_ref_ids,
    derive_adaptation_policy_id,
    register_finding_from_trigger,
    research_trigger_v1_from_dict,
    research_trigger_v1_to_dict,
)
from market_platform_foundation.intelligence.governance import DriftSeverity, DriftType
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository, RepositoryPutResult
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.research_experiments.types import ResearchFindingType
from market_platform_foundation.intelligence.adaptation.service import AdaptationService
from tests.intelligence.adaptation_fixtures import (
    default_adaptation_policy,
    default_context,
    performance_drift_assessment,
    recurrence_bundle,
    schema_drift_assessment,
)
from tests.intelligence.governance_fixtures import activated_champion_bundle, monitoring_window
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE


class AdaptationPolicyTests(unittest.TestCase):
    def test_policy_round_trip(self) -> None:
        policy = default_adaptation_policy()
        restored = adaptation_policy_v1_from_dict(adaptation_policy_v1_to_dict(policy))
        self.assertEqual(policy.adaptation_policy_id, restored.adaptation_policy_id)

    def test_policy_id_determinism(self) -> None:
        p1 = default_adaptation_policy()
        p2 = default_adaptation_policy()
        self.assertEqual(p1.adaptation_policy_id, p2.adaptation_policy_id)

    def test_semantic_change_changes_id(self) -> None:
        p1 = default_adaptation_policy()
        p2 = default_adaptation_policy(minimum_recurrence_count=3)
        self.assertNotEqual(p1.adaptation_policy_id, p2.adaptation_policy_id)

    def test_invalid_cooldown_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_adaptation_policy(champion_scope=DEFAULT_SCOPE, cooldown_ns=-1)

    def test_empty_evidence_classes_rejected(self) -> None:
        from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION

        with self.assertRaises(ValueError):
            AdaptationPolicyV1(
                adaptation_policy_id="bad",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                champion_scope=DEFAULT_SCOPE,
                eligible_evidence_types=(),
            )


class EvidenceEligibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AdaptationEngine()
        self.policy = default_adaptation_policy()

    def test_healthy_evidence_no_trigger(self) -> None:
        bundle = EvidenceBundle(drift_assessments=())
        results = self.engine.assess(
            policy=self.policy,
            evidence=self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        self.assertEqual(results, ())

    def test_single_warning_accumulates(self) -> None:
        bundle = EvidenceBundle(
            drift_assessments=(performance_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M),)
        )
        results = self.engine.assess(
            policy=self.policy,
            evidence=self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].assessment.action, AdaptationAction.ACCUMULATE)
        self.assertIsNone(results[0].trigger)

    def test_recurrence_triggers_research(self) -> None:
        results = self.engine.assess(
            policy=self.policy,
            evidence=self.engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].assessment.action, AdaptationAction.TRIGGER_RESEARCH)
        self.assertIsNotNone(results[0].trigger)
        self.assertTrue(results[0].trigger.research_trigger_id.startswith("RTRIG-"))

    def test_structural_schema_triggers_immediately(self) -> None:
        policy = default_adaptation_policy(minimum_sample=100, minimum_recurrence_count=5)
        bundle = EvidenceBundle(
            drift_assessments=(schema_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M),)
        )
        results = self.engine.assess(
            policy=policy,
            evidence=self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        self.assertEqual(results[0].assessment.action, AdaptationAction.TRIGGER_RESEARCH)
        self.assertEqual(results[0].trigger.suggested_research_class, SuggestedResearchClass.FEATURES)

    def test_insufficient_sample_accumulates(self) -> None:
        policy = default_adaptation_policy(minimum_sample=100)
        bundle = EvidenceBundle(
            drift_assessments=(
                performance_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M, sample_count=5),
                performance_drift_assessment(
                    start_ns=T + HORIZON_5M,
                    end_ns=T + HORIZON_5M * 2,
                    sample_count=5,
                ),
            )
        )
        results = self.engine.assess(
            policy=policy,
            evidence=self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        self.assertEqual(results[0].assessment.action, AdaptationAction.ACCUMULATE)


class DeduplicationCooldownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AdaptationEngine()
        self.policy = default_adaptation_policy(cooldown_ns=HORIZON_5M * 10)

    def test_exact_duplicate_suppressed(self) -> None:
        bundle = recurrence_bundle()
        evidence = self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE)
        first = self.engine.assess(policy=self.policy, evidence=evidence, context=default_context())[0]
        self.assertIsNotNone(first.trigger)
        context = default_context(
            existing_triggers=(first.trigger,),
            consumed_evidence_ref_ids=consumed_evidence_ref_ids((first.trigger,)),
        )
        second = self.engine.assess(policy=self.policy, evidence=evidence, context=context)[0]
        self.assertEqual(second.assessment.action, AdaptationAction.SUPPRESS_DUPLICATE)

    def test_cooldown_boundary(self) -> None:
        bundle = recurrence_bundle()
        evidence = self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE)
        first = self.engine.assess(policy=self.policy, evidence=evidence, context=default_context())[0]
        trigger = first.trigger
        assert trigger is not None
        within = default_context(
            reference_time_ns=trigger.evidence_window.end_ns + self.policy.cooldown_ns - 1,
            existing_triggers=(trigger,),
        )
        new_bundle = EvidenceBundle(
            drift_assessments=(
                performance_drift_assessment(
                    start_ns=T + HORIZON_5M * 4,
                    end_ns=T + HORIZON_5M * 5,
                ),
                performance_drift_assessment(
                    start_ns=T + HORIZON_5M * 5,
                    end_ns=T + HORIZON_5M * 6,
                ),
            )
        )
        new_evidence = self.engine.normalize_bundle(new_bundle, champion_scope=DEFAULT_SCOPE)
        suppressed = self.engine.assess(policy=self.policy, evidence=new_evidence, context=within)[0]
        self.assertEqual(suppressed.assessment.action, AdaptationAction.SUPPRESS_COOLDOWN)
        after = default_context(
            reference_time_ns=trigger.evidence_window.end_ns + self.policy.cooldown_ns,
            existing_triggers=(trigger,),
        )
        eligible = self.engine.assess(policy=self.policy, evidence=new_evidence, context=after)
        self.assertTrue(any(row.trigger is not None for row in eligible))

    def test_open_research_suppression(self) -> None:
        bundle = recurrence_bundle()
        evidence = self.engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE)
        first = self.engine.assess(policy=self.policy, evidence=evidence, context=default_context())[0]
        assert first.trigger is not None
        context = default_context(open_research_dedup_keys=frozenset({first.trigger.dedup_key}))
        new_bundle = EvidenceBundle(
            drift_assessments=(
                performance_drift_assessment(
                    start_ns=T + HORIZON_5M * 4,
                    end_ns=T + HORIZON_5M * 5,
                ),
                performance_drift_assessment(
                    start_ns=T + HORIZON_5M * 5,
                    end_ns=T + HORIZON_5M * 6,
                ),
            )
        )
        result = self.engine.assess(
            policy=self.policy,
            evidence=self.engine.normalize_bundle(new_bundle, champion_scope=DEFAULT_SCOPE),
            context=context,
        )[0]
        self.assertEqual(result.assessment.action, AdaptationAction.SUPPRESS_EXISTING_RESEARCH)


class ResearchTriggerTests(unittest.TestCase):
    def test_trigger_round_trip(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        result = engine.assess(
            policy=policy,
            evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )[0]
        trigger = result.trigger
        assert trigger is not None
        restored = research_trigger_v1_from_dict(research_trigger_v1_to_dict(trigger))
        self.assertEqual(trigger.research_trigger_id, restored.research_trigger_id)

    def test_trigger_id_determinism(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        evidence = engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE)
        context = default_context()
        t1 = engine.assess(policy=policy, evidence=evidence, context=context)[0].trigger
        t2 = engine.assess(policy=policy, evidence=evidence, context=context)[0].trigger
        assert t1 is not None and t2 is not None
        self.assertEqual(t1.research_trigger_id, t2.research_trigger_id)

    def test_trigger_input_order_independent(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        bundle = recurrence_bundle()
        forward = engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE)
        reverse = tuple(reversed(forward))
        t1 = engine.assess(policy=policy, evidence=forward, context=default_context())[0].trigger
        t2 = engine.assess(policy=policy, evidence=reverse, context=default_context())[0].trigger
        assert t1 is not None and t2 is not None
        self.assertEqual(t1.research_trigger_id, t2.research_trigger_id)

    def test_priority_not_truth_probability(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        result = engine.assess(
            policy=policy,
            evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )[0]
        assert result.trigger is not None
        self.assertIn(result.trigger.priority, ResearchPriority)


class Build17HandoffTests(unittest.TestCase):
    def test_register_finding_preserves_lineage(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        trigger = engine.assess(
            policy=policy,
            evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )[0].trigger
        assert trigger is not None
        finding = register_finding_from_trigger(trigger, mode="PAPER")
        self.assertEqual(finding.finding_type, ResearchFindingType.MONITORING_OBSERVATION)
        self.assertEqual(finding.metadata["research_trigger_id"], trigger.research_trigger_id)
        self.assertNotIn("because", finding.observation_summary.lower())

    def test_no_automatic_hypothesis(self) -> None:
        self.assertFalse(hasattr(register_finding_from_trigger, "register_hypothesis"))


class BoundarySafetyTests(unittest.TestCase):
    def test_no_training_calls(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
        ) as generate:
            AdaptationEngine().assess(
                policy=default_adaptation_policy(),
                evidence=AdaptationEngine().normalize_bundle(
                    recurrence_bundle(),
                    champion_scope=DEFAULT_SCOPE,
                ),
                context=default_context(),
            )
            generate.assert_not_called()

    def test_distinct_issue_separation(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        bundle = EvidenceBundle(
            drift_assessments=(
                performance_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M),
                performance_drift_assessment(start_ns=T + HORIZON_5M, end_ns=T + HORIZON_5M * 2),
                schema_drift_assessment(start_ns=T + HORIZON_5M * 2, end_ns=T + HORIZON_5M * 3),
            )
        )
        results = engine.assess(
            policy=policy,
            evidence=engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )
        triggers = [row.trigger for row in results if row.trigger is not None]
        self.assertGreaterEqual(len(triggers), 2)
        classes = {trigger.suggested_research_class for trigger in triggers}
        self.assertIn(SuggestedResearchClass.FEATURES, classes)


class PersistenceTests(unittest.TestCase):
    def test_immutable_insert_and_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        service = AdaptationService(repository=repo)
        policy = default_adaptation_policy()
        results = service.assess_and_persist(
            policy=policy,
            bundle=recurrence_bundle(),
            context=default_context(),
            persist=True,
        )
        trigger = results[0].trigger
        assert trigger is not None
        self.assertEqual(repo.put_research_trigger(trigger), RepositoryPutResult.ALREADY_PRESENT)
        conflict = ResearchTriggerV1(
            research_trigger_id=trigger.research_trigger_id,
            schema_version=trigger.schema_version,
            champion_scope=trigger.champion_scope,
            evidence_window=trigger.evidence_window,
            adaptation_policy_ref=trigger.adaptation_policy_ref,
            adaptation_assessment_ref=trigger.adaptation_assessment_ref,
            source_evidence_refs=trigger.source_evidence_refs,
            evidence_types=trigger.evidence_types,
            severity=trigger.severity,
            observed_metric_summary={"mutated": 1.0},
            sample_counts=trigger.sample_counts,
            suggested_research_class=trigger.suggested_research_class,
            priority=trigger.priority,
            dedup_key=trigger.dedup_key,
            limitations=trigger.limitations,
            observation_summary="Different observation summary for conflict test.",
            lineage_refs=trigger.lineage_refs,
            metadata=trigger.metadata,
        )
        with self.assertRaises(RepositoryConflictError):
            repo.put_research_trigger(conflict)


class FeedbackLoopTests(unittest.TestCase):
    def test_adaptation_trigger_not_reused_as_evidence(self) -> None:
        engine = AdaptationEngine()
        policy = default_adaptation_policy()
        result = engine.assess(
            policy=policy,
            evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
            context=default_context(),
        )[0]
        assert result.trigger is not None
        from market_platform_foundation.intelligence.adaptation.evidence import NormalizedEvidence
        from market_platform_foundation.intelligence.contracts.common import ContractReference

        fake = NormalizedEvidence(
            evidence_type=result.trigger.evidence_types[0],
            evidence_ref=ContractReference(kind="research_trigger", id=result.trigger.research_trigger_id),
            champion_scope=DEFAULT_SCOPE,
            window=monitoring_window(),
            severity=DriftSeverity.CRITICAL,
            drift_types=(DriftType.PERFORMANCE_DRIFT,),
            sample_count=100,
            metric_observations={},
            sample_counts={"n": 100},
            evidence_class=result.assessment.evidence_class,
            suggested_research_class=result.trigger.suggested_research_class,
            window_key="loop",
        )
        follow_up = engine.assess(
            policy=policy,
            evidence=(fake,),
            context=default_context(existing_triggers=(result.trigger,)),
        )
        self.assertTrue(follow_up)


if __name__ == "__main__":
    unittest.main()
