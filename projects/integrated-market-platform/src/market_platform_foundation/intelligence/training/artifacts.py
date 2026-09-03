"""Safe candidate artifact serialization (BUILD 18)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import TrainingFactoryError
from .identity import artifact_content_hash


ARTIFACT_FORMAT_JSON_V1 = "sklearn-json-v1"


def serialize_logistic_artifact(
    *,
    coefficients: list[list[float]],
    intercept: list[float],
    classes: list[int],
    scaler_mean: list[float],
    scaler_scale: list[float],
    hyperparameters: dict[str, Any],
    feature_keys: list[str],
) -> bytes:
    payload = {
        "format": ARTIFACT_FORMAT_JSON_V1,
        "model_kind": "logistic-regression",
        "coefficients": coefficients,
        "intercept": intercept,
        "classes": classes,
        "scaler_mean": scaler_mean,
        "scaler_scale": scaler_scale,
        "hyperparameters": hyperparameters,
        "feature_keys": feature_keys,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_and_parse_logistic_artifact(content: bytes, expected_hash: str) -> dict[str, Any]:
    actual_hash = artifact_content_hash(content)
    if actual_hash != expected_hash:
        raise TrainingFactoryError(
            "ARTIFACT_HASH_MISMATCH",
            details={"expected": expected_hash, "actual": actual_hash},
        )
    payload = json.loads(content.decode("utf-8"))
    if payload.get("format") != ARTIFACT_FORMAT_JSON_V1:
        raise TrainingFactoryError("ARTIFACT_FORMAT_UNSUPPORTED")
    return payload


def write_artifact_file(
    *,
    base_dir: Path,
    candidate_id: str,
    content: bytes,
) -> str:
    digest = artifact_content_hash(content)
    artifact_dir = base_dir / "candidates" / candidate_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{digest}.json"
    artifact_path.write_bytes(content)
    return str(artifact_path)


__all__ = [
    "ARTIFACT_FORMAT_JSON_V1",
    "serialize_logistic_artifact",
    "verify_and_parse_logistic_artifact",
    "write_artifact_file",
]
