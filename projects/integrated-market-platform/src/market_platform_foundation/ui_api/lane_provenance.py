"""Lane-specific data provenance envelope for UI API responses (TD-002)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_ISO_Z_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{2}:\d{2}:\d{2})(?:\.(?P<frac>\d+))?Z?$"
)

SOURCE_KIND_LANE_PAYLOAD = "lane_payload"
SOURCE_KIND_CONTEXT_AS_OF = "context_as_of"
SOURCE_KIND_RETRIEVED_AT = "retrieved_at"
SOURCE_KIND_UNKNOWN = "unknown"


def _iso_to_epoch_ns(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    match = _ISO_Z_RE.match(text)
    if match:
        frac = match.group("frac") or "0"
        frac_padded = (frac + "000000000")[:9]
        iso = f"{match.group('date')}T{match.group('time')}.{frac_padded}Z"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1_000_000_000)
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000_000)
    except ValueError:
        return None


def _numeric_epoch_ns(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    # Values above 1e15 treated as epoch nanoseconds; smaller as milliseconds.
    if number > 1_000_000_000_000_000:
        return number
    if number > 1_000_000_000_000:
        return number * 1_000_000
    return number * 1_000_000_000


def _first_epoch_ns(*candidates: Any) -> int | None:
    for candidate in candidates:
        if isinstance(candidate, str):
            parsed = _iso_to_epoch_ns(candidate)
            if parsed is not None:
                return parsed
        else:
            parsed = _numeric_epoch_ns(candidate)
            if parsed is not None:
                return parsed
    return None


def extract_lane_source_time(payload: dict[str, Any]) -> tuple[int | None, str]:
    """Return (source_time_ns, source_kind) from a lane/workspace payload."""
    as_of_context = payload.get("as_of_context")
    context_as_of = None
    if isinstance(as_of_context, dict):
        context_as_of = as_of_context.get("as_of_time")

    # Direct lane payload timestamps (preferred).
    direct = _first_epoch_ns(
        payload.get("observation_time"),
        payload.get("source_time"),
        payload.get("as_of_time"),
        payload.get("as_of"),
        payload.get("as_of_ns"),
        payload.get("updated_at"),
        payload.get("snapshot_time"),
    )
    if direct is not None:
        return direct, SOURCE_KIND_LANE_PAYLOAD

    # Nested evidence rows (workspace evidence envelope).
    lanes = payload.get("lanes")
    if isinstance(lanes, list):
        lane_times: list[int] = []
        for row in lanes:
            if not isinstance(row, dict):
                continue
            row_time = _first_epoch_ns(row.get("available_time"), row.get("as_of"), row.get("observation_time"))
            if row_time is not None:
                lane_times.append(row_time)
        if lane_times:
            return min(lane_times), SOURCE_KIND_LANE_PAYLOAD

    # Health blocks with updated_at (explore catalyst etc.).
    health = payload.get("health")
    if isinstance(health, dict):
        health_time = _first_epoch_ns(health.get("updated_at"))
        if health_time is not None:
            return health_time, SOURCE_KIND_LANE_PAYLOAD

    # Context as-of is weaker than lane-native timestamps but better than unknown.
    context_time = _first_epoch_ns(context_as_of) if context_as_of else None
    if context_time is not None:
        return context_time, SOURCE_KIND_CONTEXT_AS_OF

    return None, SOURCE_KIND_UNKNOWN


def build_lane_provenance(
    payload: dict[str, Any],
    *,
    lane_id: str,
    retrieved_at_ns: int,
) -> dict[str, Any]:
    source_time, source_kind = extract_lane_source_time(payload)
    provenance: dict[str, Any] = {
        "lane_id": lane_id,
        "source_kind": source_kind,
        "retrieved_at": retrieved_at_ns,
    }
    if source_time is not None:
        provenance["source_time"] = source_time
    return provenance


def attach_lane_provenance(
    payload: dict[str, Any],
    *,
    lane_id: str,
    retrieved_at_ns: int,
) -> dict[str, Any]:
    """Attach lane_provenance without mutating unrelated fields."""
    enriched = dict(payload)
    enriched["lane_provenance"] = build_lane_provenance(
        payload,
        lane_id=lane_id,
        retrieved_at_ns=retrieved_at_ns,
    )
    return enriched
