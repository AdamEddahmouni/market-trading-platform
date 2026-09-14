"""Ingest boundary guards shared by HTTP adapters and tests."""

from __future__ import annotations

from typing import Any

from .runtime import AgentEnrichmentPersistence

AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES = 65_536


def enforce_agent_enrichment_body_limit(content_length: int) -> None:
    if content_length < 0:
        raise ValueError("AGENT_ENRICHMENT_CONTENT_LENGTH_INVALID")
    if content_length > AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES:
        raise ValueError("AGENT_ENRICHMENT_BODY_TOO_LARGE")


def resolve_agent_enrichment_persistence(strategy_repository: Any) -> AgentEnrichmentPersistence:
    if strategy_repository is None:
        raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNAVAILABLE")
    if not isinstance(strategy_repository, AgentEnrichmentPersistence):
        raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNSUPPORTED")
    return strategy_repository
