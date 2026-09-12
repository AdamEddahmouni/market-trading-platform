"""Unified PIT-safe research export manifest (PIT-A-001).

Consolidates ADR-PIT-001 cutoff semantics and ADR-RDATA-001 dataset identity into
one immutable, hash-bound export record for offline research lanes. Does not
perform network I/O or authorize live ingestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes, write_canonical_json
from .dataset_manifest import build_dataset_manifest
from .dataset_pipeline import build_research_dataset_from_events

RESEARCH_EXPORT_SCHEMA_VERSION = "1.0.0"
ADR_PIT_LOGICAL_ID = "phase1.adr_pit_001"
ADR_RDATA_LOGICAL_ID = "phase1.adr_rdata_001"


def _normalize_sha256(value: str) -> str:
    cleaned = str(value).strip().upper()
    if len(cleaned) != 64 or any(ch not in "0123456789ABCDEF" for ch in cleaned):
        raise ValueError("INVALID_SOURCE_SHA256")
    return cleaned


def _normalize_experiment_binding(binding: dict[str, object] | None) -> dict[str, object]:
    if not binding:
        return {"binding_kind": "UNBOUND"}
    kind = str(binding.get("binding_kind", "DECISION_RESEARCH_CARD"))
    normalized: dict[str, object] = {"binding_kind": kind}
    for key in ("experiment_id", "card_hash", "protocol_id", "campaign_slug"):
        if key in binding and binding[key] is not None:
            normalized[key] = str(binding[key])
    return normalized


def _dataset_manifest_summary(dataset_manifest: dict[str, object]) -> dict[str, object]:
    fingerprint = dataset_manifest.get("dataset_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ValueError("DATASET_MANIFEST_FINGERPRINT_REQUIRED")
    member_files = dataset_manifest.get("member_files")
    if not isinstance(member_files, list):
        raise ValueError("DATASET_MANIFEST_MEMBER_FILES_REQUIRED")
    return {
        "admission_reference": dataset_manifest.get("admission_reference"),
        "dataset_fingerprint": fingerprint,
        "dataset_schema_version": dataset_manifest.get("dataset_schema_version"),
        "member_files": member_files,
        "row_count": dataset_manifest.get("row_count"),
        "source_content_hash": dataset_manifest.get("source_content_hash"),
    }


def research_export_fingerprint(body: dict[str, object]) -> str:
    payload = dict(body)
    payload.pop("export_fingerprint", None)
    return sha256_bytes(canonical_bytes(payload))


def build_research_export_manifest(
    dataset_manifest: dict[str, object],
    *,
    source_sha256: str,
    prediction_cutoff_ns: int,
    experiment_binding: dict[str, object] | None = None,
    repository_head_sha: str | None = None,
) -> dict[str, object]:
    """Bind dataset identity, source bytes, PIT cutoff, and experiment metadata."""
    if prediction_cutoff_ns < 0:
        raise ValueError("INVALID_PREDICTION_CUTOFF")
    body: dict[str, object] = {
        "adr_bindings": {
            "pit": ADR_PIT_LOGICAL_ID,
            "rdata": ADR_RDATA_LOGICAL_ID,
        },
        "dataset_manifest": _dataset_manifest_summary(dataset_manifest),
        "experiment_binding": _normalize_experiment_binding(experiment_binding),
        "prediction_cutoff_ns": int(prediction_cutoff_ns),
        "research_export_schema_version": RESEARCH_EXPORT_SCHEMA_VERSION,
        "source_sha256": _normalize_sha256(source_sha256),
    }
    if repository_head_sha:
        body["repository_head_sha"] = str(repository_head_sha).strip().lower()
    fingerprint = research_export_fingerprint(body)
    return {**body, "export_fingerprint": fingerprint}


def build_research_export_from_events(
    events: list[dict[str, Any]],
    *,
    source_sha256: str,
    prediction_cutoff_ns: int,
    experiment_binding: dict[str, object] | None = None,
    repository_head_sha: str | None = None,
) -> dict[str, object]:
    """Materialize admitted events into rows/manifest, then emit export binding."""
    _, dataset_manifest = build_research_dataset_from_events(events)
    return build_research_export_manifest(
        dataset_manifest,
        source_sha256=source_sha256,
        prediction_cutoff_ns=prediction_cutoff_ns,
        experiment_binding=experiment_binding,
        repository_head_sha=repository_head_sha,
    )


def build_research_export_from_rows(
    rows: list[dict[str, object]],
    *,
    source_sha256: str,
    prediction_cutoff_ns: int,
    experiment_binding: dict[str, object] | None = None,
    repository_head_sha: str | None = None,
    member_filename: str = "research-rows.json",
) -> dict[str, object]:
    dataset_manifest = build_dataset_manifest(rows, member_filename=member_filename)
    return build_research_export_manifest(
        dataset_manifest,
        source_sha256=source_sha256,
        prediction_cutoff_ns=prediction_cutoff_ns,
        experiment_binding=experiment_binding,
        repository_head_sha=repository_head_sha,
    )


def write_research_export_manifest(path: Path, manifest: dict[str, object]) -> None:
    """Persist canonical JSON; caller must not mutate file in place afterward."""
    if "export_fingerprint" not in manifest:
        raise ValueError("EXPORT_MANIFEST_INCOMPLETE")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json(path, manifest)
