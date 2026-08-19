"""Walk-forward harness for SS P3 baseline models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..walk_forward import build_walk_forward_folds, verify_fold_pit
from ...options.features.squeeze_context import augment_features_with_context
from .calibration import calibration_report
from .logistic_hazard import predict_squeeze_probability
from .magnitude import predict_squeeze_magnitude
from .rare_event_ensemble import predict_squeeze_ensemble

DEFAULT_MECHANISM_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "squeeze"
    / "mechanism_labels.json"
)

_REQUIRED_ADJUDICATION_FIELDS = (
    "adjudicator",
    "adjudication_time",
    "label_confidence",
    "pit_verified",
)


def _row_has_adjudication(row: dict[str, Any]) -> bool:
    for field in _REQUIRED_ADJUDICATION_FIELDS:
        if field not in row:
            return False
    if not row.get("pit_verified"):
        return False
    return bool(row.get("adjudicator")) and bool(row.get("adjudication_time"))


def load_mechanism_dataset(path: Path | None = None) -> list[dict[str, Any]]:
    fixture_path = path or DEFAULT_MECHANISM_FIXTURE
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    adjudicated = [
        row
        for row in rows
        if isinstance(row, dict) and _row_has_adjudication(row)
    ]
    return adjudicated


def run_squeeze_walk_forward_harness(
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dataset = rows or load_mechanism_dataset()
    obs_times = [
        int(row.get("observation_time_ns", 0))
        for row in dataset
        if isinstance(row.get("observation_time_ns"), int)
    ]
    folds = build_walk_forward_folds(obs_times, min_train=2, test_size=1)
    pit_rows = [
        {
            "observation_time": int(row.get("observation_time_ns", 0)),
            "prediction_cutoff": int(row.get("prediction_cutoff", row.get("observation_time_ns", 0))),
        }
        for row in dataset
        if isinstance(row.get("observation_time_ns"), int)
    ]
    pit_status, pit_reasons = verify_fold_pit(folds, pit_rows)
    predictions: list[float] = []
    labels: list[bool] = []
    ensemble_predictions: list[float] = []
    magnitude_predictions: list[float] = []
    magnitude_labels: list[float] = []
    for row in dataset:
        features = row.get("features", [])
        if not isinstance(features, list):
            continue
        physical_forecast = row.get("physical_forecast")
        squeeze_context = row.get("squeeze_context")
        augmented = augment_features_with_context(
            features,
            squeeze_context=squeeze_context if isinstance(squeeze_context, dict) else None,
            physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        )
        pred = predict_squeeze_probability(augmented)
        predictions.append(float(pred["occurrence_probability"]))
        labels.append(bool(row.get("squeeze_occurred", False)))
        ensemble_pred = predict_squeeze_ensemble(augmented)
        ensemble_predictions.append(float(ensemble_pred["occurrence_probability"]))
        magnitude = predict_squeeze_magnitude(
            features,
            squeeze_context=squeeze_context if isinstance(squeeze_context, dict) else None,
            physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        )
        if magnitude.get("expected_move_pct") is not None:
            magnitude_predictions.append(float(magnitude["expected_move_pct"]))
            outcome_move = row.get("realized_move_pct")
            if isinstance(outcome_move, (int, float)):
                magnitude_labels.append(float(outcome_move))
    calibration = calibration_report(predictions, labels)
    ensemble_calibration = calibration_report(ensemble_predictions, labels)
    magnitude_calibration: dict[str, float] = {}
    if magnitude_predictions and magnitude_labels and len(magnitude_predictions) == len(magnitude_labels):
        errors = [
            (pred - label) ** 2
            for pred, label in zip(magnitude_predictions, magnitude_labels)
        ]
        magnitude_calibration = {
            "mse": round(sum(errors) / len(errors), 6),
            "sample_count": float(len(errors)),
        }
    return {
        "adjudicated_row_count": len(dataset),
        "calibration": calibration,
        "ensemble_calibration": ensemble_calibration,
        "fold_count": len(folds),
        "magnitude_calibration": magnitude_calibration,
        "pit_reasons": pit_reasons,
        "pit_status": pit_status,
        "sample_count": len(predictions),
    }


__all__ = [
    "DEFAULT_MECHANISM_FIXTURE",
    "load_mechanism_dataset",
    "run_squeeze_walk_forward_harness",
]
