"""Parse Moomoo provider timestamps into epoch nanoseconds.

Observed quote/ticker times are naive local-session strings such as
``2026-08-21 16:13:22.551``. IMP treats them as America/New_York wall time.
Lag computed from these values is event-to-local-receipt lag, not exchange latency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")


def parse_provider_datetime_ns(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            localized = parsed.replace(tzinfo=_ET)
            return int(localized.timestamp() * 1_000_000_000)
        except ValueError:
            continue
    return None


def event_time_ns_from_payload(payload: dict[str, Any], *, received_ns: int) -> int:
    """Best-effort provider event time; never use received time just to look fast.

    Quote snapshots often carry session ``data_time`` of ``16:00:00`` (regular-session
    close). That is not a tick timestamp and must not be used for lag.
    """

    for key in ("time", "update_time", "svr_recv_time_bid", "svr_recv_time_ask"):
        parsed = parse_provider_datetime_ns(payload.get(key))
        if parsed is not None:
            return parsed
    return received_ns


def is_provider_cached_push(payload: dict[str, Any]) -> bool:
    return str(payload.get("push_data_type") or "").upper() == "CACHE"


def classify_first_push(*, is_first: bool, event_ns: int, received_ns: int) -> str:
    if not is_first:
        return "FRESH"
    if event_ns == received_ns:
        return "UNKNOWN"
    return "SNAPSHOT"
