"""Canonical envelope validation per Revision 1 section 7.1."""

from __future__ import annotations

from typing import Any

TIMESTAMP_REQUIREMENT_STATES = frozenset({"REQUIRED", "DERIVED", "UNAVAILABLE", "FORBIDDEN"})
TIMESTAMP_FIELDS = (
    "event_time",
    "source_publish_time",
    "live_received_time",
    "historical_ingested_time",
    "available_time",
)

ENVELOPE_FIELDS = (
    "normalized_event_id",
    "source_record_id",
    "source_revision_id",
    "normalization_version",
    "schema_version",
    "event_type",
    "instrument_id",
    "venue_id",
    "publisher_id",
    "channel_id",
    "source_instance_id",
    "event_time",
    "source_publish_time",
    "live_received_time",
    "historical_ingested_time",
    "available_time",
    "source_sequence",
    "ingest_run_id",
    "raw_reference",
    "quality_observation_refs",
    "operation",
    "supersedes_event_id",
)


def validate_timestamp_state(
    field: str,
    state: str,
    value: object,
    *,
    acquisition_mode: str,
) -> list[str]:
    reasons: list[str] = []
    if state not in TIMESTAMP_REQUIREMENT_STATES:
        reasons.append(f"ENVELOPE_INVALID_TIMESTAMP_STATE_{field.upper()}")
        return reasons
    if state == "FORBIDDEN":
        if value is not None:
            reasons.append(f"TC002_FORBIDDEN_FIELD_POPULATED_{field.upper()}")
        return reasons
    if state == "UNAVAILABLE":
        if value is not None:
            reasons.append(f"ENVELOPE_UNAVAILABLE_FIELD_POPULATED_{field.upper()}")
        return reasons
    if state in {"REQUIRED", "DERIVED"} and value is None:
        reasons.append(f"ENVELOPE_MISSING_{field.upper()}")
    if acquisition_mode == "historical" and field == "live_received_time" and value is not None:
        reasons.append("TC002_HISTORICAL_FABRICATED_LIVE_RECEIVED_TIME")
    if acquisition_mode == "live" and field == "historical_ingested_time" and value is not None:
        reasons.append("TC002_LIVE_FABRICATED_HISTORICAL_INGESTED_TIME")
    return reasons


def validate_envelope(
    event: dict[str, Any],
    *,
    timestamp_states: dict[str, str],
    acquisition_mode: str,
) -> list[str]:
    reasons: list[str] = []
    for field in ENVELOPE_FIELDS:
        if field not in event and field not in timestamp_states:
            if field in TIMESTAMP_FIELDS:
                continue
            reasons.append(f"ENVELOPE_MISSING_FIELD_{field.upper()}")
    for field, state in timestamp_states.items():
        reasons.extend(
            validate_timestamp_state(
                field,
                state,
                event.get(field),
                acquisition_mode=acquisition_mode,
            )
        )
    if event.get("available_time") is None:
        reasons.append("ENVELOPE_MISSING_AVAILABLE_TIME")
    return sorted(set(reasons))


def round_trip_envelope(event: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical copy preserving declared fields."""
    return {key: event[key] for key in sorted(event) if event[key] is not None or key in TIMESTAMP_FIELDS}
