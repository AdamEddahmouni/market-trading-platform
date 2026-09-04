"""Gradient boosting baseline (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from ...contracts.common import ForecastTarget
from ..errors import BaselineTrainingError
from ..features import BaselineFeatureSchema, DEFAULT_STATISTICAL_FEATURE_SCHEMA
from ..identity import derive_model_id, parameter_fingerprint_from_payload
from ..training import BaselineTrainingDataset
from ..types import (
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineModelDescriptor,
    BaselineModelOutput,
    BaselinePredictionContext,
    FitSummary,
    PredictionDiagnosticCode,
)

GBM_HYPERPARAMETERS: dict[str, Any] = {
    "n_estimators": 50,
    "max_depth": 3,
    "learning_rate": 0.1,
    "random_state": 42,
}


@dataclass
class GradientBoostingBaseline:
    feature_schema: BaselineFeatureSchema = field(default_factory=lambda: DEFAULT_STATISTICAL_FEATURE_SCHEMA)
    hyperparameters: dict[str, Any] = field(default_factory=lambda: dict(GBM_HYPERPARAMETERS))
    model_kind: str = "gradient-boosting"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        self._estimator: GradientBoostingClassifier | None = None
        self._descriptor: BaselineModelDescriptor | None = None

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_FITTED")
        return self._descriptor

    def fit(self, dataset: BaselineTrainingDataset) -> FitSummary:
        if len(dataset.examples) < 2:
            raise BaselineTrainingError("INSUFFICIENT_TRAINING_EXAMPLES")
        labels = [example.label for example in dataset.examples]
        up_count = sum(1 for label in labels if label == BaselineClassLabel.UP)
        down_count = len(labels) - up_count
        if up_count == 0 or down_count == 0:
            raise BaselineTrainingError("SINGLE_CLASS_TRAINING_DATA")
        x_rows = [list(example.feature_vector.values) for example in dataset.examples]
        y_rows = [1 if label == BaselineClassLabel.UP else 0 for label in labels]
        estimator = GradientBoostingClassifier(
            n_estimators=int(self.hyperparameters["n_estimators"]),
            max_depth=int(self.hyperparameters["max_depth"]),
            learning_rate=float(self.hyperparameters["learning_rate"]),
            random_state=int(self.hyperparameters["random_state"]),
        )
        estimator.fit(np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int))
        self._estimator = estimator
        param_fp = parameter_fingerprint_from_payload(
            {
                "n_estimators": estimator.n_estimators_,
                "classes": estimator.classes_.tolist(),
                "feature_importances": estimator.feature_importances_.tolist(),
                "hyperparameters": self.hyperparameters,
            }
        )
        self._descriptor = BaselineModelDescriptor(
            model_id=derive_model_id(
                model_kind=self.model_kind,
                implementation_version=self.implementation_version,
                feature_schema_fingerprint_value=self.feature_schema.fingerprint,
                target=dataset.target,
                training_dataset_fingerprint=dataset.fingerprint,
                training_cutoff_ns=dataset.training_cutoff_ns,
                hyperparameters=self.hyperparameters,
                seed=int(self.hyperparameters["random_state"]),
            ),
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            feature_schema_fingerprint=self.feature_schema.fingerprint,
            target=dataset.target,
            training_dataset_fingerprint=dataset.fingerprint,
            training_cutoff_ns=dataset.training_cutoff_ns,
            hyperparameters=self.hyperparameters,
            parameter_fingerprint=param_fp,
            seed=int(self.hyperparameters["random_state"]),
            class_mapping={"UP": 1, "DOWN": 0},
        )
        return FitSummary(
            model_id=self._descriptor.model_id,
            dataset_fingerprint=dataset.fingerprint,
            example_count=len(dataset.examples),
            up_count=up_count,
            down_count=down_count,
            feature_count=len(self.feature_schema.selectors),
            training_cutoff_ns=dataset.training_cutoff_ns,
            parameter_fingerprint=param_fp,
        )

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = context
        if self._estimator is None:
            return BaselineModelOutput(
                abstain=True,
                abstain_reason=PredictionDiagnosticCode.MODEL_NOT_FITTED,
            )
        probabilities = self._estimator.predict_proba(
            np.asarray([list(features.values)], dtype=float)
        )[0]
        up_index = list(self._estimator.classes_).index(1)
        p_up = float(probabilities[up_index])
        predicted = BaselineClassLabel.UP if p_up >= 0.5 else BaselineClassLabel.DOWN
        return BaselineModelOutput(
            predicted_class=predicted,
            raw_score=p_up,
            raw_probability_up=p_up,
        )


__all__ = ["GBM_HYPERPARAMETERS", "GradientBoostingBaseline"]
