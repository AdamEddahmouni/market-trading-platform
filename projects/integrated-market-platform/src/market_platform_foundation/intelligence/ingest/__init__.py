"""Agent intelligence ingest runtime (Lane G — analysis-only enrichment)."""

from .runtime import (
    AgentEnrichmentIngestResult,
    AgentEnrichmentIngestRuntime,
    enrichments_for_opportunity_detail,
    is_agent_enrichment_expired,
)

__all__ = [
    "AgentEnrichmentIngestResult",
    "AgentEnrichmentIngestRuntime",
    "enrichments_for_opportunity_detail",
    "is_agent_enrichment_expired",
]
