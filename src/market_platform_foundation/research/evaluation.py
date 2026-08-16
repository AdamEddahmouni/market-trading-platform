"""Walk-forward evaluation orchestration."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .baseline_naive import MODEL_FAMILY, NaiveLastValueModel, PREPROCESSING_STATE_HASH
from .dataset_manifest import build_dataset_manifest, materialize_dataset_rows
from .forecast import verify_forecast_interface
from .model_spec import build_model_identity
from .targets import DEFAULT_HORIZON_NS, build_target_rows, verify_label_availability
from .walk_forward import build_walk_forward_folds, verify_fold_pit


def run_walk_forward_evaluation(
    events: list[dict[str, Any]],
    *,
    horizon_ns: int = DEFAULT_HORIZON_NS,
) -> dict[str, object]:
    rows = materialize_dataset_rows(events)
    manifest = build_dataset_manifest(rows)
    dataset_fp = str(manifest["dataset_fingerprint"])
    targets = build_target_rows(rows, horizon_ns=horizon_ns)
    label_status, label_reasons = verify_label_availability(targets, horizon_ns=horizon_ns)
    obs_times = [int(row["observation_time"]) for row in targets]
    folds = build_walk_forward_folds(obs_times)
    fold_status, fold_reasons = verify_fold_pit(folds, targets)
    predictions: list[dict[str, object]] = []
    final_model = NaiveLastValueModel()
    for fold in folds:
        train_end = int(fold["train_end_cutoff"])
        train_rows = [row for row in rows if int(row["available_time"]) <= train_end]
        test_targets = [
            row
            for row in targets
            if int(fold["test_start_cutoff"])
            <= int(row["observation_time"])
            <= int(fold["test_end_cutoff"])
        ]
        model = NaiveLastValueModel()
        model.fit(train_rows)
        final_model = model
        for target in test_targets:
            forecast = model.predict(target, horizon_ns=horizon_ns)
            fcast_status, _ = verify_forecast_interface(forecast)
            predictions.append(
                {
                    "fold_id": fold["fold_id"],
                    "forecast": forecast,
                    "forecast_status": fcast_status,
                    "observation_time": target["observation_time"],
                }
            )
    if not folds:
        final_model.fit(rows)
    artifact = final_model.artifact_body(dataset_fingerprint=dataset_fp)
    identity = build_model_identity(
        model_spec=final_model.model_spec,
        dataset_fingerprint=dataset_fp,
        preprocessing_state_hash=PREPROCESSING_STATE_HASH,
        artifact_bytes_hash=str(artifact["artifact_bytes_hash"]),
    )
    return {
        "artifact": artifact,
        "dataset_manifest": manifest,
        "dataset_row_count": len(rows),
        "fold_count": len(folds),
        "fold_pit_reason_codes": fold_reasons,
        "fold_pit_status": fold_status,
        "label_reason_codes": label_reasons,
        "label_status": label_status,
        "model_family": MODEL_FAMILY,
        "model_identity": identity,
        "predictions": predictions,
        "target_count": len(targets),
        "walk_forward_folds": folds,
    }


def evaluation_root_hash(result: dict[str, object]) -> str:
    body = {
        "dataset_fingerprint": result["dataset_manifest"]["dataset_fingerprint"],
        "fold_count": result["fold_count"],
        "model_identity_hash": result["model_identity"]["model_identity_hash"],
        "prediction_hashes": [
            sha256_bytes(canonical_bytes(row["forecast"]))
            for row in result.get("predictions", [])
            if isinstance(row, dict)
        ],
    }
    return sha256_bytes(canonical_bytes(body))
