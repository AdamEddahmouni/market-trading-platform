"""Research contamination audit input manifest (contractual lineage, not execution state)."""

from __future__ import annotations

from typing import Any, Mapping

RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND = "research_contamination_run_manifest_v1"
RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION = "dual_corpus.research-contamination-run/1.0.0"

_MANIFEST_REQUIRED: tuple[str, ...] = (
    "artifact_kind",
    "schema_version",
    "run_id",
    "lineage_complete",
    "authority_context",
    "splits",
)

_INTERVAL_KEYS = ("start_ns", "end_ns")


def _interval_ok(block: Mapping[str, Any] | None) -> bool:
    if not isinstance(block, Mapping):
        return False
    start = block.get("start_ns")
    end = block.get("end_ns")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    return start < end


def validate_research_contamination_run_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed when mandatory audit fields are missing or ill-formed."""

    missing = [key for key in _MANIFEST_REQUIRED if key not in manifest]
    if missing:
        return {"ok": False, "reason_code": "MANIFEST_INCOMPLETE", "missing_fields": tuple(missing)}
    if str(manifest.get("artifact_kind") or "") != RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND:
        return {"ok": False, "reason_code": "MANIFEST_KIND_INVALID", "missing_fields": ("artifact_kind",)}
    if str(manifest.get("schema_version") or "") != RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION:
        return {
            "ok": False,
            "reason_code": "MANIFEST_SCHEMA_VERSION_INVALID",
            "missing_fields": ("schema_version",),
        }
    if not str(manifest.get("run_id") or "").strip():
        return {"ok": False, "reason_code": "RUN_ID_REQUIRED", "missing_fields": ("run_id",)}
    if manifest.get("lineage_complete") is not True:
        return {"ok": False, "reason_code": "LINEAGE_INCOMPLETE", "missing_fields": ("lineage_complete",)}
    authority = manifest.get("authority_context")
    if not isinstance(authority, Mapping):
        return {"ok": False, "reason_code": "AUTHORITY_CONTEXT_REQUIRED", "missing_fields": ("authority_context",)}
    splits = manifest.get("splits")
    if not isinstance(splits, Mapping):
        return {"ok": False, "reason_code": "SPLITS_REQUIRED", "missing_fields": ("splits",)}
    for role in ("train", "test"):
        if role not in splits:
            return {"ok": False, "reason_code": "SPLIT_ROLE_MISSING", "missing_fields": (f"splits.{role}",)}
        if not _interval_ok(splits.get(role)):
            return {"ok": False, "reason_code": "SPLIT_INTERVAL_INVALID", "missing_fields": (f"splits.{role}",)}
    return {"ok": True, "reason_code": None, "missing_fields": ()}


__all__ = [
    "RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND",
    "RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION",
    "validate_research_contamination_run_manifest",
]
