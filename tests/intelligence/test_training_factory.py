"""BUILD 18 training and distillation factory tests."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.baselines import BaselineClassLabel, direction_up_down_target
from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema
from market_platform_foundation.intelligence.baselines.training import BaselineTrainingExample
from market_platform_foundation.intelligence.baselines.types import BaselineFeatureVector
from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
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
from market_platform_foundation.intelligence.training import (
    CandidateStatus,
    TrainerKind,
    TrainingFactory,
    TrainingFactoryError,
    derive_candidate_id,
    derive_candidate_spec_id,
    derive_training_dataset_fingerprint,
)
from market_platform_foundation.intelligence.training.artifacts import verify_and_parse_logistic_artifact
from market_platform_foundation.intelligence.training.authorization import (
    holdout_boundary_ns,
    is_frontier_historical_teacher_blocked,
    validate_experiment_for_training,
)
from market_platform_foundation.intelligence.training.datasets import build_dataset_from_examples
from market_platform_foundation.intelligence.training.distillation import FixtureTeacher, build_distillation_dataset
from market_platform_foundation.intelligence.training.search import expand_candidate_specs
from market_platform_foundation.intelligence.training.trainers import get_trainer
from market_platform_foundation.intelligence.training.types import SupervisionKind
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.test_baseline_fixtures import default_target


def _feature_vector(values: tuple[float, ...]) -> BaselineFeatureVector:
    keys = tuple(f"f{i}" for i in range(len(values)))
    return BaselineFeatureVector(values=values, source_signals=(), feature_keys=keys)


def _synthetic_examples() -> list[BaselineTrainingExample]:
    schema_keys = ("f0",)
    examples = []
    for idx, (label, value) in enumerate(
        (
            (BaselineClassLabel.UP, 1.0),
            (BaselineClassLabel.DOWN, -1.0),
            (BaselineClassLabel.UP, 0.8),
            (BaselineClassLabel.DOWN, -0.5),
        )
    ):
        examples.append(
            BaselineTrainingExample(
                snapshot_id=f"snap-{idx}",
                decision_time_ns=T + idx,
                feature_vector=BaselineFeatureVector(
                    values=(value,), source_signals=(), feature_keys=schema_keys
                ),
                label=label,
                label_available_time_ns=T + HORIZON_5M,
                label_provenance="OUTCOME_LABEL",
            )
        )
    return examples


def _experiment_manifest(**overrides):
    treatment = ComponentMutationSpec(
        component="baseline_model",
        parameter="C",
        candidate_ref="1.0",
    )
    control = ComponentMutationSpec(
        component="baseline_model",
        parameter="C",
        baseline_ref="0.1",
    )
    footprint = ResearchKnowledgeFootprint(evaluation_report_ids=("rep",))
    hypothesis = build_research_hypothesis(
        title="model test",
        hypothesis_kind=ResearchHypothesisKind.MODEL_CHANGE,
        source_finding_ids=("f1",),
        claim="test",
        treatment=treatment,
        control=control,
        primary_metric="brier_score",
        expected_direction="decrease",
        falsification=FalsificationCriterion(description="no improvement"),
        knowledge_footprint=footprint,
        target_kind="direction_up_down",
        horizon_ns=HORIZON_5M,
        mode="ACTUAL_LIVE",
    )
    kwargs = {
        "hypothesis": hypothesis,
        "experiment_kind": ExperimentKind.MODEL_VARIANT,
        "treatment": treatment,
        "control": control,
        "data_spec": DataSpecification(
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
            decision_start_ns=T,
            decision_end_ns=T + 10,
        ),
        "metric_plan": MetricPlan(primary_metric="brier_score"),
        "success_criteria": "lower brier",
        "falsification": FalsificationCriterion(description="fail"),
        "knowledge_footprint": footprint,
        "allowed_changes": ("baseline_model",),
        "seed_policy": SeedPolicy(fixed_seeds=(11,)),
        "resource_budget": ResourceBudget(max_candidates=4, max_training_runs=4),
    }
    kwargs.update(overrides)
    return design_experiment(**kwargs)


class AuthorizationTests(unittest.TestCase):
    def test_forbidden_mutation_rejected(self) -> None:
        manifest = _experiment_manifest(
            forbidden_changes=("baseline_model",),
            allowed_changes=(),
        )
        with self.assertRaises(TrainingFactoryError) as ctx:
            validate_experiment_for_training(
                manifest,
                trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
                target_kind="direction_up_down",
                horizon_ns=HORIZON_5M,
                mode="ACTUAL_LIVE",
                hyperparameter_keys=frozenset({"C"}),
            )
        self.assertEqual(ctx.exception.code, "TRAINING_AUTHORIZATION_ERROR")

    def test_target_mismatch_rejected(self) -> None:
        manifest = _experiment_manifest()
        with self.assertRaises(TrainingFactoryError):
            validate_experiment_for_training(
                manifest,
                trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
                target_kind="wrong",
                horizon_ns=HORIZON_5M,
                mode="ACTUAL_LIVE",
            )

    def test_frontier_teacher_blocked(self) -> None:
        manifest = _experiment_manifest()
        blocked = ExperimentManifestV1(
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
            knowledge_footprint=manifest.knowledge_footprint,
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
            metadata={"requires_frontier_teacher_replay": True},
        )
        self.assertTrue(is_frontier_historical_teacher_blocked(blocked))


class DatasetFingerprintTests(unittest.TestCase):
    def test_fingerprint_deterministic(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = default_target()
        prepared_a = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        prepared_b = build_dataset_from_examples(
            experiment_id="exp",
            examples=list(reversed(_synthetic_examples())),
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        self.assertEqual(
            prepared_a.manifest.dataset_fingerprint,
            prepared_b.manifest.dataset_fingerprint,
        )

    def test_feature_change_changes_fingerprint(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = default_target()
        examples = _synthetic_examples()
        prepared_a = build_dataset_from_examples(
            experiment_id="exp",
            examples=examples,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        mutated = copy.deepcopy(examples)
        ex = mutated[0]
        mutated[0] = BaselineTrainingExample(
            snapshot_id=ex.snapshot_id,
            decision_time_ns=ex.decision_time_ns,
            feature_vector=BaselineFeatureVector(
                values=(99.0,), source_signals=(), feature_keys=ex.feature_vector.feature_keys
            ),
            label=ex.label,
            label_available_time_ns=ex.label_available_time_ns,
        )
        prepared_b = build_dataset_from_examples(
            experiment_id="exp",
            examples=mutated,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        self.assertNotEqual(
            prepared_a.manifest.dataset_fingerprint,
            prepared_b.manifest.dataset_fingerprint,
        )


class SearchExpansionTests(unittest.TestCase):
    def test_bounded_grid_order(self) -> None:
        manifest = _experiment_manifest(
            search_space=SearchSpaceSpec(parameters={"C": (0.1, 1.0)}),
            seed_policy=SeedPolicy(fixed_seeds=(11, 29)),
            resource_budget=ResourceBudget(max_candidates=10, max_training_runs=10),
        )
        specs = expand_candidate_specs(
            manifest,
            training_dataset_id="ds",
            dataset_fingerprint="TRDS-abc",
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            trainer_version="v1",
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
            base_hyperparameters={},
            authorized_mutation_surface=("baseline_model",),
        )
        self.assertEqual(len(specs), 4)
        self.assertEqual(specs[0].hyperparameters["C"], 0.1)
        self.assertEqual(specs[0].seed, 11)
        self.assertEqual(specs[1].hyperparameters["C"], 0.1)
        self.assertEqual(specs[1].seed, 29)

    def test_max_candidates_exceeded(self) -> None:
        manifest = _experiment_manifest(
            search_space=SearchSpaceSpec(parameters={"C": (0.1, 1.0, 10.0)}),
            seed_policy=SeedPolicy(fixed_seeds=(11, 29)),
            resource_budget=ResourceBudget(max_candidates=2),
        )
        with self.assertRaises(TrainingFactoryError):
            expand_candidate_specs(
                manifest,
                training_dataset_id="ds",
                dataset_fingerprint="TRDS-abc",
                trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
                trainer_version="v1",
                target_kind="direction_up_down",
                horizon_ns=HORIZON_5M,
                mode="ACTUAL_LIVE",
                base_hyperparameters={},
                authorized_mutation_surface=("baseline_model",),
            )


class LogisticTrainerTests(unittest.TestCase):
    def test_deterministic_parameters(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = default_target()
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        manifest = _experiment_manifest()
        spec_id = derive_candidate_spec_id(
            experiment_id=manifest.experiment_id,
            dataset_fingerprint=prepared.manifest.dataset_fingerprint,
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION.value,
            trainer_version="training-distillation-factory-v1",
            hyperparameters={"solver": "lbfgs", "max_iter": 1000, "random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
        )
        from market_platform_foundation.intelligence.training.types import CandidateTrainingSpec

        spec = CandidateTrainingSpec(
            candidate_spec_id=spec_id,
            experiment_id=manifest.experiment_id,
            training_dataset_id=prepared.manifest.training_dataset_id,
            dataset_fingerprint=prepared.manifest.dataset_fingerprint,
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            hyperparameters={"solver": "lbfgs", "max_iter": 1000, "random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )
        trainer = get_trainer(TrainerKind.LOGISTIC_REGRESSION)
        result_a = trainer.train(spec, prepared)
        result_b = trainer.train(spec, prepared)
        assert result_a.candidate is not None and result_b.candidate is not None
        self.assertEqual(
            result_a.candidate.parameter_fingerprint,
            result_b.candidate.parameter_fingerprint,
        )
        self.assertEqual(result_a.candidate.artifact_hash, result_b.candidate.artifact_hash)

    def test_single_class_rejected(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = default_target()
        examples = [
            BaselineTrainingExample(
                snapshot_id="s1",
                decision_time_ns=T,
                feature_vector=_feature_vector((1.0,)),
                label=BaselineClassLabel.UP,
                label_available_time_ns=T + HORIZON_5M,
            ),
            BaselineTrainingExample(
                snapshot_id="s2",
                decision_time_ns=T + 1,
                feature_vector=_feature_vector((0.5,)),
                label=BaselineClassLabel.UP,
                label_available_time_ns=T + HORIZON_5M,
            ),
        ]
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=examples,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        from market_platform_foundation.intelligence.training.types import CandidateTrainingSpec

        spec = CandidateTrainingSpec(
            candidate_spec_id="csp-test",
            experiment_id="exp",
            training_dataset_id=prepared.manifest.training_dataset_id,
            dataset_fingerprint=prepared.manifest.dataset_fingerprint,
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            hyperparameters={"random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )
        with self.assertRaises(TrainingFactoryError):
            get_trainer(TrainerKind.LOGISTIC_REGRESSION).train(spec, prepared)

    def test_artifact_hash_verification(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        from market_platform_foundation.intelligence.training.types import CandidateTrainingSpec

        spec = CandidateTrainingSpec(
            candidate_spec_id="csp",
            experiment_id="exp",
            training_dataset_id=prepared.manifest.training_dataset_id,
            dataset_fingerprint=prepared.manifest.dataset_fingerprint,
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            hyperparameters={"random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )
        result = get_trainer(TrainerKind.LOGISTIC_REGRESSION).train(spec, prepared)
        assert result.candidate is not None and result.artifact_bytes is not None
        payload = verify_and_parse_logistic_artifact(
            result.artifact_bytes, result.candidate.artifact_hash
        )
        self.assertEqual(payload["model_kind"], "logistic-regression")


class CandidateIdentityTests(unittest.TestCase):
    def test_same_spec_same_candidate_id(self) -> None:
        from market_platform_foundation.intelligence.training.types import CandidateTrainingSpec

        spec = CandidateTrainingSpec(
            candidate_spec_id="csp-1",
            experiment_id="exp",
            training_dataset_id="ds",
            dataset_fingerprint="TRDS-x",
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            hyperparameters={"random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
        )
        self.assertEqual(derive_candidate_id(spec), derive_candidate_id(spec))

    def test_development_status_unvalidated(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        from market_platform_foundation.intelligence.training.types import CandidateTrainingSpec

        spec = CandidateTrainingSpec(
            candidate_spec_id="csp",
            experiment_id="exp",
            training_dataset_id=prepared.manifest.training_dataset_id,
            dataset_fingerprint=prepared.manifest.dataset_fingerprint,
            trainer_kind=TrainerKind.LOGISTIC_REGRESSION,
            hyperparameters={"random_state": 11},
            seed=11,
            authorized_mutation_surface=("baseline_model",),
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )
        result = get_trainer(TrainerKind.LOGISTIC_REGRESSION).train(spec, prepared)
        assert result.candidate is not None
        self.assertEqual(result.candidate.status, CandidateStatus.UNVALIDATED)


class DistillationTests(unittest.TestCase):
    def test_teacher_not_market_truth(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = direction_up_down_target("TEST")
        teacher = FixtureTeacher()
        inputs = [
            ("s1", T, _feature_vector((1.0,)), T + HORIZON_5M),
            ("s2", T + 1, _feature_vector((-1.0,)), T + HORIZON_5M),
        ]
        prepared, dist_manifest = build_distillation_dataset(
            experiment_id="exp",
            teacher=teacher,
            input_examples=inputs,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            mode="ACTUAL_LIVE",
            horizon_ns=HORIZON_5M,
        )
        self.assertEqual(prepared.manifest.supervision_kind, SupervisionKind.TEACHER_TARGET)
        self.assertEqual(dist_manifest.teacher_id, teacher.teacher_id)

    def test_teacher_version_changes_fingerprint(self) -> None:
        schema = BaselineFeatureSchema(selectors=())
        target = direction_up_down_target("TEST")
        inputs = [("s1", T, _feature_vector((1.0,)), T + HORIZON_5M)]
        teacher_a = FixtureTeacher()
        teacher_b = FixtureTeacher()
        object.__setattr__(teacher_b, "teacher_version", "v2")
        _, manifest_a = build_distillation_dataset(
            experiment_id="exp",
            teacher=teacher_a,
            input_examples=inputs,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            mode="ACTUAL_LIVE",
            horizon_ns=HORIZON_5M,
        )
        _, manifest_b = build_distillation_dataset(
            experiment_id="exp",
            teacher=teacher_b,
            input_examples=inputs,
            feature_schema=schema,
            target=target,
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            mode="ACTUAL_LIVE",
            horizon_ns=HORIZON_5M,
        )
        self.assertNotEqual(manifest_a.dataset_fingerprint, manifest_b.dataset_fingerprint)


class HoldoutSafetyTests(unittest.TestCase):
    def test_holdout_boundary_declared(self) -> None:
        base = _experiment_manifest(
            validation_requirements=ValidationRequirements(requires_locked_holdout=True),
        )
        manifest = ExperimentManifestV1(
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
            validation_requirements=ValidationRequirements(requires_locked_holdout=True),
            guardrails=base.guardrails,
            search_space=base.search_space,
            seed_policy=base.seed_policy,
            complexity_budget=base.complexity_budget,
            resource_budget=base.resource_budget,
            allowed_changes=base.allowed_changes,
            forbidden_changes=base.forbidden_changes,
            evaluation_spec_id=base.evaluation_spec_id,
            implementation_version=base.implementation_version,
            metadata={"holdout_start_ns": T + 5},
        )
        self.assertEqual(holdout_boundary_ns(manifest), T + 5)


class PersistenceTests(unittest.TestCase):
    def test_dataset_manifest_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        schema = BaselineFeatureSchema(selectors=())
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        first = repo.put_training_dataset_manifest(prepared.manifest)
        second = repo.put_training_dataset_manifest(prepared.manifest)
        self.assertEqual(first, RepositoryPutResult.INSERTED)
        self.assertEqual(second, RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_on_changed_content(self) -> None:
        repo = InMemoryIntelligenceRepository()
        schema = BaselineFeatureSchema(selectors=())
        prepared = build_dataset_from_examples(
            experiment_id="exp",
            examples=_synthetic_examples(),
            feature_schema=schema,
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + 10,
            horizon_ns=HORIZON_5M,
        )
        repo.put_training_dataset_manifest(prepared.manifest)
        mutated = copy.deepcopy(prepared.manifest)
        object.__setattr__(mutated, "example_count", 999)
        with self.assertRaises(RepositoryConflictError):
            repo.put_training_dataset_manifest(mutated)


class Build01To18LifecycleTests(unittest.TestCase):
    def test_research_to_candidate_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        manifest = _experiment_manifest(
            search_space=SearchSpaceSpec(parameters={"C": (1.0,)}),
            seed_policy=SeedPolicy(fixed_seeds=(11,)),
            resource_budget=ResourceBudget(max_candidates=1, max_training_runs=1),
        )
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
        self.assertEqual(len(specs), 1)

        with tempfile.TemporaryDirectory() as tmp:
            factory = TrainingFactory(repo, artifact_base_dir=Path(tmp))
            trainer = get_trainer(TrainerKind.LOGISTIC_REGRESSION)
            result = trainer.train(specs[0], prepared)
            assert result.candidate is not None
            repo.put_training_run_manifest(result.run)
            repo.put_candidate_artifact(result.candidate)

            stored = repo.get_candidate_artifact(result.candidate.candidate_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.status, CandidateStatus.UNVALIDATED)

            # Production immutability: no champion fields
            self.assertNotIn("CHAMPION", stored.status.value)
            self.assertNotIn("PRODUCTION", stored.status.value)


if __name__ == "__main__":
    unittest.main()
