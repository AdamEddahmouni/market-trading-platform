"""Event and jump primitives for SHARED P2 — fail-closed without catalyst data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class EventJumpPrimitive:
    """Detected jump or catalyst window with explicit provenance."""

    event_time: str
    jump_detected: bool
    standardized_return: float | None
    catalyst_type: str | None
    source_ref: str
    available: bool


def _parse_event_time(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def detect_return_jump(
    returns: Sequence[float],
    *,
    threshold: float = 2.5,
) -> list[float]:
    """Return standardized returns exceeding threshold (jump candidates)."""
    if len(returns) < 3:
        return []
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return []
    std = variance ** 0.5
    jumps: list[float] = []
    for value in returns:
        z = (value - mean) / std
        if abs(z) >= threshold:
            jumps.append(round(z, 6))
    return jumps


def count_recent_jumps(returns: Sequence[float], *, window: int = 10) -> int:
    recent = list(returns[-window:])
    return len(detect_return_jump(recent))


def event_window_active(
    as_of_time: str,
    catalyst_event_times: Sequence[str],
    *,
    window_hours: int = 48,
) -> bool:
    """Tag whether as_of_time falls within catalyst event window."""
    anchor = _parse_event_time(as_of_time)
    if anchor is None or not catalyst_event_times:
        return False
    for raw in catalyst_event_times:
        event = _parse_event_time(raw)
        if event is None:
            continue
        delta = abs((anchor - event).total_seconds())
        if delta <= window_hours * 3600:
            return True
    return False


def build_event_jump_primitive(
    *,
    as_of_time: str,
    returns: Sequence[float],
    catalyst_row: dict[str, Any] | None = None,
    source_ref: str = "",
) -> EventJumpPrimitive:
    jumps = detect_return_jump(returns)
    catalyst_type = None
    if catalyst_row:
        catalyst_type = str(catalyst_row.get("catalyst_type", "")) or None
    return EventJumpPrimitive(
        event_time=as_of_time,
        jump_detected=bool(jumps),
        standardized_return=jumps[-1] if jumps else None,
        catalyst_type=catalyst_type,
        source_ref=source_ref,
        available=bool(returns),
    )


__all__ = [
    "EventJumpPrimitive",
    "build_event_jump_primitive",
    "count_recent_jumps",
    "detect_return_jump",
    "event_window_active",
]
