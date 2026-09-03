"""Gradient boosting candidate trainer (BUILD 18)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from ...baselines.errors import BaselineTrainingError
from ...baselines.identity import parameter_fingerprint_from_payload
from ...baselines.types import BaselineClassLabel
from ...contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..artifacts import serialize_logistic_artifact
from ..identity import artifact_content_hash, derive_candidate_id, derive_training_run_id
from ..types import (
    CandidateArtifactV1,
    CandidateStatus,
    CandidateTrainingResult,
    CandidateTrainingSpec,
    PreparedTrainingDataset,
    TrainerKind,
    TrainingDiagnostics,
    TrainingRunManifestV1,
    TrainingRunStatus,
    TRAINING_IMPLEMENTATION_VERSION,
)
from .base import register_trainer

DEFAULT_GBM_HYPERPARAMETERS: dict[str, Any] = {
    "n_estimators": 50,
    "max_depth": 3,
    "learning_rate": 0.1,
}


class SklearnGbmCandidateTrainer:
    trainer_kind = TrainerKind.GRADIENT_BOOSTING
    trainer_version = TRAINING_IMPLEMENTATION_VERSION

    def train(
        self,
        spec: CandidateTrainingSpec,
        dataset: PreparedTrainingDataset,
    ) -> CandidateTrainingResult:
        baseline_dataset = dataset.baseline_dataset
        hyperparams = dict(DEFAULT_GBM_HYPERPARAMETERS)
        hyperparams.update(
            {k: v for k, v in spec.hyperparameters.items() if k != "random_state"}
        )
        seed = int(spec.hyperparameters.get("random_state", spec.seed))

        if len(baseline_dataset.examples) < 2:
            raise BaselineTrainingError("INSUFFICIENT_TRAINING_EXAMPLES")
        labels = [example.label for example in baseline_dataset.examples]
        up_count = sum(1 for label in labels if label == BaselineClassLabel.UP)
        down_count = len(labels) - up_count
        if up_count == 0 or down_count == 0:
            raise BaselineTrainingError("SINGLE_CLASS_TRAINING_DATA")

        x_rows = [list(example.feature_vector.values) for example in baseline_dataset.examples]
        y_rows = [1 if label == BaselineClassLabel.UP else 0 for label in labels]
        estimator = GradientBoostingClassifier(
            n_estimators=int(hyperparams["n_estimators"]),
            max_depth=int(hyperparams["max_depth"]),
            learning_rate=float(hyperparams["learning_rate"]),
            random_state=seed,
        )
        estimator.fit(np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int))
        feature_keys = list(baseline_dataset.examples[0].feature_vector.feature_keys)
        param_fp = parameter_fingerprint_from_payload(
            {
                "feature_importances": estimator.feature_importances_.tolist(),
                "n_estimators": estimator.n_estimators,
                "max_depth": hyperparams["max_depth"],
                "learning_rate": hyperparams["learning_rate"],
                "seed": seed,
            }
        )
        artifact_bytes = serialize_logistic_artifact(
            coefficients=[estimator.feature_importances_.tolist()],
            intercept=[float(estimator.n_estimators)],
            classes=estimator.classes_.tolist(),
            scaler_mean=[],
            scaler_scale=[],
            hyperparameters={**hyperparams, "model_kind": "gradient-boosting"},
            feature_keys=feature_keys,
        )
        artifact_hash = artifact_content_hash(artifact_bytes)
        candidate_id = derive_candidate_id(spec)
        run_id = derive_training_run_id(
            candidate_spec_id=spec.candidate_spec_id,
            trainer_version=self.trainer_version,
        )
        diagnostics = TrainingDiagnostics(
            example_count=len(baseline_dataset.examples),
            up_count=up_count,
            down_count=down_count,
        )
        run = TrainingRunManifestV1(
            training_run_id=run_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            experiment_id=spec.experiment_id,
            candidate_spec_id=spec.candidate_spec_id,
            training_dataset_id=spec.training_dataset_id,
            dataset_fingerprint=spec.dataset_fingerprint,
            trainer_kind=self.trainer_kind,
            trainer_version=self.trainer_version,
            hyperparameters=spec.hyperparameters,
            seed=seed,
            status=TrainingRunStatus.COMPLETED,
            candidate_id=candidate_id,
            diagnostics=diagnostics,
        )
        candidate = CandidateArtifactV1(
            candidate_id=candidate_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            experiment_id=spec.experiment_id,
            training_run_id=run_id,
            candidate_spec_id=spec.candidate_spec_id,
            training_dataset_id=spec.training_dataset_id,
            dataset_fingerprint=spec.dataset_fingerprint,
            candidate_kind=self.trainer_kind,
            model_family="gradient-boosting",
            artifact_format="sklearn-json-v1",
            artifact_hash=artifact_hash,
            parameter_fingerprint=param_fp,
            trainer_version=self.trainer_version,
            target_kind=spec.target_kind,
            horizon_ns=spec.horizon_ns,
            input_schema_fingerprint=dataset.manifest.feature_schema_fingerprint,
            seed=seed,
            status=CandidateStatus.UNVALIDATED,
            supervision_kind=dataset.manifest.supervision_kind,
            lineage={
                "experiment_id": spec.experiment_id,
                "dataset_fingerprint": spec.dataset_fingerprint,
            },
        )
        return CandidateTrainingResult(run=run, candidate=candidate, artifact_bytes=artifact_bytes)


register_trainer(TrainerKind.GRADIENT_BOOSTING, SklearnGbmCandidateTrainer)

__all__ = ["DEFAULT_GBM_HYPERPARAMETERS", "SklearnGbmCandidateTrainer"]
