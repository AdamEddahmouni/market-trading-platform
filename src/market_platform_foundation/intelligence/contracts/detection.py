"""DetectionV1 — deterministic semantic trigger contract (BUILD 09)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractKind,
    ContractReference,
    IntelligenceScope,
    QualitySummary,
    component_lineage_from_dict,
    component_lineage_to_dict,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


class SemanticEventType(StrEnum):
    ORDER_FLOW_REVERSAL = "ORDER_FLOW_REVERSAL"
    UNUSUAL_OPTIONS_ACTIVITY = "UNUSUAL_OPTIONS_ACTIVITY"
    BORROW_CHANGE = "BORROW_CHANGE"
    LIQUIDITY_EVENT = "LIQUIDITY_EVENT"
    NEWS_EVENT = "NEWS_EVENT"
    REGIME_SHIFT = "REGIME_SHIFT"


class DetectionSeverity(StrEnum):
    """Deterministic trigger magnitude/importance, never probability."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _sorted_refs(refs: tuple[ContractReference, ...], *, kind: ContractKind, field_name: str) -> tuple[ContractReference, ...]:
    unique = {(ref.kind, ref.id, ref.schema_version): ref for ref in refs}
    ordered = tuple(unique[key] for key in sorted(unique))
    if any(ref.kind != kind.value for ref in ordered):
        raise ValueError(f"DETECTION_{field_name.upper()}_REF_KIND_INVALID")
    return ordered


def _normalized_codes(values: tuple[str, ...]) -> tuple[str, ...]:
    codes = tuple(sorted({str(value) for value in values if str(value).strip()}))
    if not codes:
        raise ValueError("DETECTION_REASON_CODES_REQUIRED")
    return codes


@dataclass(frozen=True, slots=True)
class DetectionV1:
    """Derived semantic trigger anchored to one immutable SnapshotV1."""

    detection_id: str
    schema_version: str
    semantic_event_type: SemanticEventType
    detected_at_ns: int
    source_snapshot_ref: ContractReference
    detector_lineage: ComponentLineage
    scope: IntelligenceScope
    severity: DetectionSeverity
    reason_codes: tuple[str, ...]
    quality: QualitySummary
    source_signal_refs: tuple[ContractReference, ...] = ()
    source_event_refs: tuple[ContractReference, ...] = ()
    identity_context: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.detection_id, field_name="detection_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.detected_at_ns, field_name="detected_at_ns")
        if not isinstance(self.semantic_event_type, SemanticEventType):
            object.__setattr__(self, "semantic_event_type", SemanticEventType(str(self.semantic_event_type)))
        if not isinstance(self.severity, DetectionSeverity):
            object.__setattr__(self, "severity", DetectionSeverity(str(self.severity)))
        if self.source_snapshot_ref.kind != ContractKind.SNAPSHOT.value:
            raise ValueError("DETECTION_SNAPSHOT_REF_KIND_INVALID")
        if not self.detector_lineage.component_id or not self.detector_lineage.component_version:
            raise ValueError("DETECTION_LINEAGE_IDENTITY_REQUIRED")
        object.__setattr__(
            self,
            "source_signal_refs",
            _sorted_refs(self.source_signal_refs, kind=ContractKind.SIGNAL, field_name="signal"),
        )
        object.__setattr__(
            self,
            "source_event_refs",
            _sorted_refs(self.source_event_refs, kind=ContractKind.EVENT, field_name="event"),
        )
        object.__setattr__(self, "reason_codes", _normalized_codes(self.reason_codes))
        if not isinstance(self.identity_context, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.identity_context.items()
        ):
            raise ValueError("DETECTION_IDENTITY_CONTEXT_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("DETECTION_METADATA_INVALID")


_DETECTION_ALLOWED = dataclass_field_names(DetectionV1)


def detection_v1_to_dict(record: DetectionV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "detection_id": record.detection_id,
        "schema_version": record.schema_version,
        "semantic_event_type": record.semantic_event_type.value,
        "detected_at_ns": record.detected_at_ns,
        "source_snapshot_ref": contract_reference_to_dict(record.source_snapshot_ref),
        "detector_lineage": component_lineage_to_dict(record.detector_lineage),
        "scope": scope_to_dict(record.scope),
        "severity": record.severity.value,
        "reason_codes": list(record.reason_codes),
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.source_signal_refs:
        body["source_signal_refs"] = [contract_reference_to_dict(ref) for ref in record.source_signal_refs]
    if record.source_event_refs:
        body["source_event_refs"] = [contract_reference_to_dict(ref) for ref in record.source_event_refs]
    if record.identity_context:
        body["identity_context"] = dict(record.identity_context)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def detection_v1_from_dict(payload: dict[str, Any]) -> DetectionV1:
    reject_unknown_keys(payload, _DETECTION_ALLOWED)
    lineage = component_lineage_from_dict(payload.get("detector_lineage"))
    if lineage is None:
        raise ValueError("DETECTION_LINEAGE_REQUIRED")
    return DetectionV1(
        detection_id=str(payload["detection_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        semantic_event_type=SemanticEventType(str(payload["semantic_event_type"])),
        detected_at_ns=int(payload["detected_at_ns"]),
        source_snapshot_ref=contract_reference_from_dict(payload["source_snapshot_ref"]),
        source_signal_refs=tuple(
            contract_reference_from_dict(item) for item in payload.get("source_signal_refs", ())
        ),
        source_event_refs=tuple(
            contract_reference_from_dict(item) for item in payload.get("source_event_refs", ())
        ),
        detector_lineage=lineage,
        scope=scope_from_dict(payload["scope"]),
        severity=DetectionSeverity(str(payload["severity"])),
        reason_codes=tuple(payload["reason_codes"]),
        quality=quality_summary_from_dict(payload["quality"]),
        identity_context=dict(payload.get("identity_context") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "DetectionSeverity",
    "DetectionV1",
    "SemanticEventType",
    "detection_v1_from_dict",
    "detection_v1_to_dict",
]
