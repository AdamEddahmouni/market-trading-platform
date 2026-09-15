"""Generic research-artifact evidence projections for opportunity detail/evidence APIs."""

from __future__ import annotations

from typing import Any

from ...research.edge_stats.artifact import AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
from ...research.edge_stats.precomputed_catalog import resolve_precomputed_research_artifact
from ...research.options_flow_replay import OPTIONS_FLOW_REPLAY_EVIDENCE_READY
from ...research.options_flow_replay.artifact import ARTIFACT_TYPE as OPTIONS_FLOW_REPLAY_ARTIFACT_TYPE
from ..contracts.research_artifact_attachment import OpportunityResearchArtifactAttachmentV1

EDGE_STATS_OPPORTUNITY_EVIDENCE_READY = "EDGE_STATS_OPPORTUNITY_EVIDENCE_READY"
RESEARCH_EVIDENCE_ARTIFACT_LINEAGE_KIND = "research_evidence_artifact"
_EDGE_STATS_ARTIFACT_TYPE = "EDGE_STATS_EVIDENCE_ARTIFACT"

_STABILITY_DIVERGENCE_THRESHOLD = 0.25


def derive_stability_status(recent_full_comparison: dict[str, Any]) -> dict[str, Any]:
    full = recent_full_comparison.get("full") if isinstance(recent_full_comparison, dict) else {}
    recent = recent_full_comparison.get("recent_half") if isinstance(recent_full_comparison, dict) else {}
    if not isinstance(full, dict) or not isinstance(recent, dict):
        return {"status": "UNAVAILABLE", "reason": "MISSING_COMPARISON"}
    if full.get("status") == "INSUFFICIENT_DATA" or recent.get("status") == "INSUFFICIENT_DATA":
        return {"status": "INSUFFICIENT_DATA", "reason": "THIN_SAMPLE_IN_SPLIT"}
    full_est = full.get("estimate")
    recent_est = recent.get("estimate")
    if full_est is None or recent_est is None:
        return {"status": "UNAVAILABLE", "reason": "MISSING_ESTIMATE"}
    full_f = float(full_est)
    recent_f = float(recent_est)
    if full_f == 0.0:
        relative = abs(recent_f - full_f)
    else:
        relative = abs((recent_f - full_f) / full_f)
    rounded = round(relative, 6)
    if relative <= _STABILITY_DIVERGENCE_THRESHOLD:
        return {"status": "STABLE", "relative_divergence": rounded}
    return {"status": "DIVERGENT", "relative_divergence": rounded}


def project_historical_statistical_context(artifact: dict[str, Any]) -> dict[str, Any]:
    """Operator-facing panel fields — evidence only, never execution authority."""

    ci = artifact.get("ci") if isinstance(artifact.get("ci"), dict) else {}
    dataset = artifact.get("dataset") if isinstance(artifact.get("dataset"), dict) else {}
    query = artifact.get("query") if isinstance(artifact.get("query"), dict) else {}
    recent_full = (
        artifact.get("recent_full_comparison")
        if isinstance(artifact.get("recent_full_comparison"), dict)
        else {}
    )
    return {
        "authority_class": str(artifact.get("authority_class") or AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION),
        "artifact_type": str(artifact.get("artifact_type") or ""),
        "sample_n": artifact.get("n"),
        "estimate": artifact.get("estimate"),
        "confidence_interval": {
            "status": ci.get("status"),
            "ci_lower": ci.get("ci_lower"),
            "ci_upper": ci.get("ci_upper"),
            "sample_count": ci.get("sample_count"),
        },
        "recent_full_comparison": recent_full,
        "stability_status": derive_stability_status(recent_full),
        "regime_splits": artifact.get("regime_splits"),
        "time_splits": artifact.get("time_splits"),
        "dataset": {
            "source_object_id": dataset.get("source_object_id"),
            "source_sha256": dataset.get("source_sha256"),
            "collection_relative_path": dataset.get("collection_relative_path"),
            "bar_count": dataset.get("bar_count"),
        },
        "query_version_hash": query.get("version_hash"),
        "schema_version": artifact.get("schema_version"),
        "engine_version": artifact.get("engine_version"),
        "content_sha256": artifact.get("content_sha256"),
        "generated_at": artifact.get("generated_at"),
        "pit_class": artifact.get("pit_class"),
    }


