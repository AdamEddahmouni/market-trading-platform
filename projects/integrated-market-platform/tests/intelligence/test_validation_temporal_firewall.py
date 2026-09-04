"""BUILD 19 independent validation and temporal knowledge firewall tests."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.baselines import BaselineClassLabel
from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema
from market_platform_foundation.intelligence.baselines.training import BaselineTrainingExample
from market_platform_foundation.intelligence.baselines.types import BaselineFeatureVector
from market_platform_foundation.intelligence.evaluation.metrics import compute_brier_contribution
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.research_experiments import (
    ComponentMutationSpec,
    DataSpecification,
    ExperimentKind,
    ExperimentManifestV1,
    FalsificationCriterion,
    MetricPlan,
    ResearchHypothesisKind,
    ResearchKnowledgeFootprint,
    ResourceBudget,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
    build_research_hypothesis,
    design_experiment,
)
from market_platform_foundation.intelligence.training import TrainerKind, TrainingFactory
from market_platform_foundation.intelligence.training.datasets import build_dataset_from_examples
from market_platform_foundation.intelligence.training.search import expand_candidate_specs
from market_platform_foundation.intelligence.training.trainers import get_trainer
from market_platform_foundation.intelligence.training.types import TrainingExampleRef
from market_platform_foundation.intelligence.validation import (
    ContaminationDisposition,
    KnowledgeAssessmentStatus,
    KnowledgeCutoffState,
    StatisticalPlan,
    ToolPolicyClass,
    ValidationDataAccessGuard,
    ValidationDisposition,
    ValidationEngine,
    ValidationError,
    ValidationExample,
    ValidationRunContext,
    WalkForwardMode,
    WalkForwardSpec,
    aggregate_assessment_status,
    assess_holdout_contamination,
    assess_knowledge_cutoff,
    assess_prompt_only_time_travel,
    assess_retrieval_source,
    assess_tool_policy,
    build_validation_plan,
    derive_validation_plan_id,
    generate_walk_forward_folds,
    is_training_example_purge_clean,
    llm_profile,
    moving_block_bootstrap_ci,
    paired_metric_deltas,
    require_historical_inference_allowed,
    statistical_candidate_profile,
    validation_plan_v1_from_dict,
    validation_plan_v1_to_dict,
    verify_plan_matches_commitment,
    verify_training_purge_for_fold,
)
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.test_baseline_fixtures import default_target
from tests.intelligence.test_training_factory import _experiment_manifest, _synthetic_examples


def _manifest_with_holdout(holdout_start_ns: int, **kwargs):
    base = _experiment_manifest(**kwargs)
    return ExperimentManifestV1(
        experiment_id=base.experiment_id,
        schema_version=base.schema_version,
        research_hypothesis_id=base.research_hypothesis_id,
        experiment_kind=base.experiment_kind,
        treatment=base.treatment,
        control=base.control,
        data_spec=base.data_spec,
        metric_plan=base.metric_plan,
        success_criteria=base.success_criteria,
        falsification=base.falsification,
        knowledge_footprint=base.knowledge_footprint,
        validation_requirements=base.validation_requirements,
        guardrails=base.guardrails,
        search_space=base.search_space,
        seed_policy=base.seed_policy,
        complexity_budget=base.complexity_budget,
        resource_budget=base.resource_budget,
        allowed_changes=base.allowed_changes,
        forbidden_changes=base.forbidden_changes,
        evaluation_spec_id=base.evaluation_spec_id,
        implementation_version=base.implementation_version,
        metadata={"holdout_start_ns": holdout_start_ns},
    )


NS_2024 = 1_704_067_200_000_000_000
NS_2026 = 1_767_225_600_000_000_000


def _holdout_examples(count: int = 8, *, candidate_better: bool = True) -> tuple[ValidationExample, ...]:
    rows: list[ValidationExample] = []
    for idx in range(count):
        label = 1 if idx % 2 == 0 else 0
        if candidate_better:
            candidate_p = 0.8 if label == 1 else 0.2
            control_p = 0.6 if label == 1 else 0.4
        else:
            candidate_p = 0.6 if label == 1 else 0.4
            control_p = 0.6 if label == 1 else 0.4
        rows.append(
            ValidationExample(
                example_id=f"ex-{idx}",
                snapshot_id=f"snap-h-{idx}",
                decision_time_ns=T + 20 + idx,
                label_available_time_ns=T + 20 + idx + HORIZON_5M,
                binary_label=label,
                candidate_probability=candidate_p,
                control_probability=control_p,
                forecast_id=f"fc-h-{idx}",
                outcome_id=f"out-h-{idx}",
            )
        )
    return tuple(rows)


def _trained_candidate(repo: InMemoryIntelligenceRepository, manifest):
    repo.put_experiment_manifest(manifest)
    schema = BaselineFeatureSchema(selectors=())
    prepared = build_dataset_from_examples(
        experiment_id=manifest.experiment_id,
        examples=_synthetic_examples(),
        feature_schema=schema,
        target=default_target(),
        training_cutoff_ns=T + HORIZON_5M,
        development_start_ns=T,
        development_end_ns=T + 10,
        horizon_ns=HORIZON_5M,
    )
    repo.put_training_dataset_manifest(prepared.manifest)
    specs = expand_candidate_specs(
        manifest,
        training_dataset_id=prepared.manifest.training_dataset_id,
        dataset_fingerprint=prepared.manifest.dataset_fingerprint,
        trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
        trainer_version="training-distillation-factory-v1",
        target_kind="direction_up_down",
        horizon_ns=HORIZON_5M,
        mode="ACTUAL_LIVE",
        base_hyperparameters={},
        authorized_mutation_surface=("baseline_model",),
    )
    with tempfile.TemporaryDirectory() as tmp:
        trainer = get_trainer(TrainerKind.LOGISTIC_REGRESSION)
        result = trainer.train(specs[0], prepared)
        assert result.candidate is not None
        repo.put_training_run_manifest(result.run)
        repo.put_candidate_artifact(result.candidate)
        return result.candidate, prepared.manifest, result.artifact_bytes


class ValidationPlanTests(unittest.TestCase):
    def test_plan_round_trip(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        payload = validation_plan_v1_to_dict(plan)
        restored = validation_plan_v1_from_dict(payload)
        self.assertEqual(plan.validation_plan_id, restored.validation_plan_id)

    def test_plan_id_deterministic(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan_a = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        plan_b = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        self.assertEqual(plan_a.validation_plan_id, plan_b.validation_plan_id)

    def test_semantic_change_changes_plan_id(self) -> None:
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        base = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            purge_ns=0,
        )
        changed = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            purge_ns=100,
        )
        self.assertNotEqual(base.validation_plan_id, changed.validation_plan_id)


class WalkForwardTests(unittest.TestCase):
    def test_fold_generation_chronological(self) -> None:
        spec = WalkForwardSpec(
            mode=WalkForwardMode.EXPANDING,
            fold_boundaries_ns=(T, T + 5, T + 10),
            fold_candidate_ids=("c1", "c1"),
        )
        folds = generate_walk_forward_folds(spec)
        self.assertEqual(len(folds), 2)
        self.assertEqual(folds[0].validation_start_ns, T)
        self.assertEqual(folds[1].validation_start_ns, T + 5)

    def test_missing_fold_candidate_allowed_in_spec(self) -> None:
        spec = WalkForwardSpec(
            mode=WalkForwardMode.EXPANDING,
            fold_boundaries_ns=(T, T + 5, T + 10),
            fold_candidate_ids=(None, None),
        )
        folds = generate_walk_forward_folds(spec)
        self.assertIsNone(folds[0].candidate_id)


class PurgeTests(unittest.TestCase):
    def test_clean_example(self) -> None:
        self.assertTrue(
            is_training_example_purge_clean(
                label_available_time_ns=T,
                validation_start_ns=T + 100,
                purge_ns=0,
            )
        )

    def test_overlap_violation(self) -> None:
        self.assertFalse(
            is_training_example_purge_clean(
                label_available_time_ns=T + 100,
                validation_start_ns=T + 50,
                purge_ns=0,
            )
        )

    def test_equality_conservative(self) -> None:
        self.assertFalse(
            is_training_example_purge_clean(
                label_available_time_ns=T + 50,
                validation_start_ns=T + 50,
                purge_ns=0,
            )
        )


class HoldoutGuardTests(unittest.TestCase):
    def test_outcome_access_before_commitment_blocked(self) -> None:
        repo = InMemoryIntelligenceRepository()
        guard = ValidationDataAccessGuard(repo)
        with self.assertRaises(ValidationError) as ctx:
            guard.get_holdout_outcome("out-1")
        self.assertEqual(ctx.exception.code, "HOLDOUT_OUTCOME_ACCESS_BEFORE_COMMITMENT")
        self.assertEqual(len(guard.outcome_reads_before_commitment), 1)


class KnowledgeFirewallTests(unittest.TestCase):
    def test_statistical_profile_not_applicable(self) -> None:
        profile = statistical_candidate_profile("cand-1")
        assessment = assess_knowledge_cutoff(profile, T)
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.NOT_APPLICABLE)

    def test_llm_cutoff_before_decision_passes(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2024,
        )
        assessment = assess_knowledge_cutoff(profile, NS_2024 + 1)
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.PASS)

    def test_llm_cutoff_after_decision_fails(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2026,
        )
        with self.assertRaises(ValidationError):
            require_historical_inference_allowed(profile, NS_2024)

    def test_unknown_cutoff_blocked(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.UNKNOWN,
        )
        assessment = assess_knowledge_cutoff(profile, NS_2024)
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF)

    def test_prompt_only_time_travel_fails(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2026,
        )
        assessment = assess_prompt_only_time_travel(
            profile, NS_2024, prompt_claims_historical_date=True
        )
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.FAIL_KNOWLEDGE_CUTOFF)

    def test_future_retrieval_fails(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2024,
        )
        assessment = assess_retrieval_source(
            available_time_ns=NS_2026,
            decision_time_ns=NS_2024,
            profile=profile,
        )
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.FAIL_RETRIEVAL_TIME)

    def test_pit_tool_passes(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2024,
        )
        assessment = assess_tool_policy(ToolPolicyClass.PIT_SAFE, profile, NS_2024)
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.PASS)

    def test_current_web_tool_fails(self) -> None:
        profile = llm_profile(
            component_id="llm",
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2024,
        )
        assessment = assess_tool_policy(ToolPolicyClass.CURRENT_ONLY, profile, NS_2024)
        self.assertEqual(assessment.status, KnowledgeAssessmentStatus.FAIL_TOOL_POLICY)


class BootstrapTests(unittest.TestCase):
    def test_deterministic_seed(self) -> None:
        deltas = (0.1, -0.2, 0.05, -0.1, 0.0, -0.3)
        plan = StatisticalPlan(
            block_length=2,
            replicate_count=100,
            seed=42,
            confidence_level=0.95,
            minimum_paired_sample=3,
        )
        first = moving_block_bootstrap_ci(deltas, plan)
        second = moving_block_bootstrap_ci(deltas, plan)
        self.assertEqual(first.ci_lower, second.ci_lower)
        self.assertEqual(first.ci_upper, second.ci_upper)

    def test_insufficient_sample_inconclusive(self) -> None:
        from market_platform_foundation.intelligence.validation.statistics import evaluate_statistical_criteria

        plan = StatisticalPlan(
            block_length=1,
            replicate_count=50,
            seed=1,
            confidence_level=0.95,
            minimum_paired_sample=5,
        )
        paired = moving_block_bootstrap_ci((0.1,), plan)
        outcome = evaluate_statistical_criteria(paired, plan)
        self.assertEqual(outcome, "INCONCLUSIVE_INSUFFICIENT_SAMPLE")


class ContaminationTests(unittest.TestCase):
    def test_training_overlap_detected(self) -> None:
        from market_platform_foundation.intelligence.training.types import TrainingDatasetManifestV1, SupervisionKind

        dataset = TrainingDatasetManifestV1(
            training_dataset_id="ds",
            schema_version="1",
            experiment_id="exp",
            development_start_ns=T,
            development_end_ns=T + 20,
            training_cutoff_ns=T + 10,
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
            feature_schema_fingerprint="fp",
            example_count=1,
            example_refs=(
                TrainingExampleRef(snapshot_id="s1", decision_time_ns=T + 15),
            ),
            dataset_fingerprint="df",
            supervision_kind=SupervisionKind.OUTCOME_LABEL,
        )
        ledger = assess_holdout_contamination(
            footprint=ResearchKnowledgeFootprint(),
            training_dataset=dataset,
            holdout=type("H", (), {"holdout_start_ns": T + 10, "holdout_end_ns": T + 20})(),
            validation_plan_id="plan",
            experiment_id="exp",
        )
        self.assertEqual(ledger.disposition, ContaminationDisposition.CONTAMINATED)


class Build01To19LifecycleTests(unittest.TestCase):
    def test_clean_statistical_candidate_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _manifest_with_holdout(
            T + 8,
            search_space=SearchSpaceSpec(parameters={"C": (1.0,)}),
            seed_policy=SeedPolicy(fixed_seeds=(11,)),
            resource_budget=ResourceBudget(max_candidates=1, max_training_runs=1),
        )
        candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
        plan = build_validation_plan(
            manifest,
            (candidate,),
            control_ref="baseline_control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            minimum_paired_sample=3,
        )
        engine = ValidationEngine(repo)
        report = engine.validate(
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
        self.assertEqual(report.knowledge_assessment_status, KnowledgeAssessmentStatus.NOT_APPLICABLE)
        self.assertEqual(report.contamination_disposition, ContaminationDisposition.CLEAN)
        self.assertIn(
            report.final_disposition,
            {
                ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA,
                ValidationDisposition.INCONCLUSIVE,
                ValidationDisposition.INCONCLUSIVE_INSUFFICIENT_SAMPLE,
            },
        )
        stored = repo.get_validation_report(report.validation_report_id)
        self.assertIsNotNone(stored)

    def test_contaminated_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _manifest_with_holdout(T + 2)
        candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
        footprint = ResearchKnowledgeFootprint(
            decision_start_ns=T,
            decision_end_ns=T + 10,
        )
        contaminated_manifest = ExperimentManifestV1(
            experiment_id=manifest.experiment_id,
            schema_version=manifest.schema_version,
            research_hypothesis_id=manifest.research_hypothesis_id,
            experiment_kind=manifest.experiment_kind,
            treatment=manifest.treatment,
            control=manifest.control,
            data_spec=manifest.data_spec,
            metric_plan=manifest.metric_plan,
            success_criteria=manifest.success_criteria,
            falsification=manifest.falsification,
            knowledge_footprint=footprint,
            validation_requirements=manifest.validation_requirements,
            guardrails=manifest.guardrails,
            search_space=manifest.search_space,
            seed_policy=manifest.seed_policy,
            complexity_budget=manifest.complexity_budget,
            resource_budget=manifest.resource_budget,
            allowed_changes=manifest.allowed_changes,
            forbidden_changes=manifest.forbidden_changes,
            evaluation_spec_id=manifest.evaluation_spec_id,
            implementation_version=manifest.implementation_version,
            metadata=manifest.metadata,
        )
        plan = build_validation_plan(
            contaminated_manifest,
            (candidate,),
            control_ref="baseline_control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            minimum_paired_sample=3,
        )
        engine = ValidationEngine(repo)
        report = engine.validate(
            ValidationRunContext(
                plan=plan,
                experiment=contaminated_manifest,
                candidates=(candidate,),
                training_dataset=dataset_manifest,
                holdout_examples=_holdout_examples(),
                fold_examples={},
                knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
                artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
                guardrail_thresholds={},
            )
        )
        self.assertEqual(report.final_disposition, ValidationDisposition.INVALID_CONTAMINATED)

    def test_llm_knowledge_leak_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _manifest_with_holdout(T + 8)
        candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
        plan = build_validation_plan(
            manifest,
            (candidate,),
            control_ref="baseline_control",
            fold_boundaries_ns=(T, T + 4, T + 8),
            minimum_paired_sample=3,
        )
        llm = llm_profile(
            component_id=candidate.candidate_id,
            knowledge_cutoff_state=KnowledgeCutoffState.DECLARED_BOUNDED,
            model_knowledge_cutoff_ns=NS_2026,
        )
        engine = ValidationEngine(repo)
        report = engine.validate(
            ValidationRunContext(
                plan=plan,
                experiment=manifest,
                candidates=(candidate,),
                training_dataset=dataset_manifest,
                holdout_examples=_holdout_examples(),
                fold_examples={},
                knowledge_profiles={candidate.candidate_id: llm},
                artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
                guardrail_thresholds={},
            )
        )
        self.assertEqual(report.final_disposition, ValidationDisposition.INVALID_KNOWLEDGE_FIREWALL)


class MetricReuseTests(unittest.TestCase):
    def test_brier_reuse(self) -> None:
        example = ValidationExample(
            example_id="e1",
            snapshot_id="s1",
            decision_time_ns=T,
            label_available_time_ns=T + HORIZON_5M,
            binary_label=1,
            candidate_probability=0.7,
            control_probability=0.6,
        )
        from market_platform_foundation.intelligence.validation.metrics import compute_example_primary_metric

        direct = compute_brier_contribution(0.7, 1)
        via_validation = compute_example_primary_metric(example, primary_metric="brier_score", for_candidate=True)
        self.assertAlmostEqual(direct, via_validation)


class PersistenceTests(unittest.TestCase):
    def test_validation_plan_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        first = repo.put_validation_plan(plan)
        second = repo.put_validation_plan(plan)
        self.assertEqual(first, RepositoryPutResult.INSERTED)
        self.assertEqual(second, RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_on_changed_plan(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _manifest_with_holdout(T + 8)
        candidate = type("C", (), {"candidate_id": "c1", "artifact_hash": "h1"})()
        plan = build_validation_plan(
            manifest,
            (candidate,),  # type: ignore[arg-type]
            control_ref="control",
            fold_boundaries_ns=(T, T + 4, T + 8),
        )
        repo.put_validation_plan(plan)
        mutated = copy.deepcopy(plan)
        object.__setattr__(mutated, "metadata", {"changed": True})
        with self.assertRaises(RepositoryConflictError):
            repo.put_validation_plan(mutated)


if __name__ == "__main__":
    unittest.main()
