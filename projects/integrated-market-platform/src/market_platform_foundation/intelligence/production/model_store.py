"""Versioned JSON persist/load for fitted Path A PRODUCTION specialist models.

Serialization is operator-side Paper/Demo artifact storage — not canonical FTEP
state and not empirical Item 7 proof by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...canonical import load_json_strict, write_canonical_json
from ..contracts.common import forecast_target_from_dict, forecast_target_to_dict, time_horizon_from_dict, time_horizon_to_dict
from .model import ProductionSpecialistModel

MODEL_ARTIFACT_KIND = "path_a_production_specialist_model_v1"


def production_model_to_dict(model: ProductionSpecialistModel) -> dict[str, Any]:
    return {
        "artifact_kind": MODEL_ARTIFACT_KIND,
        "class_counts": dict(model.class_counts),
        "feature_schema_fingerprint": model.feature_schema_fingerprint,
        "horizon": time_horizon_to_dict(model.horizon),
        "hyperparameters": dict(model.hyperparameters),
        "implementation_version": model.implementation_version,
        "model_id": model.model_id,
        "model_kind": model.model_kind,
        "parameter_fingerprint": model.parameter_fingerprint,
        "parameters": dict(model.parameters),
        "sample_count": model.sample_count,
        "target": forecast_target_to_dict(model.target),
        "training_cutoff_ns": model.training_cutoff_ns,
        "training_dataset_fingerprint": model.training_dataset_fingerprint,
    }


def production_model_from_dict(payload: Mapping[str, Any]) -> ProductionSpecialistModel | None:
    if str(payload.get("artifact_kind") or "") != MODEL_ARTIFACT_KIND:
        return None
    try:
        return ProductionSpecialistModel(
            model_id=str(payload["model_id"]),
            model_kind=str(payload["model_kind"]),
            implementation_version=str(payload["implementation_version"]),
            feature_schema_fingerprint=str(payload["feature_schema_fingerprint"]),
            target=forecast_target_from_dict(dict(payload["target"])),
            horizon=time_horizon_from_dict(dict(payload["horizon"])),
            training_dataset_fingerprint=str(payload["training_dataset_fingerprint"]),
            training_cutoff_ns=int(payload["training_cutoff_ns"]),
            hyperparameters=dict(payload.get("hyperparameters") or {}),
            parameter_fingerprint=str(payload["parameter_fingerprint"]),
            parameters=dict(payload.get("parameters") or {}),
            sample_count=int(payload["sample_count"]),
            class_counts={str(k): int(v) for k, v in dict(payload.get("class_counts") or {}).items()},
        )
    except (KeyError, TypeError, ValueError):
        return None


def persist_production_specialist_model(
    model: ProductionSpecialistModel,
    *,
    destination: str | Path,
) -> dict[str, Any]:
    dest = Path(destination)
    payload = production_model_to_dict(model)
    if dest.suffix.lower() == ".json":
        target = dest
    else:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / f"{model.model_id}.json"
    write_canonical_json(target, payload)
    return payload


def load_production_specialist_model(source: str | Path | None) -> ProductionSpecialistModel | None:
    if source is None:
        return None
    path = Path(source)
    if not path.exists():
        return None
    targets = sorted(path.glob("*.json")) if path.is_dir() else (path,)
    for child in targets:
        try:
            payload = load_json_strict(child)
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        model = production_model_from_dict(payload)
        if model is not None:
            return model
    return None


__all__ = [
    "MODEL_ARTIFACT_KIND",
    "load_production_specialist_model",
    "persist_production_specialist_model",
    "production_model_from_dict",
    "production_model_to_dict",
]
