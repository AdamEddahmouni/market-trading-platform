"""Naive last-value baseline model — stdlib only."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .forecast import MODEL_INTERFACE_VERSION, build_forecast
from .model_spec import SEED_POLICY, build_model_spec, model_artifact_hash

MODEL_FAMILY = "NAIVE_LAST_VALUE"
PREPROCESSING_STATE_HASH = sha256_bytes(canonical_bytes({"state": "identity"}))


class NaiveLastValueModel:
    """Predicts the most recent observed bar_close as the score."""

    def __init__(self) -> None:
        self._last_value: dict[str, str] = {}

    @property
    def model_spec(self) -> dict[str, object]:
        return build_model_spec(
            model_family=MODEL_FAMILY,
            interface_version=MODEL_INTERFACE_VERSION,
            hyperparameters={"lookback": 1},
        )

    def fit(self, rows: list[dict[str, object]]) -> None:
        for row in rows:
            instrument = str(row.get("instrument_id", ""))
            value = str(row.get("value", row.get("forward_return", "0")))
            if "value" in row:
                self._last_value[instrument] = value

    def predict(
        self,
        row: dict[str, object],
        *,
        horizon_ns: int,
    ) -> dict[str, Any]:
        instrument = str(row.get("instrument_id", ""))
        cutoff = int(row.get("prediction_cutoff", row.get("observation_time", 0)))
        if instrument not in self._last_value:
            return build_forecast(
                score="0",
                prediction_cutoff=cutoff,
                horizon_ns=horizon_ns,
                status="fallback",
                fallback_reason_code="FCAST_NO_TRAINING_OBSERVATION",
            )
        return build_forecast(
            score=self._last_value[instrument],
            prediction_cutoff=cutoff,
            horizon_ns=horizon_ns,
        )

    def artifact_body(self, *, dataset_fingerprint: str) -> dict[str, object]:
        body = {
            "dataset_fingerprint": dataset_fingerprint,
            "last_values": dict(sorted(self._last_value.items())),
            "model_family": MODEL_FAMILY,
            "model_spec": self.model_spec,
            "preprocessing_state_hash": PREPROCESSING_STATE_HASH,
            "seed_policy": SEED_POLICY,
        }
        return {**body, "artifact_bytes_hash": model_artifact_hash(body)}

    def load_from_artifact(self, artifact: dict[str, object]) -> None:
        last_values = artifact.get("last_values", {})
        if not isinstance(last_values, dict):
            raise ValueError("invalid artifact last_values")
        self._last_value = {str(k): str(v) for k, v in last_values.items()}