def project_options_flow_transparent_context(artifact: dict[str, Any]) -> dict[str, Any]:
    """Operator-facing replay decomposition — no vendor composite / ranking score."""

    dataset = artifact.get("dataset") if isinstance(artifact.get("dataset"), dict) else {}
    query = artifact.get("query") if isinstance(artifact.get("query"), dict) else {}
    aggregate = artifact.get("aggregate") if isinstance(artifact.get("aggregate"), dict) else {}
    prints = artifact.get("decomposed_prints") if isinstance(artifact.get("decomposed_prints"), list) else []
    return {
        "authority_class": str(artifact.get("authority_class") or AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION),
        "artifact_type": str(artifact.get("artifact_type") or ""),
        "replay_mode": artifact.get("replay_mode"),
        "live_feed_claim": artifact.get("live_feed_claim"),
        "print_count": aggregate.get("print_count"),
        "trade_class_counts": aggregate.get("trade_class_counts"),
        "missing_data_fields_union": aggregate.get("missing_data_fields_union"),
        "decomposed_prints": prints,
        "explicit_exclusions": artifact.get("explicit_exclusions"),
        "dataset": {
            "admission_id": dataset.get("admission_id"),
            "fixture_id": dataset.get("fixture_id"),
            "instrument_id": dataset.get("instrument_id"),
            "source_object_id": dataset.get("source_object_id"),
            "source_sha256": dataset.get("source_sha256"),
            "collection_relative_path": dataset.get("collection_relative_path"),
            "activity_count": dataset.get("activity_count"),
        },
        "query_version_hash": query.get("version_hash"),
        "schema_version": artifact.get("schema_version"),
        "engine_version": artifact.get("engine_version"),
        "content_sha256": artifact.get("content_sha256"),
        "generated_at": artifact.get("generated_at"),
        "pit_class": artifact.get("pit_class"),
    }


def _readiness_for_resolved_types(resolved_types: set[str]) -> str:
    if not resolved_types:
        return EDGE_STATS_OPPORTUNITY_EVIDENCE_READY
    if resolved_types == {OPTIONS_FLOW_REPLAY_ARTIFACT_TYPE}:
        return OPTIONS_FLOW_REPLAY_EVIDENCE_READY
    if resolved_types == {_EDGE_STATS_ARTIFACT_TYPE}:
        return EDGE_STATS_OPPORTUNITY_EVIDENCE_READY
    return "MULTI_RESEARCH_ARTIFACT_EVIDENCE_READY"


def resolve_attachment_artifact(
    attachment: OpportunityResearchArtifactAttachmentV1,
) -> dict[str, Any] | None:
    artifact = resolve_precomputed_research_artifact(
        artifact_type=attachment.artifact_type,
        content_sha256=attachment.content_sha256,
    )
    if artifact is None:
        return None
    if attachment.query_version_hash:
        query = artifact.get("query") if isinstance(artifact.get("query"), dict) else {}
        if str(query.get("version_hash") or "") != attachment.query_version_hash:
            return None
    return artifact


def project_attachment_read_model(
    attachment: OpportunityResearchArtifactAttachmentV1,
) -> dict[str, Any]:
    artifact = resolve_attachment_artifact(attachment)
    if artifact is None:
        return {
            "attachment_id": attachment.attachment_id,
            "artifact_type": attachment.artifact_type,
            "content_sha256": attachment.content_sha256,
            "status": "UNRESOLVED",
            "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        }
    read_model: dict[str, Any] = {
        "attachment_id": attachment.attachment_id,
        "artifact_type": attachment.artifact_type,
        "content_sha256": attachment.content_sha256,
        "status": "RESOLVED",
        "authority_class": artifact.get("authority_class"),
    }
    artifact_type = str(artifact.get("artifact_type") or "")
    if artifact_type == OPTIONS_FLOW_REPLAY_ARTIFACT_TYPE:
        read_model["options_flow_transparent_context"] = project_options_flow_transparent_context(artifact)
    elif artifact_type == _EDGE_STATS_ARTIFACT_TYPE:
        read_model["historical_statistical_context"] = project_historical_statistical_context(artifact)
    else:
        read_model["opaque_artifact_keys"] = sorted(
            key for key in artifact.keys() if key not in {"content_sha256"}
        )
    return read_model


def project_opportunity_research_artifact_evidence(
    attachments: tuple[OpportunityResearchArtifactAttachmentV1, ...],
) -> dict[str, Any]:
    models = [project_attachment_read_model(row) for row in attachments]
    resolved_types = {
        str(model.get("artifact_type"))
        for model in models
        if model.get("status") == "RESOLVED" and model.get("artifact_type")
    }
    return {
        "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        "readiness": _readiness_for_resolved_types(resolved_types),
        "attachments": models,
    }


__all__ = [
    "EDGE_STATS_OPPORTUNITY_EVIDENCE_READY",
    "OPTIONS_FLOW_REPLAY_EVIDENCE_READY",
    "RESEARCH_EVIDENCE_ARTIFACT_LINEAGE_KIND",
    "derive_stability_status",
    "project_attachment_read_model",
    "project_historical_statistical_context",
    "project_options_flow_transparent_context",
    "project_opportunity_research_artifact_evidence",
    "resolve_attachment_artifact",
]
