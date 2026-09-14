"""HTTP adapter: research-artifact evidence attach + detail/evidence overlay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from ..intelligence.contracts.opportunity import OpportunityV1
from ..intelligence.ingest.research_artifact_attachment import (
    ResearchArtifactAttachmentRuntime,
    research_artifact_evidence_for_opportunity_detail,
    resolve_research_artifact_attachment_persistence,
)
from .store import ReplayStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _opportunity_getter(repository: Any) -> Callable[[str], OpportunityV1 | None] | None:
    getter = getattr(repository, "get_opportunity", None)
    if not callable(getter):
        return None

    def _lookup(opportunity_id: str) -> OpportunityV1 | None:
        record = getter(str(opportunity_id))
        return record if isinstance(record, OpportunityV1) else None

    return _lookup


def research_artifact_repository_for_store(store: ReplayStore):
    return resolve_research_artifact_attachment_persistence(getattr(store, "strategy_repository", None))


def _runtime_for_store(store: ReplayStore) -> ResearchArtifactAttachmentRuntime:
    repository = research_artifact_repository_for_store(store)
    return ResearchArtifactAttachmentRuntime(
        repository,
        get_opportunity=_opportunity_getter(repository),
    )


def _optional_runtime_for_store(store: ReplayStore) -> ResearchArtifactAttachmentRuntime | None:
    try:
        return _runtime_for_store(store)
    except ValueError:
        return None


def handle_research_artifact_attachment_post(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    if not payload.get("attached_at"):
        payload["attached_at"] = _utc_now_iso()
    runtime = _runtime_for_store(store)
    result = runtime.attach(payload)
    return {
        "disposition": result.disposition,
        "attachment_id": result.attachment_id,
        "opportunity_id": result.opportunity_id,
    }


def overlay_research_artifact_evidence_on_detail(
    store: ReplayStore,
    detail: dict[str, Any],
) -> dict[str, Any]:
    opportunity_id = str(detail.get("opportunity_id") or "")
    if not opportunity_id:
        return detail
    runtime = _optional_runtime_for_store(store)
    if runtime is None:
        return detail
    overlay = research_artifact_evidence_for_opportunity_detail(
        runtime,
        opportunity_id=opportunity_id,
        base_lineage_refs=tuple(detail.get("lineage_refs") or ()),
        base_metadata=dict(detail.get("metadata") or {}),
    )
    merged = dict(detail)
    merged["lineage_refs"] = overlay["lineage_refs"]
    merged["metadata"] = overlay["metadata"]
    merged["research_artifact_evidence"] = overlay["research_artifact_evidence"]
    return merged


__all__ = [
    "handle_research_artifact_attachment_post",
    "overlay_research_artifact_evidence_on_detail",
]
