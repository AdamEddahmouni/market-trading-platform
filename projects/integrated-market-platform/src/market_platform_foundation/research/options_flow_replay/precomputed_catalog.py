"""Read-only catalog entry for golden options-flow replay artifact."""

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
    / "options_flow_replay_golden_artifact.json"
)


@lru_cache(maxsize=1)
def _golden_nvda_default_artifact() -> dict[str, Any]:
    artifact = load_json_strict(_GOLDEN_FIXTURE)
    if not isinstance(artifact, dict):
        raise ValueError("OPTIONS_FLOW_REPLAY_GOLDEN_FIXTURE_INVALID")
    computed = evidence_artifact_content_sha256(artifact)
    declared = str(artifact.get("content_sha256") or "").upper()
    if computed != declared:
        raise ValueError("OPTIONS_FLOW_REPLAY_GOLDEN_CONTENT_SHA256_MISMATCH")
    return artifact


def list_precomputed_options_flow_replay_artifacts() -> tuple[dict[str, Any], ...]:
    return (_golden_nvda_default_artifact(),)


__all__ = ["list_precomputed_options_flow_replay_artifacts"]
