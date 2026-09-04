"""Deterministic identity helpers for BUILD 14 fusion and calibration."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import ForecastTarget, TimeHorizonNs, forecast_target_to_dict, time_horizon_to_dict
from .types import CalibrationExample, FusionContributorRef, POOLING_METHOD

FUSION_MANIFEST_ID_VERSION = "forecast-fusion-manifest-sha256-v1"
RAW_FUSION_ID_VERSION = "raw-forecast-fusion-sha256-v1"
CALIBRATION_DATASET_ID_VERSION = "calibration-dataset-sha256-v1"
CALIBRATION_MODEL_ID_VERSION = "calibration-model-sha256-v1"
UNCERTAINTY_ASSESSMENT_ID_VERSION = "uncertainty-assessment-sha256-v1"
FINAL_FORECAST_ID_VERSION = "final-forecast-sha256-v1"
FUSION_POLICY_ID_VERSION = "forecast-fusion-policy-sha256-v1"
FINAL_POLICY_ID_VERSION = "final-forecast-policy-sha256-v1"


def _target_payload(target: ForecastTarget) -> dict[str, Any]:
    return forecast_target_to_dict(target)


def _horizon_payload(horizon: TimeHorizonNs) -> dict[str, Any]:
    return time_horizon_to_dict(horizon)


def derive_fusion_manifest_id(
    *,
    snapshot_id: str,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    decision_time_ns: int,
    contributor_entries: list[dict[str, Any]],
    fusion_policy_identity: str,
    hypothesis_context_ids: tuple[str, ...] = (),
    regime_key: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": FUSION_MANIFEST_ID_VERSION,
        "snapshot_id": snapshot_id,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
        "decision_time_ns": decision_time_ns,
        "contributors": contributor_entries,
        "fusion_policy_identity": fusion_policy_identity,
        "hypothesis_context_ids": list(hypothesis_context_ids),
    }
    if regime_key is not None:
        payload["regime_key"] = regime_key
    return f"FFM-{sha256_bytes(canonical_bytes(payload))}"


def contributor_entry_for_identity(ref: FusionContributorRef) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "forecast_id": ref.forecast.forecast_id,
        "role": ref.role.value,
        "contributor_weight": ref.contributor_weight,
    }
    if ref.forecast_family_key is not None:
        entry["forecast_family_key"] = ref.forecast_family_key
    return entry


def derive_raw_fusion_id(
    *,
    manifest_id: str,
    fusion_policy_identity: str,
    pooling_method: str = POOLING_METHOD,
) -> str:
    payload = {
        "identity_version": RAW_FUSION_ID_VERSION,
        "manifest_id": manifest_id,
        "fusion_policy_identity": fusion_policy_identity,
        "pooling_method": pooling_method,
    }
    return f"RFF-{sha256_bytes(canonical_bytes(payload))}"


def derive_dependence_group_id(
    *,
    forecast_ids: tuple[str, ...],
    fusion_policy_identity: str,
) -> str:
    payload = {
        "identity_version": "forecast-dependence-group-sha256-v1",
        "forecast_ids": list(forecast_ids),
        "fusion_policy_identity": fusion_policy_identity,
    }
    return f"FDG-{sha256_bytes(canonical_bytes(payload))}"


def derive_calibration_dataset_id(
    *,
    examples: tuple[CalibrationExample, ...],
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    fusion_policy_identity: str,
    calibration_cutoff_ns: int,
    regime_key: str | None = None,
) -> str:
    example_payloads = [
        {
            "raw_fusion_id": example.raw_fusion_id,
            "raw_probability": example.raw_probability,
            "label": example.label,
            "label_available_time_ns": example.label_available_time_ns,
            "forecast_decision_time_ns": example.forecast_decision_time_ns,
        }
        for example in sorted(examples, key=lambda row: row.raw_fusion_id)
    ]
    payload: dict[str, Any] = {
        "identity_version": CALIBRATION_DATASET_ID_VERSION,
        "examples": example_payloads,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
        "fusion_policy_identity": fusion_policy_identity,
        "calibration_cutoff_ns": calibration_cutoff_ns,
    }
    if regime_key is not None:
        payload["regime_key"] = regime_key
    return f"CLDS-{sha256_bytes(canonical_bytes(payload))}"


def derive_calibration_model_id(
    *,
    method: str,
    method_version: str,
    dataset_fingerprint: str,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    fusion_policy_identity: str,
    training_cutoff_ns: int,
    available_time_ns: int,
    hyperparameters: dict[str, Any],
    regime_key: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": CALIBRATION_MODEL_ID_VERSION,
        "method": method,
        "method_version": method_version,
        "dataset_fingerprint": dataset_fingerprint,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
        "fusion_policy_identity": fusion_policy_identity,
        "training_cutoff_ns": training_cutoff_ns,
        "available_time_ns": available_time_ns,
        "hyperparameters": {key: hyperparameters[key] for key in sorted(hyperparameters)},
    }
    if regime_key is not None:
        payload["regime_key"] = regime_key
    return f"CALM-{sha256_bytes(canonical_bytes(payload))}"


def parameter_fingerprint(parameters: dict[str, Any]) -> str:
    return f"CLPF-{sha256_bytes(canonical_bytes(parameters))}"


def derive_uncertainty_assessment_id(
    *,
    raw_fusion_id: str,
    calibration_model_id: str | None,
    final_policy_identity: str,
) -> str:
    payload = {
        "identity_version": UNCERTAINTY_ASSESSMENT_ID_VERSION,
        "raw_fusion_id": raw_fusion_id,
        "calibration_model_id": calibration_model_id,
        "final_policy_identity": final_policy_identity,
    }
    return f"UAS-{sha256_bytes(canonical_bytes(payload))}"


def derive_final_forecast_id(
    *,
    raw_fusion_id: str,
    calibration_model_id: str | None,
    final_policy_identity: str,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    snapshot_id: str,
    decision_time_ns: int,
    hypothesis_context_ids: tuple[str, ...] = (),
) -> str:
    payload = {
        "identity_version": FINAL_FORECAST_ID_VERSION,
        "raw_fusion_id": raw_fusion_id,
        "calibration_model_id": calibration_model_id,
        "final_policy_identity": final_policy_identity,
        "target": _target_payload(target),
        "horizon": _horizon_payload(horizon),
        "snapshot_id": snapshot_id,
        "decision_time_ns": decision_time_ns,
        "hypothesis_context_ids": list(hypothesis_context_ids),
        "forecast_stage_version": FINAL_FORECAST_ID_VERSION,
    }
    return f"FCST-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "CALIBRATION_DATASET_ID_VERSION",
    "CALIBRATION_MODEL_ID_VERSION",
    "FINAL_FORECAST_ID_VERSION",
    "FINAL_POLICY_ID_VERSION",
    "FUSION_MANIFEST_ID_VERSION",
    "FUSION_POLICY_ID_VERSION",
    "RAW_FUSION_ID_VERSION",
    "UNCERTAINTY_ASSESSMENT_ID_VERSION",
    "contributor_entry_for_identity",
    "derive_calibration_dataset_id",
    "derive_calibration_model_id",
    "derive_dependence_group_id",
    "derive_final_forecast_id",
    "derive_fusion_manifest_id",
    "derive_raw_fusion_id",
    "derive_uncertainty_assessment_id",
    "parameter_fingerprint",
]
