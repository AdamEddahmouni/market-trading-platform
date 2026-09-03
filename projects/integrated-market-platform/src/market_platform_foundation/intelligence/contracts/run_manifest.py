"""RunManifestV1 — frozen intelligence run configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...operating_modes import DATA_MODES, EXECUTION_AUTHORITIES, EXECUTION_MODES
from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    QualitySummary,
    component_lineage_from_dict,
    component_lineage_to_dict,
    dataclass_field_names,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class RunManifestV1:
    """Frozen runtime configuration for reproducible intelligence runs.

    What: immutable manifest of versions, modes, and component references.
    Not: mutable runtime state or execution authorization grant.
    Producers: run orchestration / shadow recorder.
    Consumers: replay, audit, challenger comparison.
    Immutable after construction.
    """

    run_id: str
    schema_version: str
    created_at_ns: int
    quality: QualitySummary
    run_window_start_ns: int | None = None
    run_window_end_ns: int | None = None
    data_mode: str | None = None
    execution_mode: str | None = None
    execution_authority: str | None = None
    code_revision: str | None = None
    config_identity: str | None = None
    provider_config_refs: tuple[dict[str, str], ...] = ()
    feature_schema_refs: tuple[dict[str, str], ...] = ()
    router_version: str | None = None
    model_versions: tuple[dict[str, str], ...] = ()
    fusion_version: str | None = None
    calibration_version: str | None = None
    strategy_version: str | None = None
    prediction_version: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    component_lineage: ComponentLineage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.run_id, field_name="run_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.created_at_ns, field_name="created_at_ns")
        if self.run_window_start_ns is not None:
            validate_timestamp_ns(self.run_window_start_ns, field_name="run_window_start_ns")
        if self.run_window_end_ns is not None:
            validate_timestamp_ns(self.run_window_end_ns, field_name="run_window_end_ns")
        if self.data_mode is not None and self.data_mode not in DATA_MODES:
            raise ValueError("RUN_MANIFEST_DATA_MODE_INVALID")
        if self.execution_mode is not None and self.execution_mode not in EXECUTION_MODES:
            raise ValueError("RUN_MANIFEST_EXECUTION_MODE_INVALID")
        if self.execution_authority is not None and self.execution_authority not in EXECUTION_AUTHORITIES:
            raise ValueError("RUN_MANIFEST_EXECUTION_AUTHORITY_INVALID")
        object.__setattr__(
            self,
            "provider_config_refs",
            tuple(dict(item) for item in self.provider_config_refs),
        )
        object.__setattr__(
            self,
            "feature_schema_refs",
            tuple(dict(item) for item in self.feature_schema_refs),
        )
        object.__setattr__(
            self,
            "model_versions",
            tuple(dict(item) for item in self.model_versions),
        )
        if not isinstance(self.environment, dict):
            raise ValueError("RUN_MANIFEST_ENVIRONMENT_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("RUN_MANIFEST_METADATA_INVALID")


_RUN_MANIFEST_ALLOWED = dataclass_field_names(RunManifestV1)


def run_manifest_v1_to_dict(record: RunManifestV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "run_id": record.run_id,
        "schema_version": record.schema_version,
        "created_at_ns": record.created_at_ns,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.run_window_start_ns is not None:
        body["run_window_start_ns"] = record.run_window_start_ns
    if record.run_window_end_ns is not None:
        body["run_window_end_ns"] = record.run_window_end_ns
    if record.data_mode is not None:
        body["data_mode"] = record.data_mode
    if record.execution_mode is not None:
        body["execution_mode"] = record.execution_mode
    if record.execution_authority is not None:
        body["execution_authority"] = record.execution_authority
    if record.code_revision is not None:
        body["code_revision"] = record.code_revision
    if record.config_identity is not None:
        body["config_identity"] = record.config_identity
    if record.provider_config_refs:
        body["provider_config_refs"] = [dict(item) for item in record.provider_config_refs]
    if record.feature_schema_refs:
        body["feature_schema_refs"] = [dict(item) for item in record.feature_schema_refs]
    if record.router_version is not None:
        body["router_version"] = record.router_version
    if record.model_versions:
        body["model_versions"] = [dict(item) for item in record.model_versions]
    if record.fusion_version is not None:
        body["fusion_version"] = record.fusion_version
    if record.calibration_version is not None:
        body["calibration_version"] = record.calibration_version
    if record.strategy_version is not None:
        body["strategy_version"] = record.strategy_version
    if record.prediction_version is not None:
        body["prediction_version"] = record.prediction_version
    if record.environment:
        body["environment"] = dict(record.environment)
    if record.component_lineage is not None:
        body["component_lineage"] = component_lineage_to_dict(record.component_lineage)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def run_manifest_v1_from_dict(payload: dict[str, Any]) -> RunManifestV1:
    reject_unknown_keys(payload, _RUN_MANIFEST_ALLOWED)
    return RunManifestV1(
        run_id=str(payload["run_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        created_at_ns=int(payload["created_at_ns"]),
        quality=quality_summary_from_dict(payload["quality"]),
        run_window_start_ns=payload.get("run_window_start_ns"),
        run_window_end_ns=payload.get("run_window_end_ns"),
        data_mode=payload.get("data_mode"),
        execution_mode=payload.get("execution_mode"),
        execution_authority=payload.get("execution_authority"),
        code_revision=payload.get("code_revision"),
        config_identity=payload.get("config_identity"),
        provider_config_refs=tuple(dict(item) for item in (payload.get("provider_config_refs") or [])),
        feature_schema_refs=tuple(dict(item) for item in (payload.get("feature_schema_refs") or [])),
        router_version=payload.get("router_version"),
        model_versions=tuple(dict(item) for item in (payload.get("model_versions") or [])),
        fusion_version=payload.get("fusion_version"),
        calibration_version=payload.get("calibration_version"),
        strategy_version=payload.get("strategy_version"),
        prediction_version=payload.get("prediction_version"),
        environment=dict(payload.get("environment") or {}),
        component_lineage=component_lineage_from_dict(payload.get("component_lineage")),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["RunManifestV1", "run_manifest_v1_from_dict", "run_manifest_v1_to_dict"]
