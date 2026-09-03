"""PredictionLedgerEntryV1 — frozen settlement plan preregistered at forecast registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    ForecastTarget,
    IntelligenceScope,
    dataclass_field_names,
    contract_reference_from_dict,
    contract_reference_to_dict,
    forecast_target_from_dict,
    forecast_target_to_dict,
    normalize_unique_refs,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class PredictionLedgerEntryV1:
    """Immutable preregistered settlement semantics for one forecast evaluation.

    What: frozen anchor, target window, availability cutoff, and policy identity.
    Not: mutable settlement status or adjudicated outcome values.
    Producers: BUILD 15 prediction ledger registration.
    Consumers: outcome settlement scheduler/adjudicator.
    """

    ledger_entry_id: str
    schema_version: str
    forecast_id: str
    forecast_ref: ContractReference
    target: ForecastTarget
    horizon_ns: int
    scope: IntelligenceScope
    instrument_id: str
    forecast_decision_time_ns: int
    anchor_observation: dict[str, Any]
    target_time_ns: int
    target_window_start_ns: int
    target_window_end_ns: int
    availability_cutoff_ns: int
    settlement_policy_identity: str
    observation_source_policy: dict[str, Any]
    mode: str
    registered_at_ns: int
    scenario_id: str | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.ledger_entry_id, field_name="ledger_entry_id")
        validate_schema_version(self.schema_version)
        validate_id(self.forecast_id, field_name="forecast_id")
        validate_timestamp_ns(self.forecast_decision_time_ns, field_name="forecast_decision_time_ns")
        validate_timestamp_ns(self.target_time_ns, field_name="target_time_ns")
        validate_timestamp_ns(self.target_window_start_ns, field_name="target_window_start_ns")
        validate_timestamp_ns(self.target_window_end_ns, field_name="target_window_end_ns")
        validate_timestamp_ns(self.availability_cutoff_ns, field_name="availability_cutoff_ns")
        validate_timestamp_ns(self.registered_at_ns, field_name="registered_at_ns")
        if self.horizon_ns <= 0:
            raise ValueError("HORIZON_MUST_BE_POSITIVE")
        validate_id(self.instrument_id, field_name="instrument_id")
        if not self.settlement_policy_identity:
            raise ValueError("SETTLEMENT_POLICY_IDENTITY_REQUIRED")
        if not self.mode:
            raise ValueError("SETTLEMENT_MODE_REQUIRED")
        if not isinstance(self.anchor_observation, dict):
            raise ValueError("ANCHOR_OBSERVATION_INVALID")
        if not isinstance(self.observation_source_policy, dict):
            raise ValueError("OBSERVATION_SOURCE_POLICY_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("LEDGER_METADATA_INVALID")
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))


_LEDGER_ALLOWED = dataclass_field_names(PredictionLedgerEntryV1)


def prediction_ledger_entry_v1_to_dict(record: PredictionLedgerEntryV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ledger_entry_id": record.ledger_entry_id,
        "schema_version": record.schema_version,
        "forecast_id": record.forecast_id,
        "forecast_ref": contract_reference_to_dict(record.forecast_ref),
        "target": forecast_target_to_dict(record.target),
        "horizon_ns": record.horizon_ns,
        "scope": scope_to_dict(record.scope),
        "instrument_id": record.instrument_id,
        "forecast_decision_time_ns": record.forecast_decision_time_ns,
        "anchor_observation": dict(record.anchor_observation),
        "target_time_ns": record.target_time_ns,
        "target_window_start_ns": record.target_window_start_ns,
        "target_window_end_ns": record.target_window_end_ns,
        "availability_cutoff_ns": record.availability_cutoff_ns,
        "settlement_policy_identity": record.settlement_policy_identity,
        "observation_source_policy": dict(record.observation_source_policy),
        "mode": record.mode,
        "registered_at_ns": record.registered_at_ns,
    }
    if record.scenario_id is not None:
        body["scenario_id"] = record.scenario_id
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def prediction_ledger_entry_v1_from_dict(payload: dict[str, Any]) -> PredictionLedgerEntryV1:
    reject_unknown_keys(payload, _LEDGER_ALLOWED)
    return PredictionLedgerEntryV1(
        ledger_entry_id=str(payload["ledger_entry_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        forecast_id=str(payload["forecast_id"]),
        forecast_ref=contract_reference_from_dict(payload["forecast_ref"]),
        target=forecast_target_from_dict(payload["target"]),
        horizon_ns=int(payload["horizon_ns"]),
        scope=scope_from_dict(payload["scope"]),
        instrument_id=str(payload["instrument_id"]),
        forecast_decision_time_ns=int(payload["forecast_decision_time_ns"]),
        anchor_observation=dict(payload.get("anchor_observation") or {}),
        target_time_ns=int(payload["target_time_ns"]),
        target_window_start_ns=int(payload["target_window_start_ns"]),
        target_window_end_ns=int(payload["target_window_end_ns"]),
        availability_cutoff_ns=int(payload["availability_cutoff_ns"]),
        settlement_policy_identity=str(payload["settlement_policy_identity"]),
        observation_source_policy=dict(payload.get("observation_source_policy") or {}),
        mode=str(payload["mode"]),
        registered_at_ns=int(payload["registered_at_ns"]),
        scenario_id=payload.get("scenario_id"),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "PredictionLedgerEntryV1",
    "prediction_ledger_entry_v1_from_dict",
    "prediction_ledger_entry_v1_to_dict",
]
