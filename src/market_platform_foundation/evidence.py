"""Canonical, immutable Phase 0 evidence publication."""

from __future__ import annotations

import uuid
from pathlib import Path

from .canonical import canonical_bytes, sha256_bytes

_FINALIZED: set[Path] = set()


def _record(
    logical_id: str,
    content: object,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    content_sha256 = sha256_bytes(canonical_bytes(content))
    supplied = dict(metadata or {})
    return {
        "artifact_type": "PHASE0_EVIDENCE_RECORD",
        "content": content,
        "content_sha256": content_sha256,
        "exclusions": supplied.pop("exclusions", []),
        "inputs": supplied.pop("inputs", []),
        "logical_id": logical_id,
        "media_type": "application/json",
        "procedure_versions": supplied.pop("procedure_versions", {}),
        "sanitization": supplied.pop(
            "sanitization",
            {
                "absolute_paths_included": False,
                "account_identifiers_included": False,
                "credential_values_included": False,
                "environment_values_included": False,
                "remote_urls_included": False,
            },
        ),
        "scope": supplied.pop("scope", "PHASE_0_STEPS_9_THROUGH_13"),
        "source_manifest_sha256": supplied.pop("source_manifest_sha256", "UNBOUND"),
        "status": supplied.pop("status", "FINALIZED"),
        **supplied,
    }


def finalize_artifact(
    path: Path,
    logical_id: str,
    content: object,
    metadata: dict[str, object] | None = None,
) -> str:
    target = path.resolve()
    if path.exists() or target in _FINALIZED:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(_record(logical_id, content, metadata))
    staging = path.parent / f".staging-{uuid.uuid4().hex}"
    try:
        staging.write_bytes(data)
        if path.exists():
            raise FileExistsError(path)
        staging.replace(path)
    finally:
        if staging.exists():
            staging.unlink()
    _FINALIZED.add(target)
    return sha256_bytes(data)


def _filename(logical_id: str) -> str:
    name = logical_id.removeprefix("phase0.").replace("_", "-").replace(".", "-")
    return name + ".json"


def publish_artifacts(
    output_dir: Path,
    artifacts: list[tuple[str, object]],
    metadata: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    logical_ids = [logical_id for logical_id, _content in artifacts]
    if len(logical_ids) != len(set(logical_ids)):
        raise ValueError("duplicate logical ID")
    index: list[dict[str, object]] = []
    for logical_id, content in sorted(artifacts, key=lambda row: row[0]):
        path = output_dir / _filename(logical_id)
        digest = finalize_artifact(path, logical_id, content, metadata)
        index.append(
            {
                "byte_length": path.stat().st_size,
                "logical_id": logical_id,
                "media_type": "application/json",
                "path": path.name,
                "sha256": digest,
            }
        )
    return index

