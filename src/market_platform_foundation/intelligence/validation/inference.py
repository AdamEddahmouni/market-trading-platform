"""Validation-only candidate inference (BUILD 19)."""

from __future__ import annotations

import math
from typing import Any

from ..baselines.types import BaselineFeatureVector
from ..training.types import CandidateArtifactV1, TrainerKind
from .artifacts import load_verified_logistic_artifact
from .errors import ValidationError


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _scale_features(values: list[float], mean: list[float], scale: list[float]) -> list[float]:
    scaled: list[float] = []
    for value, mu, sigma in zip(values, mean, scale, strict=True):
        if sigma == 0:
            scaled.append(0.0)
        else:
            scaled.append((value - mu) / sigma)
    return scaled


def predict_logistic_probability(
    artifact: dict[str, Any],
    feature_vector: BaselineFeatureVector,
) -> float:
    feature_keys = artifact.get("feature_keys", [])
    if tuple(feature_keys) != feature_vector.feature_keys:
        raise ValidationError(
            "FEATURE_SCHEMA_MISMATCH",
            details={"expected": feature_keys, "actual": list(feature_vector.feature_keys)},
        )
    values = list(feature_vector.values)
    scaled = _scale_features(
        values,
        artifact["scaler_mean"],
        artifact["scaler_scale"],
    )
    coefficients = artifact["coefficients"][0]
    intercept = artifact["intercept"][0]
    logit = intercept + sum(c * v for c, v in zip(coefficients, scaled, strict=True))
    return _sigmoid(logit)


def run_candidate_inference(
    candidate: CandidateArtifactV1,
    artifact_bytes: bytes,
    feature_vector: BaselineFeatureVector,
) -> float:
    if candidate.candidate_kind != TrainerKind.LOGISTIC_REGRESSION:
        raise ValidationError(
            "CANDIDATE_INFERENCE_UNSUPPORTED",
            details={"candidate_kind": candidate.candidate_kind.value},
        )
    artifact = load_verified_logistic_artifact(candidate, artifact_bytes)
    return predict_logistic_probability(artifact, feature_vector)


__all__ = ["predict_logistic_probability", "run_candidate_inference"]
