"""Model spec and artifact identity per ADR-MODEL-001."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

SEED_POLICY = "DETERMINISTIC_STDlib_ONLY/1.0.0"


def build_model_spec(
    *,
    model_family: str,
    interface_version: str,
    hyperparameters: dict[str, object] | None = None,
) -> dict[str, object]:
    spec = {
        "hyperparameters": hyperparameters or {},
        "interface_version": interface_version,
        "model_family": model_family,
        "seed_policy": SEED_POLICY,
    }
    return {**spec, "model_spec_hash": sha256_bytes(canonical_bytes(spec))}


def build_model_identity(
    *,
    model_spec: dict[str, object],
    dataset_fingerprint: str,
    preprocessing_state_hash: str,
    artifact_bytes_hash: str,
) -> dict[str, str]:
    identity = {
        "artifact_bytes_hash": artifact_bytes_hash,
        "dataset_fingerprint": dataset_fingerprint,
        "model_spec_hash": str(model_spec["model_spec_hash"]),
        "preprocessing_state_hash": preprocessing_state_hash,
        "seed_policy": SEED_POLICY,
    }
    return {**identity, "model_identity_hash": sha256_bytes(canonical_bytes(identity))}


def model_artifact_hash(artifact: dict[str, Any]) -> str:
    body = dict(artifact)
    body.pop("artifact_bytes_hash", None)
    return sha256_bytes(canonical_bytes(body))
