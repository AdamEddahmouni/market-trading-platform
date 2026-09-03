"""Logistic regression candidate trainer (BUILD 18)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ...baselines.errors import BaselineTrainingError
from ...baselines.identity import parameter_fingerprint_from_payload
from ...baselines.types import BaselineClassLabel
from ...contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..artifacts import serialize_logistic_artifact
from ..errors import TrainingFactoryError
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

DEFAULT_LOGISTIC_HYPERPARAMETERS: dict[str, Any] = {
    "solver": "lbfgs",
    "max_iter": 1000,
}


class SklearnLogisticCandidateTrainer:
    trainer_kind = TrainerKind.LOGISTIC_REGRESSION
    trainer_version = TRAINING_IMPLEMENTATION_VERSION

    def train(
        self,
        spec: CandidateTrainingSpec,
        dataset: PreparedTrainingDataset,
    ) -> CandidateTrainingResult:
        baseline_dataset = dataset.baseline_dataset
        hyperparams = dict(DEFAULT_LOGISTIC_HYPERPARAMETERS)
        hyperparams.update(
            {k: v for k, v in spec.hyperparameters.items() if k != "random_state"}
        )
        seed = int(spec.hyperparameters.get("random_state", spec.seed))

        try:
            if len(baseline_dataset.examples) < 2:
                raise BaselineTrainingError("INSUFFICIENT_TRAINING_EXAMPLES")
            labels = [example.label for example in baseline_dataset.examples]
            up_count = sum(1 for label in labels if label == BaselineClassLabel.UP)
            down_count = len(labels) - up_count
            if up_count == 0 or down_count == 0:
                raise BaselineTrainingError("SINGLE_CLASS_TRAINING_DATA")

            x_rows = [list(example.feature_vector.values) for example in baseline_dataset.examples]
            y_rows = [1 if label == BaselineClassLabel.UP else 0 for label in labels]
            pipeline = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            solver=str(hyperparams["solver"]),
                            max_iter=int(hyperparams["max_iter"]),
                            random_state=seed,
                        ),
                    ),
                ]
            )
            pipeline.fit(np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int))
            classifier: LogisticRegression = pipeline.named_steps["classifier"]
            scaler: StandardScaler = pipeline.named_steps["scaler"]
            feature_keys = list(baseline_dataset.examples[0].feature_vector.feature_keys)
            param_fp = parameter_fingerprint_from_payload(
                {
                    "coefficients": classifier.coef_.tolist(),
                    "intercept": classifier.intercept_.tolist(),
                    "classes": classifier.classes_.tolist(),
                    "scaler_mean": scaler.mean_.tolist(),
                    "scaler_scale": scaler.scale_.tolist(),
                    "hyperparameters": hyperparams,
                    "seed": seed,
                }
            )
            artifact_bytes = serialize_logistic_artifact(
                coefficients=classifier.coef_.tolist(),
                intercept=classifier.intercept_.tolist(),
                classes=classifier.classes_.tolist(),
                scaler_mean=scaler.mean_.tolist(),
                scaler_scale=scaler.scale_.tolist(),
                hyperparameters=hyperparams,
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
                convergence_status="converged",
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
                model_family="logistic-regression",
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
                    "candidate_spec_id": spec.candidate_spec_id,
                },
            )
            return CandidateTrainingResult(
                run=run, candidate=candidate, artifact_bytes=artifact_bytes
            )
        except BaselineTrainingError as exc:
            run_id = derive_training_run_id(
                candidate_spec_id=spec.candidate_spec_id,
                trainer_version=self.trainer_version,
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
                status=TrainingRunStatus.FAILED,
                metadata={"error": str(exc)},
            )
            raise TrainingFactoryError(str(exc)) from exc


register_trainer(TrainerKind.LOGISTIC_REGRESSION, SklearnLogisticCandidateTrainer)

__all__ = ["DEFAULT_LOGISTIC_HYPERPARAMETERS", "SklearnLogisticCandidateTrainer"]
