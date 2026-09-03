"""SignalV1 — deterministic or statistical market measurement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    Direction,
    IntelligenceScope,
    QualitySummary,
    TimeHorizonNs,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    time_horizon_from_dict,
    time_horizon_to_dict,
    validate_finite,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class SignalV1:
    """Market measurement — not an interpretation or forecast.

    What: scalar/structured measurement (CVD, spread, IV percentile, etc.).
    Not: evidence, hypothesis, forecast, or opportunity.
    Producers: feature/signal engines.
    Consumers: specialist routers, evidence generators.
    Immutable after construction.
    """

    signal_id: str
    schema_version: str
    signal_type: str
    scope: IntelligenceScope
    as_of_time_ns: int
    value: float
    quality: QualitySummary
    source_snapshot_ref: ContractReference | None = None
    source_event_refs: tuple[ContractReference, ...] = ()
    raw_value: float | None = None
    normalized_value: float | None = None
    unit: str | None = None
    direction: Direction | None = None
    calculation_window: TimeHorizonNs | None = None
    calculation_lineage: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.signal_id, field_name="signal_id")
        validate_schema_version(self.schema_version)
        if not self.signal_type or not str(self.signal_type).strip():
            raise ValueError("SIGNAL_TYPE_REQUIRED")
        validate_timestamp_ns(self.as_of_time_ns, field_name="as_of_time_ns")
        validate_finite(self.value, field_name="value")
        if self.raw_value is not None:
            validate_finite(self.raw_value, field_name="raw_value")
        if self.normalized_value is not None:
            validate_finite(self.normalized_value, field_name="normalized_value")
        if self.direction is not None and not isinstance(self.direction, Direction):
            object.__setattr__(self, "direction", Direction(str(self.direction)))
        object.__setattr__(self, "source_event_refs", normalize_unique_refs(self.source_event_refs))
        if not isinstance(self.calculation_lineage, dict):
            raise ValueError("SIGNAL_CALCULATION_LINEAGE_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("SIGNAL_METADATA_INVALID")


_SIGNAL_ALLOWED = dataclass_field_names(SignalV1)


def signal_v1_to_dict(record: SignalV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "signal_id": record.signal_id,
        "schema_version": record.schema_version,
        "signal_type": record.signal_type,
        "scope": scope_to_dict(record.scope),
        "as_of_time_ns": record.as_of_time_ns,
        "value": record.value,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.source_snapshot_ref is not None:
        body["source_snapshot_ref"] = contract_reference_to_dict(record.source_snapshot_ref)
    if record.source_event_refs:
        body["source_event_refs"] = [contract_reference_to_dict(ref) for ref in record.source_event_refs]
    if record.raw_value is not None:
        body["raw_value"] = record.raw_value
    if record.normalized_value is not None:
        body["normalized_value"] = record.normalized_value
    if record.unit is not None:
        body["unit"] = record.unit
    if record.direction is not None:
        body["direction"] = record.direction.value
    if record.calculation_window is not None:
        body["calculation_window"] = time_horizon_to_dict(record.calculation_window)
    if record.calculation_lineage:
        body["calculation_lineage"] = dict(record.calculation_lineage)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def signal_v1_from_dict(payload: dict[str, Any]) -> SignalV1:
    reject_unknown_keys(payload, _SIGNAL_ALLOWED)
    source_snapshot = payload.get("source_snapshot_ref")
    return SignalV1(
        signal_id=str(payload["signal_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        signal_type=str(payload["signal_type"]),
        scope=scope_from_dict(payload["scope"]),
        as_of_time_ns=int(payload["as_of_time_ns"]),
        value=float(payload["value"]),
        quality=quality_summary_from_dict(payload["quality"]),
        source_snapshot_ref=(
            contract_reference_from_dict(source_snapshot) if source_snapshot is not None else None
        ),
        source_event_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_event_refs") or [])
        ),
        raw_value=payload.get("raw_value"),
        normalized_value=payload.get("normalized_value"),
        unit=payload.get("unit"),
        direction=Direction(payload["direction"]) if payload.get("direction") is not None else None,
        calculation_window=(
            time_horizon_from_dict(payload["calculation_window"])
            if payload.get("calculation_window") is not None
            else None
        ),
        calculation_lineage=dict(payload.get("calculation_lineage") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["SignalV1", "signal_v1_from_dict", "signal_v1_to_dict"]
