"""Build EventV1 from normalized components (BUILD 03)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, QualityState, QualitySummary, SourceReference
from ..contracts.event import EventV1
from .models import PROVENANCE_METADATA_KEY, ProviderProvenance


def build_event_v1(
    *,
    event_id: str,
    event_type: str,
    event_time_ns: int,
    available_time_ns: int,
    payload: dict[str, Any],
    source: SourceReference,
    provenance: ProviderProvenance,
    instrument_id: str | None = None,
    provider_time_ns: int | None = None,
    received_time_ns: int | None = None,
    quality_state: QualityState = QualityState.UNKNOWN,
    quality_flags: tuple[str, ...] = (),
) -> EventV1:
    metadata = {PROVENANCE_METADATA_KEY: provenance.to_dict()}
    return EventV1(
        event_id=event_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        event_type=event_type,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        quality=QualitySummary(state=quality_state, flags=quality_flags),
        source=source,
        instrument_id=instrument_id,
        provider_time_ns=provider_time_ns,
        received_time_ns=received_time_ns,
        metadata=metadata,
    )


def provenance_from_event(event: EventV1) -> ProviderProvenance | None:
    raw = (event.metadata or {}).get(PROVENANCE_METADATA_KEY)
    if not isinstance(raw, dict):
        return None
    return ProviderProvenance.from_dict(raw)


__all__ = ["build_event_v1", "provenance_from_event"]
