"""US equity extended-hours session labels for discovery surfaces."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_PREMARKET_OPEN = 4 * 60
_REGULAR_OPEN = 9 * 60 + 30
_REGULAR_CLOSE = 16 * 60
_AFTER_HOURS_CLOSE = 20 * 60


def us_equity_session_label(at: datetime | None = None) -> str:
    """Return PREMARKET, REGULAR, AFTER_HOURS, or CLOSED in America/New_York."""

    now = at or datetime.now(ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    else:
        now = now.astimezone(ET)
    if now.weekday() >= 5:
        return "CLOSED"
    minutes = now.hour * 60 + now.minute
    if minutes < _PREMARKET_OPEN or minutes >= _AFTER_HOURS_CLOSE:
        return "CLOSED"
    if minutes < _REGULAR_OPEN:
        return "PREMARKET"
    if minutes < _REGULAR_CLOSE:
        return "REGULAR"
    return "AFTER_HOURS"
