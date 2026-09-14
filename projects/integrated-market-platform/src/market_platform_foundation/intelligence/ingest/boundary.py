"""Ingest boundary guards shared by HTTP adapters and tests."""

from __future__ import annotations

from typing import Any

AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES = 65_536

_AGENT_ENRICHMENT_PERSISTENCE_METHODS = (
    "put_agent_enrichment_evidence",
    "get_agent_enrichment_evidence",
    "list_agent_enrichment_by_opportunity",
)


def enforce_agent_enrichment_body_limit(content_length: int) -> None:
    if content_length < 0:
        raise ValueError("AGENT_ENRICHMENT_CONTENT_LENGTH_INVALID")
    if content_length > AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES:
        raise ValueError("AGENT_ENRICHMENT_BODY_TOO_LARGE")


def resolve_agent_enrichment_persistence(strategy_repository: Any) -> Any:
    if strategy_repository is None:
        raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNAVAILABLE")
    for method_name in _AGENT_ENRICHMENT_PERSISTENCE_METHODS:
        if not callable(getattr(strategy_repository, method_name, None)):
            raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNSUPPORTED")
    return strategy_repository
