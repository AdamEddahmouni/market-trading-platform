"""Observational NEWS_ARTICLE → OpportunityV1. Not Live authority; not BUILD 09 NEWS_EVENT.

``OpportunityEngine.assess`` remains Path A (ForecastV1 + champion). News mint
does not invent a forecast or DetectionFrame; catalyst qualification is the
deterministic detector already on the production ingress consumer.
"""

from __future__ import annotations

from typing import Any

from ..intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
    IntelligenceScope,
    QualitySummary,
)
from ..intelligence.contracts.event import EventV1
from ..intelligence.contracts.opportunity import OpportunityV1
from .catalysts import DEFAULT_CATALYST_REGISTRY, CatalystRegistry

OBSERVATIONAL_CONTEXT_ID = "observational_news"
OPPORTUNITY_ID_PREFIX = "newsopp-"


def _enabled_catalyst_ids() -> frozenset[str]:
    return frozenset(entry.catalyst_id for entry in DEFAULT_CATALYST_REGISTRY if entry.enabled)


def instrument_id_from_news_event(event: EventV1) -> str | None:
    if event.instrument_id:
        return str(event.instrument_id)
    payload = event.payload if isinstance(event.payload, dict) else {}
    linkages = payload.get("instrument_linkages") or []
    if isinstance(linkages, list) and linkages and isinstance(linkages[0], dict):
        text = str(linkages[0].get("instrument_id") or "").strip()
        return text or None
    return None


def observational_news_catalyst_ids(event: EventV1) -> tuple[str, ...]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    text = " ".join(
        [str(payload.get("headline") or ""), str(payload.get("summary") or "")]
    ).strip()
    return CatalystRegistry().match(text, enabled_catalyst_ids=_enabled_catalyst_ids())


def qualifies_observational_news_opportunity(event: EventV1) -> bool:
    return bool(instrument_id_from_news_event(event) and observational_news_catalyst_ids(event))


def observational_news_opportunity_id(event_id: str) -> str:
    return f"{OPPORTUNITY_ID_PREFIX}{event_id}"


def build_observational_news_opportunity(event: EventV1) -> OpportunityV1 | None:
    instrument_id = instrument_id_from_news_event(event)
    catalysts = observational_news_catalyst_ids(event)
    if not instrument_id or not catalysts:
        return None
    created_at_ns = event.received_time_ns if event.received_time_ns is not None else event.available_time_ns
    payload = event.payload if isinstance(event.payload, dict) else {}
    return OpportunityV1(
        opportunity_id=observational_news_opportunity_id(event.event_id),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id=OBSERVATIONAL_CONTEXT_ID),
        created_at_ns=int(created_at_ns),
        quality=QualitySummary(state=event.quality.state, flags=tuple(event.quality.flags)),
        opportunity_type="NEWS_OBSERVATIONAL",
        side=None,
        reason_summary=str(payload.get("headline") or event.event_id),
        lineage_refs=(ContractReference(kind=ContractKind.EVENT.value, id=event.event_id),),
        metadata={
            "observational": True,
            "live_authority": False,
            "news_event_build09": "INACTIVE",
            "provider_id": event.source.provider_id,
            "source_event_id": event.event_id,
            "event_time_ns": event.event_time_ns,
            "available_time_ns": event.available_time_ns,
            "received_time_ns": event.received_time_ns,
            "provider_time_ns": event.provider_time_ns,
            "matched_catalyst_ids": list(catalysts),
        },
    )


def persist_observational_news_opportunity(
    event: EventV1,
    repository: Any | None,
) -> OpportunityV1 | None:
    opportunity = build_observational_news_opportunity(event)
    if opportunity is None or repository is None:
        return None
    putter = getattr(repository, "put_opportunity", None)
    if not callable(putter):
        return None
    putter(opportunity)
    from ..observability.latency_instrumentation_v1.context import current_latency_collector
    from ..observability.latency_instrumentation_v1.types import LatencyStageId

    collector = current_latency_collector()
    if collector is not None:
        collector.mark_stage(event.event_id, LatencyStageId.OPPORTUNITY_PERSISTED)
        collector.attach_opportunity_id(event.event_id, opportunity.opportunity_id)
    return opportunity


__all__ = [
    "OBSERVATIONAL_CONTEXT_ID",
    "OPPORTUNITY_ID_PREFIX",
    "build_observational_news_opportunity",
    "instrument_id_from_news_event",
    "observational_news_catalyst_ids",
    "observational_news_opportunity_id",
    "persist_observational_news_opportunity",
    "qualifies_observational_news_opportunity",
]
