"""Validated ingest + durable outbox ACK without blocking opportunity surfaces."""

from __future__ import annotations

from typing import Any, Callable

from ..contracts.opportunity import OpportunityV1
from ..ingest.runtime import AgentEnrichmentIngestResult, AgentEnrichmentIngestRuntime
from .callback_ack import maybe_acknowledge_enrichment_outbox
from .outbox import EnrichmentOutbox


class AgentEnrichmentIngestCoordinator:
    """Compose Lane G ingest runtime with enrichment-plane outbox ACK."""

    def __init__(
        self,
        runtime: AgentEnrichmentIngestRuntime,
        *,
        outbox: EnrichmentOutbox | None = None,
        get_opportunity: Callable[[str], OpportunityV1 | None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._outbox = outbox
        self._get_opportunity = get_opportunity

    def ingest(
        self,
        payload: dict[str, Any],
        *,
        as_of_iso: str,
    ) -> AgentEnrichmentIngestResult:
        result = self._runtime.ingest(payload, as_of_iso=as_of_iso)
        maybe_acknowledge_enrichment_outbox(
            self._outbox,
            ingest_result=result,
            payload=payload,
        )
        return result


__all__ = ["AgentEnrichmentIngestCoordinator"]
