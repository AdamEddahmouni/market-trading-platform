"""PIT-legal Path A PRODUCTION logistic specialist.

Fits a serializable logistic on snapshot-bound 5m momentum and net-signed-share
signals. Parameters are JSON data, not pickle. This is not a BUILD 08
control floor and does not construct CONTROL ForecastV1 records.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ..baselines.features import FeatureVectorBuilder
from ..baselines.types import BaselineFeatureVector
from ..contracts.common import ForecastTarget, TimeHorizonNs, QualityState
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from .errors import ProductionTrainingError
from .identity import (
    MINIMUM_SPECIALIST_CLASS_COUNT,
    MINIMUM_SPECIALIST_SAMPLES,
    PATH_A_PRODUCTION_FEATURE_SCHEMA,
    PRODUCTION_MODEL_KIND,
    PRODUCTION_MODEL_VERSION,
    derive_dataset_fingerprint,
    derive_model_id,
    matches_path_a_identity,
    parameter_fingerprint,
)

LOGISTIC_HYPERPARAMETERS: dict[str, Any] = {
    "solver": "lbfgs",
    "max_iter": 1000,
    "random_state": 7,
}


@dataclass(frozen=True, slots=True)
class ProductionTrainingExample:
    snapshot: SnapshotV1
    signals: tuple[SignalV1, ...]
    label: int
    label_available_time_ns: int


@dataclass(frozen=True, slots=True)
class ProductionSpecialistModel:
    """Fitted PRODUCTION specialist. Predict is a pure function of stored params."""

    model_id: str
    model_kind: str
    implementation_version: str
    feature_schema_fingerprint: str
    target: ForecastTarget
    horizon: TimeHorizonNs
    training_dataset_fingerprint: str
    training_cutoff_ns: int
    hyperparameters: dict[str, Any]
    parameter_fingerprint: str
    parameters: dict[str, Any]
    sample_count: int
    class_counts: dict[str, int]

    def predict_probability_up(self, features: BaselineFeatureVector) -> float:
        mean = np.asarray(self.parameters["scaler_mean"], dtype=float)
        scale = np.asarray(self.parameters["scaler_scale"], dtype=float)
        coef = np.asarray(self.parameters["coef"], dtype=float)
        intercept = float(self.parameters["intercept"])
        values = np.asarray(list(features.values), dtype=float)
        if values.shape != mean.shape:
            raise ProductionTrainingError("FEATURE_DIMENSION_MISMATCH")
        z = (values - mean) / scale
        logit = float(intercept + float(np.dot(coef, z)))
        probability = 1.0 / (1.0 + math.exp(-logit))
        if not math.isfinite(probability):
            raise ProductionTrainingError("MODEL_OUTPUT_NOT_FINITE")
        return min(1.0, max(0.0, probability))


def _extract_features(
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...] | list[SignalV1],
) -> BaselineFeatureVector | None:
    vector, diagnostics = FeatureVectorBuilder(PATH_A_PRODUCTION_FEATURE_SCHEMA).extract(
        snapshot,
        signals,
        allow_degraded=False,
    )
    if vector is None or diagnostics:
        return None
    return vector


def _normalize_examples(
    examples: list[ProductionTrainingExample],
    *,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    training_cutoff_ns: int,
) -> tuple[tuple[BaselineFeatureVector, int, ProductionTrainingExample], ...]:
    identity_reasons = matches_path_a_identity(target=target, horizon=horizon)
    if identity_reasons:
        raise ProductionTrainingError(",".join(identity_reasons))
    by_key: dict[tuple[str, int], ProductionTrainingExample] = {}
    extracted: list[tuple[BaselineFeatureVector, int, ProductionTrainingExample]] = []
    for example in examples:
        if example.label not in (0, 1):
            raise ProductionTrainingError("INVALID_LABEL")
        if example.label_available_time_ns <= example.snapshot.decision_time_ns:
            raise ProductionTrainingError("LABEL_AVAILABLE_BEFORE_FORECAST")
        if example.label_available_time_ns < example.snapshot.decision_time_ns + horizon.duration_ns:
            raise ProductionTrainingError("LABEL_AVAILABLE_BEFORE_HORIZON_COMPLETION")
        if example.label_available_time_ns > training_cutoff_ns:
            raise ProductionTrainingError("FUTURE_LABEL_PAST_CUTOFF")
        if example.snapshot.quality.state == QualityState.INVALID:
            raise ProductionTrainingError("SNAPSHOT_QUALITY_REJECTED")
        vector = _extract_features(example.snapshot, example.signals)
        if vector is None:
            raise ProductionTrainingError("TRAINING_FEATURE_EXTRACTION_FAILED")
        key = (example.snapshot.snapshot_id, example.snapshot.decision_time_ns)
        existing = by_key.get(key)
        if existing is not None:
            if existing.label != example.label:
                raise ProductionTrainingError("CONFLICTING_TRAINING_LABELS")
            continue
        by_key[key] = example
        extracted.append((vector, example.label, example))
    extracted.sort(key=lambda row: (row[2].snapshot.decision_time_ns, row[2].snapshot.snapshot_id))
    return tuple(extracted)


def fit_production_specialist(
    examples: list[ProductionTrainingExample],
    *,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    training_cutoff_ns: int,
) -> ProductionSpecialistModel | None:
    """Fit a Path A PRODUCTION specialist. Insufficient support → None."""

    normalized = _normalize_examples(
        examples,
        target=target,
        horizon=horizon,
        training_cutoff_ns=training_cutoff_ns,
    )
    if len(normalized) < MINIMUM_SPECIALIST_SAMPLES:
        return None
    labels = [label for _vector, label, _example in normalized]
    class_0 = sum(1 for label in labels if label == 0)
    class_1 = sum(1 for label in labels if label == 1)
    if class_0 < MINIMUM_SPECIALIST_CLASS_COUNT or class_1 < MINIMUM_SPECIALIST_CLASS_COUNT:
        return None

    x_rows = [list(vector.values) for vector, _label, _example in normalized]
    y_rows = [label for _vector, label, _example in normalized]
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(np.asarray(x_rows, dtype=float))
    classifier = LogisticRegression(
        solver=str(LOGISTIC_HYPERPARAMETERS["solver"]),
        max_iter=int(LOGISTIC_HYPERPARAMETERS["max_iter"]),
        random_state=int(LOGISTIC_HYPERPARAMETERS["random_state"]),
    )
    classifier.fit(x_scaled, np.asarray(y_rows, dtype=int))
    parameters = {
        "coef": [float(value) for value in classifier.coef_.reshape(-1)],
        "intercept": float(classifier.intercept_[0]),
        "scaler_mean": [float(value) for value in scaler.mean_],
        "scaler_scale": [float(value) for value in scaler.scale_],
        "classes": [int(value) for value in classifier.classes_],
    }
    canonical_examples = [
        {
            "snapshot_id": example.snapshot.snapshot_id,
            "decision_time_ns": example.snapshot.decision_time_ns,
            "feature_values": list(vector.values),
            "label": label,
            "label_available_time_ns": example.label_available_time_ns,
        }
        for vector, label, example in normalized
    ]
    dataset_fp = derive_dataset_fingerprint(
        feature_schema_fingerprint=PATH_A_PRODUCTION_FEATURE_SCHEMA.fingerprint,
        target=target,
        training_cutoff_ns=training_cutoff_ns,
        examples=canonical_examples,
    )
    param_fp = parameter_fingerprint(parameters)
    model_id = derive_model_id(
        model_kind=PRODUCTION_MODEL_KIND,
        implementation_version=PRODUCTION_MODEL_VERSION,
        feature_schema_fingerprint=PATH_A_PRODUCTION_FEATURE_SCHEMA.fingerprint,
        target=target,
        training_dataset_fingerprint=dataset_fp,
        training_cutoff_ns=training_cutoff_ns,
        hyperparameters=LOGISTIC_HYPERPARAMETERS,
    )
    return ProductionSpecialistModel(
        model_id=model_id,
        model_kind=PRODUCTION_MODEL_KIND,
        implementation_version=PRODUCTION_MODEL_VERSION,
        feature_schema_fingerprint=PATH_A_PRODUCTION_FEATURE_SCHEMA.fingerprint,
        target=target,
        horizon=horizon,
        training_dataset_fingerprint=dataset_fp,
        training_cutoff_ns=training_cutoff_ns,
        hyperparameters=dict(LOGISTIC_HYPERPARAMETERS),
        parameter_fingerprint=param_fp,
        parameters=parameters,
        sample_count=len(normalized),
        class_counts={"0": class_0, "1": class_1},
    )


__all__ = [
    "LOGISTIC_HYPERPARAMETERS",
    "ProductionSpecialistModel",
    "ProductionTrainingExample",
    "fit_production_specialist",
]
