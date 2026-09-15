"""EventV1 adapters for congressional PTR runtime vertical."""

from __future__ import annotations

from ...contracts import EventV1
from .constants import RUNTIME_EVENT_TYPE, RUNTIME_PROVIDER_ID
from .facts import CongressionalDisclosureFacts, facts_from_runtime_event


def accepts_congressional_disclosure_event(event: EventV1) -> bool:
    if str(event.event_type) != RUNTIME_EVENT_TYPE:
        return False
    if event.source.provider_id != RUNTIME_PROVIDER_ID:
        return False
    clocks = event.payload.get("clocks")
    return isinstance(clocks, dict)


def extract_congressional_disclosure_facts(event: EventV1) -> CongressionalDisclosureFacts | None:
    if not accepts_congressional_disclosure_event(event):
        return None
    return facts_from_runtime_event(event)


__all__ = [
    "accepts_congressional_disclosure_event",
    "extract_congressional_disclosure_facts",
]
