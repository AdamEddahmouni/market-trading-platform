"""Pure regular-session calendar, primary grids, and decision buckets.

All wall-clock semantics are America/New_York regular hours 09:30-16:00.
Holiday and early-close dates are supplied frozen at manifest open; this
module owns no hidden calendar state (spec section 7.1).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_OPEN_MINUTES = 9 * 60 + 30
_CLOSE_MINUTES = 16 * 60
_NS = 1_000_000_000


def decision_bucket(event_time_ns: int, bucket_seconds: int = 60) -> int:
    return int(event_time_ns) // (int(bucket_seconds) * _NS)


def _et_ns(day: date, minutes_after_midnight: int) -> int:
    stamp = datetime.combine(day, datetime.min.time(), tzinfo=ET).replace(
        hour=minutes_after_midnight // 60, minute=minutes_after_midnight % 60
    )
    return int(stamp.timestamp() * _NS)


def session_bounds_ns(date_iso: str) -> tuple[int, int]:
    day = date.fromisoformat(date_iso)
    return _et_ns(day, _OPEN_MINUTES), _et_ns(day, _CLOSE_MINUTES)


def build_session_list(
    first_date_iso: str,
    sessions_needed: int,
    holidays: frozenset[str],
    early_closes: frozenset[str],
) -> list[str]:
    day = date.fromisoformat(first_date_iso)
    found: list[str] = []
    while len(found) < sessions_needed:
        iso = day.isoformat()
        if day.weekday() < 5 and iso not in holidays and iso not in early_closes:
            found.append(iso)
        day += timedelta(days=1)
    return found


def outside_session_window(target_ns: int, tolerance_ns: int, session_end_ns: int) -> bool:
    return (target_ns + tolerance_ns) > session_end_ns


def grid_targets_ns(date_iso: str, horizon_seconds: int, tolerance_seconds: int) -> list[int]:
    open_ns, close_ns = session_bounds_ns(date_iso)
    step = 30 * 60 * _NS
    limit = horizon_seconds * _NS + tolerance_seconds * _NS
    targets: list[int] = []
    t = open_ns
    while t + limit <= close_ns:
        targets.append(t)
        t += step
    return targets
