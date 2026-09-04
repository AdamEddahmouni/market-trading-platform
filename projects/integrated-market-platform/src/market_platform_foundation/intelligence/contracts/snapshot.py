"""SnapshotV1 — immutable decision-time information state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    QualitySummary,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class SnapshotV1:
    """Immutable information state for a decision point.

    What: shared PIT view so experts evaluate the same snapshot_id.
    Not: a forecast, hypothesis, or rolling market history dump.
    Producers: snapshot assembly service (future BUILD).
    Consumers: specialists, signal routers, evidence generators.
    Immutable after construction.
    """

    snapshot_id: str
    schema_version: str
    decision_time_ns: int
    scope: IntelligenceScope
    quality: QualitySummary
    source_event_refs: tuple[ContractReference, ...] = ()
    source_signal_refs: tuple[ContractReference, ...] = ()
    component_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    created_at_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.snapshot_id, field_name="snapshot_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.created_at_ns is not None:
            validate_timestamp_ns(self.created_at_ns, field_name="created_at_ns")
        object.__setattr__(self, "source_event_refs", normalize_unique_refs(self.source_event_refs))
        object.__setattr__(self, "source_signal_refs", normalize_unique_refs(self.source_signal_refs))
        object.__setattr__(self, "component_refs", normalize_unique_refs(self.component_refs))
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.metadata, dict):
            raise ValueError("SNAPSHOT_METADATA_INVALID")


_SNAPSHOT_ALLOWED = dataclass_field_names(SnapshotV1)


def snapshot_v1_to_dict(record: SnapshotV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "snapshot_id": record.snapshot_id,
        "schema_version": record.schema_version,
        "decision_time_ns": record.decision_time_ns,
        "scope": scope_to_dict(record.scope),
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.source_event_refs:
        body["source_event_refs"] = [contract_reference_to_dict(ref) for ref in record.source_event_refs]
    if record.source_signal_refs:
        body["source_signal_refs"] = [contract_reference_to_dict(ref) for ref in record.source_signal_refs]
    if record.component_refs:
        body["component_refs"] = [contract_reference_to_dict(ref) for ref in record.component_refs]
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.created_at_ns is not None:
        body["created_at_ns"] = record.created_at_ns
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def snapshot_v1_from_dict(payload: dict[str, Any]) -> SnapshotV1:
    reject_unknown_keys(payload, _SNAPSHOT_ALLOWED)
    return SnapshotV1(
        snapshot_id=str(payload["snapshot_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        decision_time_ns=int(payload["decision_time_ns"]),
        scope=scope_from_dict(payload["scope"]),
        quality=quality_summary_from_dict(payload["quality"]),
        source_event_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_event_refs") or [])
        ),
        source_signal_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_signal_refs") or [])
        ),
        component_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("component_refs") or [])
        ),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        created_at_ns=payload.get("created_at_ns"),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["SnapshotV1", "snapshot_v1_from_dict", "snapshot_v1_to_dict"]
