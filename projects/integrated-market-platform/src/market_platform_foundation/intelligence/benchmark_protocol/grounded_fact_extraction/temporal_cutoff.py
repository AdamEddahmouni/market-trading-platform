"""Temporal cutoff enforcement for admitted historical bar fixtures."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_ISO_Z = re.compile(
    r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})Z$",
)


def _parse_cutoff_instant(cutoff: dict[str, Any] | None) -> datetime | None:
    if not cutoff:
        return None
    instant = str(cutoff.get("cutoff_instant") or "")
    match = _ISO_Z.match(instant)
    if not match:
        return None
    y, mo, d = int(match.group(1)[:4]), int(instant[5:7]), int(instant[8:10])
    h, mi, s = int(match.group(2)), int(match.group(3)), int(match.group(4))
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


def _parse_bar_time_key(time_key: str) -> datetime | None:
    text = time_key.strip()
    if text == "not-a-timestamp":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None


def historical_payload_violates_cutoff(payload: Any, cutoff: dict[str, Any] | None) -> bool:
    """True when any parseable bar time_key is strictly after cutoff_instant."""
    limit = _parse_cutoff_instant(cutoff)
    if limit is None or not isinstance(payload, dict):
        return False
    for rows in payload.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            parsed = _parse_bar_time_key(str(row.get("time_key") or ""))
            if parsed is not None and parsed > limit:
                return True
    return False


__all__ = ["historical_payload_violates_cutoff"]
