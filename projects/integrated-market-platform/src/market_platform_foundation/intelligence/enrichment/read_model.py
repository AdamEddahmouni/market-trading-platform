"""Additive read-model fields for async enrichment (detail-only)."""

from __future__ import annotations

from typing import Any

from ..contracts.ingest_ui_timing import evaluate_ui_intelligence_render_gate
from ..ingest.runtime import AgentEnrichmentIngestRuntime
from .outbox import EnrichmentOutbox


def async_enrichment_fields_for_detail(
    *,
    opportunity_id: str,
    deterministic_detection: dict[str, Any] | None,
    outbox: EnrichmentOutbox | None,
    runtime: AgentEnrichmentIngestRuntime | None,
    as_of_iso: str,
) -> dict[str, Any]:
    requests = outbox.list_for_opportunity(opportunity_id) if outbox is not None else ()
    active_count = 0
    if runtime is not None:
        active_count = len(runtime.list_active_for_opportunity(opportunity_id, as_of_iso=as_of_iso))
    gate = evaluate_ui_intelligence_render_gate(
        deterministic_detection=deterministic_detection,
        wait_for_agent_enrichment=False,
        agent_enrichment_count=active_count,
        agent_enrichment_expected=bool(requests),
    )
    return {
        "async_enrichment": {
            "phase": gate.phase.value,
            "reason_code": gate.reason_code,
            "pending_request_ids": [row.request_id for row in requests],
            "pending_request_count": len(requests),
            "active_enrichment_count": active_count,
        }
    }


def overlay_async_enrichment_on_detail(
    detail: dict[str, Any],
    *,
    outbox: EnrichmentOutbox | None,
    runtime: AgentEnrichmentIngestRuntime | None,
    as_of_iso: str,
) -> dict[str, Any]:
    opportunity_id = str(detail.get("opportunity_id") or detail.get("summary_id") or "")
    if not opportunity_id:
        return detail
    detection = {
        "opportunity_id": opportunity_id,
        "summary_id": detail.get("summary_id"),
    }
    fields = async_enrichment_fields_for_detail(
        opportunity_id=opportunity_id,
        deterministic_detection=detection,
        outbox=outbox,
        runtime=runtime,
        as_of_iso=as_of_iso,
    )
    merged = dict(detail)
    merged.update(fields)
    return merged


__all__ = [
    "async_enrichment_fields_for_detail",
    "overlay_async_enrichment_on_detail",
]
