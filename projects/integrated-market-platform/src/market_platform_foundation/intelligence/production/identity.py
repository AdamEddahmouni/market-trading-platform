"""Path A PRODUCTION specialist identity and deterministic IDs.

Identity is locked to Path A honesty champion scope: ``target_kind=direction``
and a 5-minute horizon (300_000_000_000 ns). Forecast IDs exclude the
computed probability so a later numeric change cannot mint a new identity.
"""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..baselines.features import (
    DEFAULT_STATISTICAL_WINDOW_NS,
    BaselineFeatureSchema,
    FeatureSelector,
)
from ..contracts.common import (
    ForecastTarget,
    TimeHorizonNs,
    forecast_target_to_dict,
    time_horizon_to_dict,
)

PATH_A_TARGET_KIND = "direction"
PATH_A_HORIZON_NS = 300_000_000_000
PATH_A_FAMILY_KEY = "production:path-a-logistic-5m"
PRODUCTION_MODEL_KIND = "path-a-logistic-5m"
PRODUCTION_MODEL_VERSION = "1"
PRODUCTION_COMPONENT_ID = "path-a-production-specialist"
FORECAST_ID_VERSION = "production-specialist-forecast-sha256-v1"
MODEL_ID_VERSION = "production-specialist-model-sha256-v1"
DATASET_FINGERPRINT_VERSION = "production-specialist-dataset-sha256-v1"
PARAMETER_FINGERPRINT_VERSION = "production-specialist-parameter-sha256-v1"
MINIMUM_SPECIALIST_SAMPLES = 8
MINIMUM_SPECIALIST_CLASS_COUNT = 2

PATH_A_PRODUCTION_FEATURE_SCHEMA = BaselineFeatureSchema(
    selectors=(
        FeatureSelector(
            signal_type="momentum_simple",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="momentum-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="net_signed_share",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="cvd-calculator",
            calculator_version="1",
        ),
    )
)


def path_a_horizon() -> TimeHorizonNs:
    return TimeHorizonNs(duration_ns=PATH_A_HORIZON_NS)


def path_a_direction_target(instrument_id: str) -> ForecastTarget:
    return ForecastTarget(target_kind=PATH_A_TARGET_KIND, instrument_id=instrument_id, parameters={})


def matches_path_a_identity(*, target: ForecastTarget, horizon: TimeHorizonNs) -> tuple[str, ...]:
    reasons: list[str] = []
    if target.target_kind != PATH_A_TARGET_KIND:
        reasons.append("TARGET_MISMATCH")
    if horizon.duration_ns != PATH_A_HORIZON_NS:
        reasons.append("HORIZON_MISMATCH")
    return tuple(reasons)


def derive_model_id(
    *,
    model_kind: str,
    implementation_version: str,
    feature_schema_fingerprint: str,
    target: ForecastTarget,
    training_dataset_fingerprint: str,
    training_cutoff_ns: int,
    hyperparameters: dict[str, Any],
) -> str:
    payload = {
        "identity_version": MODEL_ID_VERSION,
        "model_kind": model_kind,
        "implementation_version": implementation_version,
        "feature_schema_fingerprint": feature_schema_fingerprint,
        "target": forecast_target_to_dict(target),
        "training_dataset_fingerprint": training_dataset_fingerprint,
        "training_cutoff_ns": training_cutoff_ns,
        "hyperparameters": {key: hyperparameters[key] for key in sorted(hyperparameters)},
    }
    return f"PSMOD-{sha256_bytes(canonical_bytes(payload))}"


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
        "target": forecast_target_to_dict(target),
        "horizon": time_horizon_to_dict(horizon),
    }
    return f"PSFC-{sha256_bytes(canonical_bytes(payload))}"


def derive_dataset_fingerprint(
    *,
    feature_schema_fingerprint: str,
    target: ForecastTarget,
    training_cutoff_ns: int,
    examples: list[dict[str, Any]],
) -> str:
    payload = {
        "identity_version": DATASET_FINGERPRINT_VERSION,
        "feature_schema_fingerprint": feature_schema_fingerprint,
        "target": forecast_target_to_dict(target),
        "training_cutoff_ns": training_cutoff_ns,
        "examples": examples,
    }
    return f"PSDS-{sha256_bytes(canonical_bytes(payload))}"


def parameter_fingerprint(parameters: dict[str, Any]) -> str:
    payload = {"identity_version": PARAMETER_FINGERPRINT_VERSION, "parameters": parameters}
    return f"PSPF-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "FORECAST_ID_VERSION",
    "MINIMUM_SPECIALIST_CLASS_COUNT",
    "MINIMUM_SPECIALIST_SAMPLES",
    "MODEL_ID_VERSION",
    "PATH_A_FAMILY_KEY",
    "PATH_A_HORIZON_NS",
    "PATH_A_PRODUCTION_FEATURE_SCHEMA",
    "PATH_A_TARGET_KIND",
    "PRODUCTION_COMPONENT_ID",
    "PRODUCTION_MODEL_KIND",
    "PRODUCTION_MODEL_VERSION",
    "derive_dataset_fingerprint",
    "derive_forecast_id",
    "derive_model_id",
    "matches_path_a_identity",
    "parameter_fingerprint",
    "path_a_direction_target",
    "path_a_horizon",
]
