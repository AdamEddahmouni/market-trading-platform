"""Project admitted evidence artifacts into in-memory payloads (fixture-only)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectedArtifact:
    artifact_ref: str
    source_type: str
    payload: Any
    support_hash: str


def artifact_support_hash(repository_root: Path, artifact_ref: str) -> str:
    path = repository_root / artifact_ref
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def load_projected_artifacts(
    repository_root: Path,
    evidence_set: dict[str, Any],
) -> list[ProjectedArtifact]:
    projected: list[ProjectedArtifact] = []
    for source in evidence_set.get("sources") or []:
        if not isinstance(source, dict):
            continue
        artifact_ref = str(source.get("artifact_ref") or "")
        if not artifact_ref:
            continue
        path = repository_root / artifact_ref
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        projected.append(
            ProjectedArtifact(
                artifact_ref=artifact_ref,
                source_type=str(source.get("source_type") or ""),
                payload=payload,
                support_hash=artifact_support_hash(repository_root, artifact_ref),
            )
        )
    return projected


def primary_artifact(projected: list[ProjectedArtifact]) -> ProjectedArtifact | None:
    return projected[0] if projected else None


__all__ = [
    "ProjectedArtifact",
    "artifact_support_hash",
    "load_projected_artifacts",
    "primary_artifact",
]
