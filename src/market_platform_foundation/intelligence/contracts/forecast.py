"""ForecastV1 — falsifiable, objectively settleable prediction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractReference,
    ForecastEstimate,
    ForecastTarget,
    IntelligenceScope,
    QualitySummary,
    TimeHorizonNs,
    component_lineage_from_dict,
    component_lineage_to_dict,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    forecast_estimate_from_dict,
    forecast_estimate_to_dict,
    forecast_target_from_dict,
    forecast_target_to_dict,
    normalize_unique_refs,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    time_horizon_from_dict,
    time_horizon_to_dict,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class ForecastV1:
    """Objective prediction record for later outcome adjudication.

    What: machine-testable forecast with explicit target and horizon.
    Not: evidence, hypothesis narrative, opportunity, or order authority.
    Producers: fusion/calibration layers (future BUILD); shadow adapter today.
    Consumers: opportunity screening, outcome scheduler (BUILD 15).
    Immutable after construction.
    """

    forecast_id: str
    schema_version: str
    scope: IntelligenceScope
    decision_time_ns: int
    snapshot_id: str
    target: ForecastTarget
    horizon: TimeHorizonNs
    estimate: ForecastEstimate
    quality: QualitySummary
    source_hypothesis_refs: tuple[ContractReference, ...] = ()
    source_evidence_refs: tuple[ContractReference, ...] = ()
    resolve_time_ns: int | None = None
    uncertainty: dict[str, Any] = field(default_factory=dict)
    component_lineage: ComponentLineage | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.forecast_id, field_name="forecast_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        validate_id(self.snapshot_id, field_name="snapshot_id")
        if self.resolve_time_ns is not None:
            validate_timestamp_ns(self.resolve_time_ns, field_name="resolve_time_ns")
        object.__setattr__(self, "source_hypothesis_refs", normalize_unique_refs(self.source_hypothesis_refs))
        object.__setattr__(self, "source_evidence_refs", normalize_unique_refs(self.source_evidence_refs))
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.uncertainty, dict):
            raise ValueError("FORECAST_UNCERTAINTY_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("FORECAST_METADATA_INVALID")


_FORECAST_ALLOWED = dataclass_field_names(ForecastV1)


def forecast_v1_to_dict(record: ForecastV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "forecast_id": record.forecast_id,
        "schema_version": record.schema_version,
        "scope": scope_to_dict(record.scope),
        "decision_time_ns": record.decision_time_ns,
        "snapshot_id": record.snapshot_id,
        "target": forecast_target_to_dict(record.target),
        "horizon": time_horizon_to_dict(record.horizon),
        "estimate": forecast_estimate_to_dict(record.estimate),
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.source_hypothesis_refs:
        body["source_hypothesis_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_hypothesis_refs
        ]
    if record.source_evidence_refs:
        body["source_evidence_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_evidence_refs
        ]
    if record.resolve_time_ns is not None:
        body["resolve_time_ns"] = record.resolve_time_ns
    if record.uncertainty:
        body["uncertainty"] = dict(record.uncertainty)
    if record.component_lineage is not None:
        body["component_lineage"] = component_lineage_to_dict(record.component_lineage)
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def forecast_v1_from_dict(payload: dict[str, Any]) -> ForecastV1:
    reject_unknown_keys(payload, _FORECAST_ALLOWED)
    return ForecastV1(
        forecast_id=str(payload["forecast_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        scope=scope_from_dict(payload["scope"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        snapshot_id=str(payload["snapshot_id"]),
        target=forecast_target_from_dict(payload["target"]),
        horizon=time_horizon_from_dict(payload["horizon"]),
        estimate=forecast_estimate_from_dict(payload["estimate"]),
        quality=quality_summary_from_dict(payload["quality"]),
        source_hypothesis_refs=tuple(
            contract_reference_from_dict(item)
            for item in (payload.get("source_hypothesis_refs") or [])
        ),
        source_evidence_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_evidence_refs") or [])
        ),
        resolve_time_ns=payload.get("resolve_time_ns"),
        uncertainty=dict(payload.get("uncertainty") or {}),
        component_lineage=component_lineage_from_dict(payload.get("component_lineage")),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["ForecastV1", "forecast_v1_from_dict", "forecast_v1_to_dict"]
