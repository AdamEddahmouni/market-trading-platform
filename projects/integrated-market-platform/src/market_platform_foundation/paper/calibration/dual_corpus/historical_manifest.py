"""Versioned historical development dataset manifest (not opaque CSV as SoT)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ....canonical import canonical_bytes, sha256_bytes
from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    resolve_effective_corpus_evidence_authority,
)
from .historical_provenance import validate_historical_development_provenance

HISTORICAL_DATASET_MANIFEST_KIND = "historical_development_dataset_manifest_v1"
HISTORICAL_DATASET_SCHEMA_VERSION = "dual_corpus.historical-dataset-manifest/1.0.0"

_MANIFEST_REQUIRED: tuple[str, ...] = (
    "artifact_kind",
    "schema_version",
    "dataset_id",
    "dataset_version",
    "corpus_evidence_authority",
    "providers",
    "universe",
    "interval",
    "session_policy",
    "bar_resolution",
    "source_artifacts",
    "normalized_artifact_ref",
    "row_count",
    "duplicate_row_count",
    "excluded_row_count",
    "missing_intervals",
    "dataset_fingerprint",
    "lineage",
    "code_sha",
    "created_at_ns",
)


def _manifest_body_fingerprint(body: Mapping[str, Any]) -> str:
    payload = dict(body)
    payload.pop("dataset_fingerprint", None)
    return sha256_bytes(canonical_bytes(payload))


def validate_historical_development_dataset_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in _MANIFEST_REQUIRED if key not in manifest]
    if missing:
        return {"ok": False, "reason_code": "MANIFEST_INCOMPLETE", "missing_fields": missing}
    if str(manifest.get("artifact_kind") or "") != HISTORICAL_DATASET_MANIFEST_KIND:
        return {"ok": False, "reason_code": "MANIFEST_KIND_INVALID", "missing_fields": ("artifact_kind",)}
    resolved = resolve_effective_corpus_evidence_authority(
        manifest_authority=str(manifest.get("corpus_evidence_authority") or ""),
        payload=manifest,
    )
    if not resolved.get("ok"):
        return {
            "ok": False,
            "reason_code": str(resolved.get("reason_code") or "AUTHORITY_INVALID"),
            "missing_fields": (),
        }
    if resolved["effective_authority"] != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return {"ok": False, "reason_code": "MANIFEST_NOT_HISTORICAL_DEVELOPMENT", "missing_fields": ()}
    expected_fp = _manifest_body_fingerprint(manifest)
    if str(manifest.get("dataset_fingerprint") or "") != expected_fp:
        return {"ok": False, "reason_code": "MANIFEST_FINGERPRINT_MISMATCH", "missing_fields": ()}
    lineage = manifest.get("lineage")
    if isinstance(lineage, Mapping):
        prov = lineage.get("historical_provenance")
        if isinstance(prov, Mapping):
            prov_gate = validate_historical_development_provenance(prov)
            if not prov_gate["ok"]:
                return {
                    "ok": False,
                    "reason_code": str(prov_gate.get("reason_code")),
                    "missing_fields": prov_gate.get("missing_fields", ()),
                }
    return {"ok": True, "reason_code": None, "missing_fields": ()}


def build_historical_development_dataset_manifest(
    *,
    dataset_id: str,
    dataset_version: str,
    providers: Sequence[str],
    universe: Sequence[str],
    interval: Mapping[str, Any],
    session_policy: str,
    bar_resolution: str,
    source_artifacts: Sequence[Mapping[str, Any]],
    normalized_artifact_ref: str,
    row_count: int,
    duplicate_row_count: int,
    excluded_row_count: int,
    missing_intervals: Sequence[Mapping[str, Any]],
    lineage: Mapping[str, Any],
    code_sha: str,
    created_at_ns: int,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_kind": HISTORICAL_DATASET_MANIFEST_KIND,
        "schema_version": HISTORICAL_DATASET_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "providers": list(providers),
        "universe": list(universe),
        "interval": dict(interval),
        "session_policy": session_policy,
        "bar_resolution": bar_resolution,
        "source_artifacts": [dict(item) for item in source_artifacts],
        "normalized_artifact_ref": normalized_artifact_ref,
        "row_count": int(row_count),
        "duplicate_row_count": int(duplicate_row_count),
        "excluded_row_count": int(excluded_row_count),
        "missing_intervals": [dict(item) for item in missing_intervals],
        "lineage": dict(lineage),
        "code_sha": code_sha,
        "created_at_ns": int(created_at_ns),
    }
    body["dataset_fingerprint"] = _manifest_body_fingerprint(body)
    return body


__all__ = [
    "HISTORICAL_DATASET_MANIFEST_KIND",
    "HISTORICAL_DATASET_SCHEMA_VERSION",
    "build_historical_development_dataset_manifest",
    "validate_historical_development_dataset_manifest",
]
