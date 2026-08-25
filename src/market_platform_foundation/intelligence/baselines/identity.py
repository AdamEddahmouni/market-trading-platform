"""Deterministic baseline identity helpers (BUILD 08)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import ForecastTarget, TimeHorizonNs, forecast_target_to_dict, time_horizon_to_dict

FORECAST_ID_VERSION = "baseline-forecast-sha256-v1"
MODEL_ID_VERSION = "baseline-model-sha256-v1"
DATASET_FINGERPRINT_VERSION = "training-dataset-sha256-v1"
FEATURE_SCHEMA_VERSION = "baseline-feature-schema-sha256-v1"
PREDICTION_POLICY_VERSION = "baseline-prediction-policy-v1"


def _target_payload(target: ForecastTarget) -> dict[str, Any]:
    return forecast_target_to_dict(target)


def _horizon_payload(horizon: TimeHorizonNs) -> dict[str, Any]:
    return time_horizon_to_dict(horizon)


def feature_schema_fingerprint(selectors_payload: list[dict[str, Any]]) -> str:
    payload = {
        "identity_version": FEATURE_SCHEMA_VERSION,
        "selectors": selectors_payload,
    }
    return sha256_bytes(canonical_bytes(payload))


def derive_model_id(
    *,
    model_kind: str,
    implementation_version: str,
    feature_schema_fingerprint_value: str,
    target: ForecastTarget,
    training_dataset_fingerprint: str | None = None,
    training_cutoff_ns: int | None = None,
    hyperparameters: dict[str, Any] | None = None,
    seed: int | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": MODEL_ID_VERSION,
        "model_kind": model_kind,
        "implementation_version": implementation_version,
        "feature_schema_fingerprint": feature_schema_fingerprint_value,
        "target": _target_payload(target),
    }
    if training_dataset_fingerprint is not None:
        payload["training_dataset_fingerprint"] = training_dataset_fingerprint
    if training_cutoff_ns is not None:
        payload["training_cutoff_ns"] = training_cutoff_ns
    if hyperparameters:
        payload["hyperparameters"] = {key: hyperparameters[key] for key in sorted(hyperparameters)}
    if seed is not None:
        payload["seed"] = seed
    return f"BLMOD-{sha256_bytes(canonical_bytes(payload))}"


def derive_forecast_id(
    *,
    snapshot_id: str,
    source_signal_ids: tuple[str, ...],
    model_id: str,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
) -> str:
    payload = {
        "identity_version": FORECAST_ID_VERSION,
        "snapshot_id": snapshot_id,
        "source_signal_ids": list(source_signal_ids),
        "model_id": model_id,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
        "prediction_policy_version": PREDICTION_POLICY_VERSION,
    }
    return f"BLFC-{sha256_bytes(canonical_bytes(payload))}"


def derive_dataset_fingerprint(
    *,
    feature_schema_fingerprint_value: str,
    target: ForecastTarget,
    training_cutoff_ns: int,
    examples: list[dict[str, Any]],
) -> str:
    payload = {
        "identity_version": DATASET_FINGERPRINT_VERSION,
        "feature_schema_fingerprint": feature_schema_fingerprint_value,
        "target": _target_payload(target),
        "training_cutoff_ns": training_cutoff_ns,
        "examples": examples,
    }
    return f"BLDS-{sha256_bytes(canonical_bytes(payload))}"


def deterministic_probability(
    *,
    seed: str,
    snapshot_id: str,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
) -> float:
    payload = {
        "seed": seed,
        "snapshot_id": snapshot_id,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
    }
    digest = sha256_bytes(canonical_bytes(payload))
    value = int(digest[:16], 16)
    return value / float(16**16 - 1)


def parameter_fingerprint_from_payload(payload: dict[str, Any]) -> str:
    return f"BLPF-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "DATASET_FINGERPRINT_VERSION",
    "FEATURE_SCHEMA_VERSION",
    "FORECAST_ID_VERSION",
    "MODEL_ID_VERSION",
    "PREDICTION_POLICY_VERSION",
    "derive_dataset_fingerprint",
    "derive_forecast_id",
    "derive_model_id",
    "deterministic_probability",
    "feature_schema_fingerprint",
    "parameter_fingerprint_from_payload",
]
