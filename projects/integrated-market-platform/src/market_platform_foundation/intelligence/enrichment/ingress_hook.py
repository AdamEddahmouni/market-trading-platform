"""Observe ingress enrichment triggers without rewriting ObservationIngressRouter."""

from __future__ import annotations

from typing import Any

from ..contracts.agent_ingest import AgentBotRole
from ..contracts.event import EventV1
from ..observation_ingress.types import IngressEnrichmentTriggerV1
from .contracts import EnrichmentUrgency
from .enqueue import enqueue_opportunity_enrichment
from .outbox import EnrichmentOutbox, derive_enrichment_request_id


def append_enrichment_request_from_ingress_trigger(
    outbox: EnrichmentOutbox,
    *,
    trigger: IngressEnrichmentTriggerV1,
    event: EventV1,
    opportunity_id: str,
    detected_at_ns: int,
    useful_until_ns: int,
    hard_expiry_ns: int,
    requested_bot_role: AgentBotRole = AgentBotRole.SENTINEL,
) -> str:
    """Append-only hook when ingress schedules enrichment for a known opportunity."""

    from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
    from .contracts import EnrichmentRequestV1

    request_id = derive_enrichment_request_id(
        opportunity_id=opportunity_id,
        requested_bot_role=requested_bot_role.value,
        event_id=event.event_id,
    )
    symbol = None
    if event.scope.instrument_ids:
        symbol = str(event.scope.instrument_ids[0])
    request = EnrichmentRequestV1(
        request_id=request_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id=opportunity_id,
        detected_at_ns=detected_at_ns,
        useful_until_ns=useful_until_ns,
        hard_expiry_ns=hard_expiry_ns,
        requested_bot_role=requested_bot_role,
        urgency=EnrichmentUrgency.ROUTINE,
        event_id=event.event_id,
        entity_symbol=symbol,
        metadata={
            "ingress_trigger_id": trigger.trigger_id,
            "ingress_consumer_id": trigger.consumer_id,
        },
    )
    outbox.append(request)
    return request_id


def opportunity_id_from_event_metadata(event: EventV1) -> str | None:
    metadata: dict[str, Any] = event.metadata if isinstance(event.metadata, dict) else {}
    value = metadata.get("opportunity_id")
    return str(value) if value else None


__all__ = [
    "append_enrichment_request_from_ingress_trigger",
    "opportunity_id_from_event_metadata",
]
