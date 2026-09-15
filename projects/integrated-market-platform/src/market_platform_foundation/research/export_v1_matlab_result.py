"""MATLAB research result artifact v1 — governed import lineage (no runtime authority)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .edge_stats.artifact import AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
from .export_v1 import (
    EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE,
    ResearchExportV1Package,
    build_matlab_parity_reference,
    require_operator_export_metadata,
)

MATLAB_RESEARCH_RESULT_SCHEMA_VERSION = "matlab_research_result/1.0.0"
MATLAB_RESEARCH_RESULT_CONTRACT = "research_export_v1_matlab_result/1.0.0"
MATLAB_RESEARCH_EVIDENCE_ARTIFACT_TYPE = "MATLAB_RESEARCH_EVIDENCE_ARTIFACT"
MATLAB_RESEARCH_ENGINE_VERSION = "research.matlab_governed_roundtrip/1.0.0"
MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY = "MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY"
MATLAB_RUNTIME_NOT_AVAILABLE = "MATLAB_RUNTIME_NOT_AVAILABLE"
CONTRACT_READY = "CONTRACT_READY"

ANALYSIS_TYPE_PARITY_REFERENCE = "parity_reference_statistics"
PIT_CLASS_FIXTURE_NON_EMPIRICAL = "NON_EMPIRICAL_FIXTURE_OPERATOR_PENDING"

_REQUIRED_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "matlab_result_contract",
        "export_id",
        "analysis_type",
        "input_manifest_hash",
        "input_source_sha256",
        "dataset_lineage",
        "parameters",
        "result_values",
        "diagnostics",
        "generated_at",
        "authority_class",
        "content_sha256",
    }
)


def _iso_utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def export_dataset_lineage(manifest: dict[str, Any]) -> dict[str, str]:
    dataset_manifest = manifest.get("dataset_manifest")
    dataset_hash = ""
    if isinstance(dataset_manifest, dict):
        dataset_hash = str(
            dataset_manifest.get("dataset_hash")
            or dataset_manifest.get("content_hash")
            or dataset_manifest.get("manifest_hash")
            or ""
        )
    return {
        "export_id": str(manifest.get("export_id") or ""),
        "manifest_hash": str(manifest.get("manifest_hash") or ""),
        "source_sha256": str(manifest.get("source_sha256") or ""),
        "dataset_hash": dataset_hash,
        "experiment_id": str(manifest.get("experiment_id") or ""),
        "export_profile": str(manifest.get("export_profile") or ""),
    }


def build_parity_matlab_research_result(
    package: ResearchExportV1Package,
    *,
    analysis_source: str,
    matlab_release: str | None = None,
    matlab_runtime_root: str | None = None,
    code_identity: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic parity result from export tables (features vs labels separated)."""
    require_operator_export_metadata(package.manifest)
    parity = build_matlab_parity_reference(package)
    stats = parity["reference_statistics"]
    meta = package.manifest.get("metadata") if isinstance(package.manifest.get("metadata"), dict) else {}
    lineage = export_dataset_lineage(package.manifest)
    body: dict[str, Any] = {
        "schema_version": MATLAB_RESEARCH_RESULT_SCHEMA_VERSION,
        "matlab_result_contract": MATLAB_RESEARCH_RESULT_CONTRACT,
        "export_id": lineage["export_id"],
        "hypothesis_id": f"{lineage['experiment_id']}:{lineage['export_profile']}",
        "experiment_id": lineage["experiment_id"],
        "analysis_type": ANALYSIS_TYPE_PARITY_REFERENCE,
        "input_manifest_hash": lineage["manifest_hash"],
        "input_source_sha256": lineage["source_sha256"],
        "dataset_lineage": lineage,
        "parameters": {
            "analysis_source": analysis_source,
            "code_identity": code_identity,
            "decision_time_feature_fields": ("feature_values.bar_close",),
            "label_fields_excluded_from_features": (
                "forward_return",
                "actual",
                "label_available_time_ns",
            ),
            "pit_operator_status": meta.get("pit_status"),
            "evidence_class": meta.get("evidence_class"),
        },
        "result_values": {
            "reference_statistics": stats,
            "parity_contract": parity.get("matlab_loader_contract"),
        },
        "uncertainty": {"status": "NOT_COMPUTED", "reason": "DETERMINISTIC_PARITY_SMOKE"},
        "diagnostics": {
            "feature_row_count": stats.get("feature_row_count"),
            "outcome_row_count": stats.get("outcome_row_count"),
            "lookahead_guard": "LABEL_FIELDS_NOT_IN_FEATURE_SNAPSHOTS",
        },
        "runtime": {
            "matlab_release": matlab_release or "UNAVAILABLE",
            "matlab_root": matlab_runtime_root,
            "toolbox_manifest_recorded": False,
        },
        "generated_at": generated_at or _iso_utc_now(),
        "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        "pit_class": PIT_CLASS_FIXTURE_NON_EMPIRICAL,
    }
    body["content_sha256"] = matlab_research_result_content_sha256(body)
    return body


def matlab_research_result_content_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "content_sha256"}
    return sha256_bytes(canonical_bytes(body)).upper()


