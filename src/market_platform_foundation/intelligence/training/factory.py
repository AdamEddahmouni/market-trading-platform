"""Training factory orchestrator (BUILD 18)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..persistence.repository import IntelligenceRepository
from ..research_experiments.types import ExperimentManifestV1, ResearchLifecycleState
from .artifacts import write_artifact_file
from .authorization import (
    is_frontier_historical_teacher_blocked,
    validate_experiment_for_training,
)
from .datasets import materialize_development_dataset
from .errors import TrainingFactoryError
from .search import expand_candidate_specs
from .trainers.base import get_trainer
from .types import (
    CandidateArtifactV1,
    TrainerKind,
    TrainingFactoryResult,
    TrainingRunManifestV1,
    TrainingRunStatus,
    TRAINING_IMPLEMENTATION_VERSION,
)

# Register trainers on import
from .trainers import sklearn_gbm  # noqa: F401
from .trainers import sklearn_logistic  # noqa: F401


class TrainingFactory:
    """Generates unvalidated development candidates from pre-registered experiments."""

    def __init__(
        self,
        repository: IntelligenceRepository,
        *,
        artifact_base_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_base_dir = artifact_base_dir or Path("artifacts/intelligence")

    def generate_candidates(
        self,
        manifest: ExperimentManifestV1,
        *,
        trainer_kind: TrainerKind = TrainerKind.LOGISTIC_REGRESSION,
        base_hyperparameters: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> TrainingFactoryResult:
        if is_frontier_historical_teacher_blocked(manifest):
            raise TrainingFactoryError(
                "VALIDATION_BLOCKED_PENDING_BUILD19",
                details={"reason": "frontier_historical_teacher_requires_tkw"},
            )

        stored = self.repository.get_experiment_manifest(manifest.experiment_id)
        if stored is None:
            raise TrainingFactoryError("EXPERIMENT_NOT_FOUND")

        prepared = materialize_development_dataset(self.repository, manifest)
        dataset_manifest = prepared.manifest

        validate_experiment_for_training(
            manifest,
            trainer_kind=trainer_kind,
            target_kind=dataset_manifest.target_kind,
            horizon_ns=dataset_manifest.horizon_ns,
            mode=dataset_manifest.mode,
            scenario_id=dataset_manifest.scenario_id,
            hyperparameter_keys=frozenset((manifest.search_space.parameters.keys() if manifest.search_space else [])),
        )

        if persist:
            self.repository.put_training_dataset_manifest(dataset_manifest)

        authorized_surface = manifest.allowed_changes or (manifest.treatment.component,)
        specs = expand_candidate_specs(
            manifest,
            training_dataset_id=dataset_manifest.training_dataset_id,
            dataset_fingerprint=dataset_manifest.dataset_fingerprint,
            trainer_kind=trainer_kind,
            trainer_version=TRAINING_IMPLEMENTATION_VERSION,
            target_kind=dataset_manifest.target_kind,
            horizon_ns=dataset_manifest.horizon_ns,
            mode=dataset_manifest.mode,
            base_hyperparameters=base_hyperparameters or {},
            authorized_mutation_surface=authorized_surface,
        )

        trainer = get_trainer(trainer_kind)
        candidates: list[CandidateArtifactV1] = []
        runs: list[TrainingRunManifestV1] = []

        for spec in specs:
            try:
                result = trainer.train(spec, prepared)
            except TrainingFactoryError:
                raise
            except Exception as exc:
                run = TrainingRunManifestV1(
                    training_run_id=f"failed-{spec.candidate_spec_id}",
                    schema_version=INTELLIGENCE_SCHEMA_VERSION,
                    experiment_id=spec.experiment_id,
                    candidate_spec_id=spec.candidate_spec_id,
                    training_dataset_id=spec.training_dataset_id,
                    dataset_fingerprint=spec.dataset_fingerprint,
                    trainer_kind=trainer_kind,
                    trainer_version=TRAINING_IMPLEMENTATION_VERSION,
                    hyperparameters=spec.hyperparameters,
                    seed=spec.seed,
                    status=TrainingRunStatus.FAILED,
                    metadata={"error": str(exc)},
                )
                runs.append(run)
                if persist:
                    self.repository.put_training_run_manifest(run)
                continue

            if result.candidate is not None and result.artifact_bytes is not None:
                artifact_ref = write_artifact_file(
                    base_dir=self.artifact_base_dir,
                    candidate_id=result.candidate.candidate_id,
                    content=result.artifact_bytes,
                )
                candidate = CandidateArtifactV1(
                    candidate_id=result.candidate.candidate_id,
                    schema_version=result.candidate.schema_version,
                    experiment_id=result.candidate.experiment_id,
                    training_run_id=result.candidate.training_run_id,
                    candidate_spec_id=result.candidate.candidate_spec_id,
                    training_dataset_id=result.candidate.training_dataset_id,
                    dataset_fingerprint=result.candidate.dataset_fingerprint,
                    candidate_kind=result.candidate.candidate_kind,
                    model_family=result.candidate.model_family,
                    artifact_format=result.candidate.artifact_format,
                    artifact_hash=result.candidate.artifact_hash,
                    parameter_fingerprint=result.candidate.parameter_fingerprint,
                    trainer_version=result.candidate.trainer_version,
                    target_kind=result.candidate.target_kind,
                    horizon_ns=result.candidate.horizon_ns,
                    input_schema_fingerprint=result.candidate.input_schema_fingerprint,
                    seed=result.candidate.seed,
                    status=result.candidate.status,
                    supervision_kind=result.candidate.supervision_kind,
                    artifact_ref=artifact_ref,
                    lineage=result.candidate.lineage,
                )
                candidates.append(candidate)
                if persist:
                    self.repository.put_training_run_manifest(result.run)
                    self.repository.put_candidate_artifact(candidate)
                runs.append(result.run)
            else:
                runs.append(result.run)
                if persist:
                    self.repository.put_training_run_manifest(result.run)

        return TrainingFactoryResult(
            experiment_id=manifest.experiment_id,
            dataset_manifest=dataset_manifest,
            candidates=tuple(candidates),
            runs=tuple(runs),
        )


__all__ = ["TrainingFactory"]
