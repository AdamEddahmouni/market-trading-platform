"""EventV1 — normalized intelligence-plane event contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    QualitySummary,
    SourceReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    normalize_unique_strings,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    source_reference_from_dict,
    source_reference_to_dict,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class EventV1:
    """Normalized event participating in the intelligence system.

    What: immutable provider-normalized event with temporal and provenance fields.
    Not: a signal, forecast, or trade instruction.
    Producers: normalization/ingestion adapters (future BUILD layers).
    Consumers: snapshot assembly, feature/signal engines.
    Immutable after construction.
  """

    event_id: str
    schema_version: str
    event_type: str
    event_time_ns: int
    available_time_ns: int
    payload: dict[str, Any]
    quality: QualitySummary
    source: SourceReference
    instrument_id: str | None = None
    provider_time_ns: int | None = None
    received_time_ns: int | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    quality_observation_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.event_id, field_name="event_id")
        validate_schema_version(self.schema_version)
        if not self.event_type or not str(self.event_type).strip():
            raise ValueError("EVENT_TYPE_REQUIRED")
        validate_timestamp_ns(self.event_time_ns, field_name="event_time_ns")
        validate_timestamp_ns(self.available_time_ns, field_name="available_time_ns")
        if self.provider_time_ns is not None:
            validate_timestamp_ns(self.provider_time_ns, field_name="provider_time_ns")
        if self.received_time_ns is not None:
            validate_timestamp_ns(self.received_time_ns, field_name="received_time_ns")
        if self.instrument_id is not None:
            validate_id(self.instrument_id, field_name="instrument_id")
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        object.__setattr__(
            self, "quality_observation_refs", normalize_unique_strings(self.quality_observation_refs)
        )
        if not isinstance(self.payload, dict):
            raise ValueError("EVENT_PAYLOAD_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("EVENT_METADATA_INVALID")


_EVENT_ALLOWED = dataclass_field_names(EventV1)


def event_v1_to_dict(record: EventV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": record.event_id,
        "schema_version": record.schema_version,
        "event_type": record.event_type,
        "event_time_ns": record.event_time_ns,
        "available_time_ns": record.available_time_ns,
        "payload": dict(record.payload),
        "quality": quality_summary_to_dict(record.quality),
        "source": source_reference_to_dict(record.source),
    }
    if record.instrument_id is not None:
        body["instrument_id"] = record.instrument_id
    if record.provider_time_ns is not None:
        body["provider_time_ns"] = record.provider_time_ns
    if record.received_time_ns is not None:
        body["received_time_ns"] = record.received_time_ns
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.quality_observation_refs:
        body["quality_observation_refs"] = list(record.quality_observation_refs)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def event_v1_from_dict(payload: dict[str, Any]) -> EventV1:
    reject_unknown_keys(payload, _EVENT_ALLOWED)
    return EventV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        event_type=str(payload["event_type"]),
        event_time_ns=int(payload["event_time_ns"]),
        available_time_ns=int(payload["available_time_ns"]),
        payload=dict(payload.get("payload") or {}),
        quality=quality_summary_from_dict(payload["quality"]),
        source=source_reference_from_dict(payload["source"]),
        instrument_id=payload.get("instrument_id"),
        provider_time_ns=payload.get("provider_time_ns"),
        received_time_ns=payload.get("received_time_ns"),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        quality_observation_refs=tuple(payload.get("quality_observation_refs") or ()),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["EventV1", "event_v1_from_dict", "event_v1_to_dict"]
