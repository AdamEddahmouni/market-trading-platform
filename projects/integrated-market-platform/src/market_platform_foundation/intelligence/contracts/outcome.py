"""OutcomeV1 — objective resolved forecast result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    Direction,
    OutcomeResolutionStatus,
    QualitySummary,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    validate_finite,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class OutcomeV1:
    """Objective measured facts adjudicating a forecast.

    What: settled measurements (return, direction, MFE/MAE) linked to forecast_id.
    Not: retrospective model critique or research narrative.
    Producers: outcome scheduler/adjudicator (future BUILD 15); shadow adapter today.
    Consumers: learning/research evaluation layers.
    Immutable after construction.
    """

    outcome_id: str
    schema_version: str
    forecast_id: str
    adjudicated_at_ns: int
    resolution_status: OutcomeResolutionStatus
    quality: QualitySummary
    start_observation: dict[str, Any] = field(default_factory=dict)
    end_observation: dict[str, Any] = field(default_factory=dict)
    realized_return: float | None = None
    realized_direction: Direction | None = None
    mfe: float | None = None
    mae: float | None = None
    path_summary: dict[str, Any] = field(default_factory=dict)
    unlabelable_reason: str | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.outcome_id, field_name="outcome_id")
        validate_schema_version(self.schema_version)
        validate_id(self.forecast_id, field_name="forecast_id")
        validate_timestamp_ns(self.adjudicated_at_ns, field_name="adjudicated_at_ns")
        if not isinstance(self.resolution_status, OutcomeResolutionStatus):
            object.__setattr__(
                self, "resolution_status", OutcomeResolutionStatus(str(self.resolution_status))
            )
        if self.realized_return is not None:
            validate_finite(self.realized_return, field_name="realized_return")
        if self.mfe is not None:
            validate_finite(self.mfe, field_name="mfe")
        if self.mae is not None:
            validate_finite(self.mae, field_name="mae")
        if self.realized_direction is not None and not isinstance(self.realized_direction, Direction):
            object.__setattr__(self, "realized_direction", Direction(str(self.realized_direction)))
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.start_observation, dict):
            raise ValueError("OUTCOME_START_OBSERVATION_INVALID")
        if not isinstance(self.end_observation, dict):
            raise ValueError("OUTCOME_END_OBSERVATION_INVALID")
        if not isinstance(self.path_summary, dict):
            raise ValueError("OUTCOME_PATH_SUMMARY_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("OUTCOME_METADATA_INVALID")
        if self.resolution_status == OutcomeResolutionStatus.UNLABELABLE and not self.unlabelable_reason:
            raise ValueError("UNLABELABLE_REASON_REQUIRED")


_OUTCOME_ALLOWED = dataclass_field_names(OutcomeV1)


def outcome_v1_to_dict(record: OutcomeV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "outcome_id": record.outcome_id,
        "schema_version": record.schema_version,
        "forecast_id": record.forecast_id,
        "adjudicated_at_ns": record.adjudicated_at_ns,
        "resolution_status": record.resolution_status.value,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.start_observation:
        body["start_observation"] = dict(record.start_observation)
    if record.end_observation:
        body["end_observation"] = dict(record.end_observation)
    if record.realized_return is not None:
        body["realized_return"] = record.realized_return
    if record.realized_direction is not None:
        body["realized_direction"] = record.realized_direction.value
    if record.mfe is not None:
        body["mfe"] = record.mfe
    if record.mae is not None:
        body["mae"] = record.mae
    if record.path_summary:
        body["path_summary"] = dict(record.path_summary)
    if record.unlabelable_reason is not None:
        body["unlabelable_reason"] = record.unlabelable_reason
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def outcome_v1_from_dict(payload: dict[str, Any]) -> OutcomeV1:
    reject_unknown_keys(payload, _OUTCOME_ALLOWED)
    return OutcomeV1(
        outcome_id=str(payload["outcome_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        forecast_id=str(payload["forecast_id"]),
        adjudicated_at_ns=int(payload["adjudicated_at_ns"]),
        resolution_status=OutcomeResolutionStatus(payload["resolution_status"]),
        quality=quality_summary_from_dict(payload["quality"]),
        start_observation=dict(payload.get("start_observation") or {}),
        end_observation=dict(payload.get("end_observation") or {}),
        realized_return=payload.get("realized_return"),
        realized_direction=(
            Direction(payload["realized_direction"])
            if payload.get("realized_direction") is not None
            else None
        ),
        mfe=payload.get("mfe"),
        mae=payload.get("mae"),
        path_summary=dict(payload.get("path_summary") or {}),
        unlabelable_reason=payload.get("unlabelable_reason"),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["OutcomeV1", "outcome_v1_from_dict", "outcome_v1_to_dict"]
