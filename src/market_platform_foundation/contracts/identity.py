"""Normalized identity and deterministic ordering per Revision 1 section 7.2."""

from __future__ import annotations

import uuid
from typing import Any

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
MISSING_SEQUENCE = -1
MISSING_SCOPE = ""


def normalized_event_id(
    *,
    provider_id: str,
    venue_id: str,
    publisher_id: str,
    channel_id: str,
    source_instance_id: str,
    source_record_id: str,
    source_revision_id: str,
    event_family: str,
    subrecord_discriminator: str = "",
) -> str:
    name = "|".join(
        (
            provider_id,
            venue_id,
            publisher_id,
            channel_id,
            source_instance_id,
            source_record_id,
            source_revision_id,
            event_family,
            subrecord_discriminator,
        )
    )
    return str(uuid.uuid5(NAMESPACE, name))


def ordering_key(
    event: dict[str, Any],
    *,
    event_time_state_rank: int,
    event_type_precedence: int,
) -> tuple[Any, ...]:
    available_time = int(event["available_time"])
    event_time = int(event.get("event_time", 0))
    sequence_scope = str(event.get("sequence_scope", MISSING_SCOPE))
    raw_sequence = event.get("source_sequence", MISSING_SEQUENCE)
    source_sequence = MISSING_SEQUENCE if raw_sequence is None else int(raw_sequence)
    return (
        available_time,
        event_time_state_rank,
        event_time,
        sequence_scope,
        source_sequence,
        event_type_precedence,
        str(event["normalized_event_id"]),
    )


def sort_events(
    events: list[dict[str, Any]],
    *,
    event_time_state_rank: int = 0,
    event_type_precedence: int = 0,
) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda event: ordering_key(
            event,
            event_time_state_rank=event_time_state_rank,
            event_type_precedence=event_type_precedence,
        ),
    )
