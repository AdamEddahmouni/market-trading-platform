"""Deterministic identity helpers for BUILD 15 settlement artifacts."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from .policy import OutcomeSettlementPolicy
from .types import SettlementMode

PREDICTION_LEDGER_ENTRY_ID_VERSION = "prediction-ledger-entry-sha256-v1"
OUTCOME_ID_VERSION = "outcome-settlement-sha256-v1"


def derive_ledger_entry_id(
    *,
    forecast_id: str,
    settlement_policy_identity: str,
    anchor_observation: dict[str, Any],
    target_time_ns: int,
    target_window_start_ns: int,
    target_window_end_ns: int,
    availability_cutoff_ns: int,
    mode: SettlementMode | str,
    scenario_id: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": PREDICTION_LEDGER_ENTRY_ID_VERSION,
        "forecast_id": forecast_id,
        "settlement_policy_identity": settlement_policy_identity,
        "anchor_event_id": anchor_observation.get("event_id"),
        "anchor_event_time_ns": anchor_observation.get("event_time_ns"),
        "anchor_available_time_ns": anchor_observation.get("available_time_ns"),
        "anchor_observation_kind": anchor_observation.get("observation_kind"),
        "target_time_ns": target_time_ns,
        "target_window_start_ns": target_window_start_ns,
        "target_window_end_ns": target_window_end_ns,
        "availability_cutoff_ns": availability_cutoff_ns,
        "mode": str(mode),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    return f"PLE-{sha256_bytes(canonical_bytes(payload))}"


def derive_outcome_id(
    *,
    forecast_id: str,
    ledger_entry_id: str,
    settlement_policy_identity: str,
    mode: SettlementMode | str,
    scenario_id: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": OUTCOME_ID_VERSION,
        "forecast_id": forecast_id,
        "ledger_entry_id": ledger_entry_id,
        "settlement_policy_identity": settlement_policy_identity,
        "mode": str(mode),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    return f"OUT-{sha256_bytes(canonical_bytes(payload))}"


def ledger_identity_payload(
    *,
    forecast_id: str,
    policy: OutcomeSettlementPolicy,
    anchor_observation: dict[str, Any],
    target_time_ns: int,
    target_window_start_ns: int,
    target_window_end_ns: int,
    availability_cutoff_ns: int,
    mode: SettlementMode | str,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    return {
        "forecast_id": forecast_id,
        "settlement_policy_identity": policy.policy_id,
        "anchor_observation": anchor_observation,
        "target_time_ns": target_time_ns,
        "target_window_start_ns": target_window_start_ns,
        "target_window_end_ns": target_window_end_ns,
        "availability_cutoff_ns": availability_cutoff_ns,
        "mode": str(mode),
        "scenario_id": scenario_id,
    }


__all__ = [
    "OUTCOME_ID_VERSION",
    "PREDICTION_LEDGER_ENTRY_ID_VERSION",
    "derive_ledger_entry_id",
    "derive_outcome_id",
    "ledger_identity_payload",
]
