"""Artifact layout for historical RTH development corpora."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def default_artifact_root(repository_root: Path) -> Path:
    return repository_root / "artifacts" / "historical-rth-development"


@dataclass(frozen=True, slots=True)
class RunArtifactPaths:
    run_root: Path
    raw_dir: Path
    normalized_dir: Path
    manifests_dir: Path
    quality_dir: Path


def run_artifact_paths(
    repository_root: Path,
    *,
    run_id: str,
    artifact_root: Path | None = None,
) -> RunArtifactPaths:
    base = artifact_root if artifact_root is not None else default_artifact_root(repository_root)
    run_root = base / "runs" / run_id
    return RunArtifactPaths(
        run_root=run_root,
        raw_dir=run_root / "raw",
        normalized_dir=run_root / "normalized",
        manifests_dir=run_root / "manifests",
        quality_dir=run_root / "quality",
    )


__all__ = ["RunArtifactPaths", "default_artifact_root", "run_artifact_paths"]
