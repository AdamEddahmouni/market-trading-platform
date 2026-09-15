"""Read-only catalog of precomputed edge-stats evidence artifacts (no hot-path compute)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ...canonical import load_json_strict
from .artifact import evidence_artifact_content_sha256

_GOLDEN_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "research"
    / "edge_stats_golden_artifact.json"
)


@lru_cache(maxsize=1)
def _golden_biya_default_artifact() -> dict[str, Any]:
    artifact = load_json_strict(_GOLDEN_FIXTURE)
    if not isinstance(artifact, dict):
        raise ValueError("EDGE_STATS_GOLDEN_FIXTURE_INVALID")
    computed = evidence_artifact_content_sha256(artifact)
    declared = str(artifact.get("content_sha256") or "").upper()
    if computed != declared:
        raise ValueError("EDGE_STATS_GOLDEN_CONTENT_SHA256_MISMATCH")
    return artifact


def list_precomputed_edge_stats_artifacts() -> tuple[dict[str, Any], ...]:
    return (_golden_biya_default_artifact(),)


def resolve_precomputed_research_artifact(
    *,
    artifact_type: str,
    content_sha256: str,
) -> dict[str, Any] | None:
    target_type = str(artifact_type)
    target_sha = str(content_sha256).upper()
    if target_type != "EDGE_STATS_EVIDENCE_ARTIFACT":
        return None
    for artifact in list_precomputed_edge_stats_artifacts():
        if str(artifact.get("artifact_type")) != target_type:
            continue
        if str(artifact.get("content_sha256") or "").upper() == target_sha:
            return artifact
    return None


__all__ = [
    "list_precomputed_edge_stats_artifacts",
    "resolve_precomputed_research_artifact",
]
