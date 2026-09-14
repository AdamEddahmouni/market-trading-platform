"""Agent intelligence ingest runtime (Lane G — analysis-only enrichment)."""

from .boundary import (
    AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES,
    enforce_agent_enrichment_body_limit,
    resolve_agent_enrichment_persistence,
)
from .runtime import (
    AgentEnrichmentIngestResult,
    AgentEnrichmentIngestRuntime,
    enrichments_for_opportunity_detail,
    is_agent_enrichment_expired,
)

__all__ = [
    "AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES",
    "AgentEnrichmentIngestResult",
    "AgentEnrichmentIngestRuntime",
    "enforce_agent_enrichment_body_limit",
    "enrichments_for_opportunity_detail",
    "is_agent_enrichment_expired",
    "resolve_agent_enrichment_persistence",
]
