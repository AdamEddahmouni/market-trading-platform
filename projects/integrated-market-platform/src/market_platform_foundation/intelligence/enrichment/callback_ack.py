"""Outbox ACK after validated agent enrichment ingest (enrichment plane only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..contracts.agent_ingest import AgentBotRole
from ..ingest.runtime import AgentEnrichmentIngestResult, IngestDisposition
from .delivery import EnrichmentDeliveryState
from .outbox import EnrichmentOutbox, derive_enrichment_request_id


class EnrichmentOutboxAckDisposition(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ALREADY_ACKNOWLEDGED = "ALREADY_ACKNOWLEDGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REQUEST_UNKNOWN = "REQUEST_UNKNOWN"
    REQUEST_NOT_ACK_ELIGIBLE = "REQUEST_NOT_ACK_ELIGIBLE"


_ACK_SUCCESS_DISPOSITIONS = frozenset(
    {
        IngestDisposition.INSERTED,
        IngestDisposition.ALREADY_PRESENT,
        IngestDisposition.UPDATED,
    }
)

_ACK_ELIGIBLE_DELIVERY_STATES = frozenset(
    {
        EnrichmentDeliveryState.PENDING,
        EnrichmentDeliveryState.CLAIMED,
        EnrichmentDeliveryState.DISPATCHED,
        EnrichmentDeliveryState.ACKNOWLEDGED,
    }
)


@dataclass(frozen=True, slots=True)
class EnrichmentOutboxAckResult:
    disposition: EnrichmentOutboxAckDisposition
    request_id: str | None = None


def resolve_enrichment_request_id_from_ingest_payload(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        explicit = metadata.get("enrichment_request_id")
        if explicit:
            return str(explicit)
        event_id = metadata.get("event_id") or metadata.get("ingress_event_id")
    else:
        event_id = None
    return derive_enrichment_request_id(
        opportunity_id=str(payload["opportunity_id"]),
        requested_bot_role=str(payload.get("bot_role", AgentBotRole.SENTINEL.value)),
        event_id=str(event_id) if event_id else None,
    )


def maybe_acknowledge_enrichment_outbox(
    outbox: EnrichmentOutbox | None,
    *,
    ingest_result: AgentEnrichmentIngestResult,
    payload: dict[str, Any],
    at_ns: int | None = None,
) -> EnrichmentOutboxAckResult:
    """ACK matching durable request only after validated ingest success."""

    if outbox is None:
        return EnrichmentOutboxAckResult(disposition=EnrichmentOutboxAckDisposition.NOT_APPLICABLE)
    if ingest_result.disposition not in _ACK_SUCCESS_DISPOSITIONS:
        return EnrichmentOutboxAckResult(disposition=EnrichmentOutboxAckDisposition.NOT_APPLICABLE)
    request_id = resolve_enrichment_request_id_from_ingest_payload(payload)
    delivery = outbox.get_delivery(request_id)
    if delivery is None:
        return EnrichmentOutboxAckResult(
            disposition=EnrichmentOutboxAckDisposition.REQUEST_UNKNOWN,
            request_id=request_id,
        )
    if delivery.delivery_state == EnrichmentDeliveryState.ACKNOWLEDGED:
        return EnrichmentOutboxAckResult(
            disposition=EnrichmentOutboxAckDisposition.ALREADY_ACKNOWLEDGED,
            request_id=request_id,
        )
    if delivery.delivery_state not in _ACK_ELIGIBLE_DELIVERY_STATES:
        return EnrichmentOutboxAckResult(
            disposition=EnrichmentOutboxAckDisposition.REQUEST_NOT_ACK_ELIGIBLE,
            request_id=request_id,
        )
    outbox.mark_acknowledged(request_id, at_ns=at_ns)
    return EnrichmentOutboxAckResult(
        disposition=EnrichmentOutboxAckDisposition.ACKNOWLEDGED,
        request_id=request_id,
    )


__all__ = [
    "EnrichmentOutboxAckDisposition",
    "EnrichmentOutboxAckResult",
    "maybe_acknowledge_enrichment_outbox",
    "resolve_enrichment_request_id_from_ingest_payload",
]