def validate_matlab_research_result_v1(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("MATLAB_RESULT_NOT_OBJECT")
    missing = sorted(key for key in _REQUIRED_RESULT_KEYS if key not in payload)
    if missing:
        raise ValueError(f"MATLAB_RESULT_MISSING_FIELDS:{','.join(missing)}")
    if payload.get("schema_version") != MATLAB_RESEARCH_RESULT_SCHEMA_VERSION:
        raise ValueError("MATLAB_RESULT_SCHEMA_VERSION_MISMATCH")
    if payload.get("matlab_result_contract") != MATLAB_RESEARCH_RESULT_CONTRACT:
        raise ValueError("MATLAB_RESULT_CONTRACT_MISMATCH")
    if payload.get("authority_class") != AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION:
        raise ValueError("MATLAB_RESULT_AUTHORITY_FORBIDDEN")
    declared = str(payload.get("content_sha256") or "").upper()
    computed = matlab_research_result_content_sha256(payload)
    if declared and declared != computed:
        raise ValueError("MATLAB_RESULT_CONTENT_SHA256_MISMATCH")
    evidence_class = (payload.get("parameters") or {}).get("evidence_class")
    if evidence_class == EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE:
        if payload.get("pit_class") != PIT_CLASS_FIXTURE_NON_EMPIRICAL:
            raise ValueError("MATLAB_RESULT_PIT_CLASS_FIXTURE_REQUIRED")


def verify_matlab_result_export_lineage(
    result: dict[str, Any],
    package: ResearchExportV1Package,
) -> None:
    validate_matlab_research_result_v1(result)
    lineage = export_dataset_lineage(package.manifest)
    if str(result.get("export_id")) != lineage["export_id"]:
        raise ValueError("MATLAB_RESULT_EXPORT_ID_MISMATCH")
    if str(result.get("input_manifest_hash")) != lineage["manifest_hash"]:
        raise ValueError("MATLAB_RESULT_MANIFEST_HASH_MISMATCH")
    if str(result.get("input_source_sha256")) != lineage["source_sha256"]:
        raise ValueError("MATLAB_RESULT_SOURCE_SHA256_MISMATCH")
    reference = build_matlab_parity_reference(package)
    result_stats = (result.get("result_values") or {}).get("reference_statistics")
    if result_stats != reference["reference_statistics"]:
        raise ValueError("MATLAB_RESULT_STATISTICS_MISMATCH")


def project_matlab_research_evidence_artifact(result: dict[str, Any]) -> dict[str, Any]:
    """Map MATLAB result payload to generic research-evidence artifact (not opportunity rank)."""
    validate_matlab_research_result_v1(result)
    dataset_lineage = result.get("dataset_lineage") if isinstance(result.get("dataset_lineage"), dict) else {}
    body: dict[str, Any] = {
        "artifact_type": MATLAB_RESEARCH_EVIDENCE_ARTIFACT_TYPE,
        "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        "schema_version": "1.0.0",
        "engine_version": MATLAB_RESEARCH_ENGINE_VERSION,
        "generated_at": result.get("generated_at"),
        "pit_class": result.get("pit_class"),
        "analysis_type": result.get("analysis_type"),
        "dataset": {
            "export_id": dataset_lineage.get("export_id"),
            "source_sha256": dataset_lineage.get("source_sha256"),
            "manifest_hash": dataset_lineage.get("manifest_hash"),
            "dataset_hash": dataset_lineage.get("dataset_hash"),
            "collection_relative_path": "research_export_v1/matlab_roundtrip",
        },
        "query": {
            "version_hash": matlab_research_result_content_sha256(result),
            "analysis_source": (result.get("parameters") or {}).get("analysis_source"),
            "code_identity": (result.get("parameters") or {}).get("code_identity"),
        },
        "matlab_research_context": {
            "result_content_sha256": result.get("content_sha256"),
            "result_values": result.get("result_values"),
            "uncertainty": result.get("uncertainty"),
            "diagnostics": result.get("diagnostics"),
            "runtime": result.get("runtime"),
        },
        "lineage_kind": "matlab_governed_research_result",
    }
    from .edge_stats.artifact import evidence_artifact_content_sha256

    body["content_sha256"] = evidence_artifact_content_sha256(body)
    return body


def roundtrip_readiness(
    *,
    matlab_runtime_available: bool,
    lineage_verified: bool,
) -> str:
    if lineage_verified and matlab_runtime_available:
        return MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY
    if lineage_verified:
        return CONTRACT_READY
    if not matlab_runtime_available:
        return MATLAB_RUNTIME_NOT_AVAILABLE
    return "MATLAB_ROUNDTRIP_LINEAGE_FAILED"


__all__ = [
    "ANALYSIS_TYPE_PARITY_REFERENCE",
    "CONTRACT_READY",
    "MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY",
    "MATLAB_RESEARCH_EVIDENCE_ARTIFACT_TYPE",
    "MATLAB_RESEARCH_ENGINE_VERSION",
    "MATLAB_RESEARCH_RESULT_CONTRACT",
    "MATLAB_RESEARCH_RESULT_SCHEMA_VERSION",
    "MATLAB_RUNTIME_NOT_AVAILABLE",
    "build_parity_matlab_research_result",
    "export_dataset_lineage",
    "matlab_research_result_content_sha256",
    "project_matlab_research_evidence_artifact",
    "roundtrip_readiness",
    "validate_matlab_research_result_v1",
    "verify_matlab_result_export_lineage",
]
