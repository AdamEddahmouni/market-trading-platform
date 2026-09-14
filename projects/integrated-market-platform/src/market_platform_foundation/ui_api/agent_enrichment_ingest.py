"""HTTP adapter for Grok/agent enrichment ingest (detail attach only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..intelligence.ingest.runtime import (
    AgentEnrichmentIngestRuntime,
    enrichments_for_opportunity_detail,
)
from ..intelligence.persistence.memory import InMemoryIntelligenceRepository
from .store import ReplayStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repository_for_store(store: ReplayStore) -> InMemoryIntelligenceRepository | None:
    repository = getattr(store, "strategy_repository", None)
    if isinstance(repository, InMemoryIntelligenceRepository):
        return repository
    cached = getattr(store, "agent_enrichment_repository", None)
    if isinstance(cached, InMemoryIntelligenceRepository):
        return cached
    created = InMemoryIntelligenceRepository()
    store.agent_enrichment_repository = created
    return created


def _runtime_for_store(store: ReplayStore) -> AgentEnrichmentIngestRuntime:
    repository = _repository_for_store(store)
    if repository is None:
        raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNAVAILABLE")
    return AgentEnrichmentIngestRuntime(repository)


def handle_agent_enrichment_ingest_post(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    runtime = _runtime_for_store(store)
    result = runtime.ingest(body, as_of_iso=_utc_now_iso())
    return {
        "disposition": result.disposition.value,
        "record_id": result.record_id,
        "opportunity_id": result.opportunity_id,
        "schema_id": result.schema_id,
    }


def handle_agent_enrichment_ingest_put(
    store: ReplayStore,
    record_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    if str(body.get("record_id") or record_id) != str(record_id):
        raise ValueError("AGENT_ENRICHMENT_RECORD_ID_MISMATCH")
    body = dict(body)
    body["record_id"] = str(record_id)
    body["operation"] = body.get("operation") or "UPDATE_OWN_EVIDENCE_RECORD"
    runtime = _runtime_for_store(store)
    result = runtime.ingest(body, as_of_iso=_utc_now_iso())
    return {
        "disposition": result.disposition.value,
        "record_id": result.record_id,
        "opportunity_id": result.opportunity_id,
        "schema_id": result.schema_id,
    }


def overlay_agent_enrichment_on_detail(
    store: ReplayStore,
    detail: dict[str, Any],
) -> dict[str, Any]:
    opportunity_id = str(detail.get("opportunity_id") or detail.get("summary_id") or "")
    if not opportunity_id:
        return detail
    runtime = _runtime_for_store(store)
    overlay = enrichments_for_opportunity_detail(
        runtime,
        opportunity_id=opportunity_id,
        as_of_iso=_utc_now_iso(),
        base_lineage_refs=tuple(detail.get("lineage_refs") or ()),
        base_metadata=dict(detail.get("metadata") or {}),
    )
    merged = dict(detail)
    merged["lineage_refs"] = overlay["lineage_refs"]
    merged["metadata"] = overlay["metadata"]
    merged["agent_enrichment_records"] = overlay["agent_enrichment_records"]
    return merged
