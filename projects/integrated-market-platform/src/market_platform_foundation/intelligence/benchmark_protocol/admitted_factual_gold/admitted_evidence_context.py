"""Load SUT-visible admitted evidence from EVIDENCE_SET (no evaluator gold)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..historical_evidence_context import build_historical_fixture_evidence_context
from .types import AdmittedFactualSourceType

_ADMITTED_EVIDENCE_DATA_MODE = "FIXTURE_REPLAY"
_ADMITTED_EVIDENCE_AUTHORITY = "ADMITTED_EVIDENCE_FIXED"


def required_artifact_refs(evidence_set: dict[str, Any]) -> list[str]:
    sources = evidence_set.get("sources") or []
    refs: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        ref = source.get("artifact_ref")
        if ref:
            refs.append(str(ref))
    return refs


def _load_static_admitted_json(
    repository_root: Path,
    *,
    artifact_ref: str,
    source_type: str,
) -> dict[str, Any] | None:
    path = repository_root / artifact_ref
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "admitted_artifact_ref": artifact_ref,
        "admitted_source_type": source_type,
        "admitted_payload_kind": "json",
        "admitted_payload": payload,
        "evidence_data_mode": _ADMITTED_EVIDENCE_DATA_MODE,
        "evidence_authority": _ADMITTED_EVIDENCE_AUTHORITY,
        "live_promotion_allowed": False,
    }


def load_admitted_source_context(
    repository_root: Path,
    source: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve one admitted source row to an evidence context fragment."""
    source_type = str(source.get("source_type") or "")
    artifact_ref = str(source.get("artifact_ref") or "")
    if not artifact_ref:
        return None

    if source_type == AdmittedFactualSourceType.HISTORICAL_DEVELOPMENT_ARTIFACT.value:
        historical = build_historical_fixture_evidence_context(repository_root, artifact_ref)
        if historical is not None:
            return {
                **historical,
                "admitted_artifact_ref": artifact_ref,
                "admitted_source_type": source_type,
                "evidence_data_mode": _ADMITTED_EVIDENCE_DATA_MODE,
                "evidence_authority": _ADMITTED_EVIDENCE_AUTHORITY,
                "live_promotion_allowed": False,
            }
        return _load_static_admitted_json(
            repository_root,
            artifact_ref=artifact_ref,
            source_type=source_type,
        )

    if source_type in {
        AdmittedFactualSourceType.GOVERNED_RESEARCH_MANIFEST.value,
        AdmittedFactualSourceType.ADMITTED_FIXTURE_RECORD.value,
        AdmittedFactualSourceType.CORPUS_SNAPSHOT_REF.value,
    }:
        return _load_static_admitted_json(
            repository_root,
            artifact_ref=artifact_ref,
            source_type=source_type,
        )

    return None


def build_admitted_evidence_context(
    repository_root: Path,
    evidence_set: dict[str, Any],
) -> dict[str, Any]:
    """Merge admitted sources into one harness context; fails closed on missing artifacts."""
    sources = evidence_set.get("sources") or []
    loaded_refs: list[str] = []
    fragments: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        fragment = load_admitted_source_context(repository_root, source)
        ref = str(source.get("artifact_ref") or "")
        if fragment is None:
            continue
        loaded_refs.append(ref)
        fragments.append(fragment)

    merged: dict[str, Any] = {
        "admitted_evidence_artifacts_loaded": loaded_refs,
        "admitted_evidence_access_mode": evidence_set.get("evidence_access_mode"),
        "evidence_data_mode": _ADMITTED_EVIDENCE_DATA_MODE,
        "evidence_authority": _ADMITTED_EVIDENCE_AUTHORITY,
        "live_promotion_allowed": False,
        "admitted_source_fragments": fragments,
    }
    for fragment in fragments:
        if callable(fragment.get("resolve_explain")):
            merged["resolve_explain"] = fragment["resolve_explain"]
        if callable(fragment.get("resolve_inspect")):
            merged["resolve_inspect"] = fragment["resolve_inspect"]
        if fragment.get("available_explain_refs"):
            merged["available_explain_refs"] = fragment["available_explain_refs"]
    return merged


def admitted_artifacts_accessible(
    repository_root: Path,
    evidence_set: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Return whether every declared artifact_ref is loadable on disk."""
    required = required_artifact_refs(evidence_set)
    context = build_admitted_evidence_context(repository_root, evidence_set)
    loaded = set(context.get("admitted_evidence_artifacts_loaded") or ())
    missing = [ref for ref in required if ref not in loaded]
    return (not missing, missing)


__all__ = [
    "admitted_artifacts_accessible",
    "build_admitted_evidence_context",
    "load_admitted_source_context",
    "required_artifact_refs",
]
