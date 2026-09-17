"""US equity regular-hours filtering and session calendar helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from ...shadow.session import session_bounds_ns

US_EQUITY_RTH_SESSION_POLICY = "US_EQUITY_RTH"
US_EQUITY_BAR_TZ = ZoneInfo("America/New_York")
RTH_MINUTES_FULL_SESSION = 390


def iter_us_equity_session_dates(
    start_date: str,
    end_date: str,
    *,
    holidays: frozenset[str] = frozenset(),
    early_closes: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Inclusive calendar range of weekdays excluding declared holidays/early-close days."""

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("INTERVAL_END_BEFORE_START")
    found: list[str] = []
    day = start
    while day <= end:
        iso = day.isoformat()
        if day.weekday() < 5 and iso not in holidays and iso not in early_closes:
            found.append(iso)
        day += timedelta(days=1)
    return tuple(found)


def parse_moomoo_time_key_local(time_key: str) -> datetime | None:
    text = str(time_key or "").strip().replace("T", " ")
    if not text:
        return None
    try:
        if len(text) >= 19:
            parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        else:
            parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=US_EQUITY_BAR_TZ)
    return parsed


def bar_start_is_rth(time_key: str) -> bool:
    parsed = parse_moomoo_time_key_local(time_key)
    if parsed is None:
        return False
    day = parsed.strftime("%Y-%m-%d")
    open_ns, close_ns = session_bounds_ns(day)
    bar_start_ns = int(parsed.timestamp() * 1_000_000_000)
    return open_ns <= bar_start_ns < close_ns


def expected_rth_minute_keys(session_date: str) -> tuple[str, ...]:
    """Expected 1m bar start time_keys for a full US RTH session (no early close)."""

    open_ns, close_ns = session_bounds_ns(session_date)
    step_ns = 60_000_000_000
    keys: list[str] = []
    t = open_ns
    while t < close_ns:
        dt = datetime.fromtimestamp(t / 1_000_000_000, tz=US_EQUITY_BAR_TZ)
        keys.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
        t += step_ns
    return tuple(keys)


def filter_raw_rows_rth(raw_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep RTH rows only; return (kept, excluded_outside_session_count)."""

    kept: list[dict[str, Any]] = []
    excluded = 0
    for row in raw_rows:
        if not isinstance(row, Mapping):
            excluded += 1
            continue
        copy = dict(row)
        if bar_start_is_rth(str(copy.get("time_key") or "")):
            kept.append(copy)
        else:
            excluded += 1
    return kept, excluded


def ohlc_row_valid(row: Mapping[str, Any]) -> bool:
    try:
        o = float(row.get("open"))
        h = float(row.get("high"))
        l = float(row.get("low"))
        c = float(row.get("close"))
    except (TypeError, ValueError):
        return False
    if o <= 0 or h <= 0 or l <= 0 or c <= 0:
        return False
    if l > min(o, c) or h < max(o, c):
        return False
    if h < l:
        return False
    return True


__all__ = [
    "RTH_MINUTES_FULL_SESSION",
    "US_EQUITY_RTH_SESSION_POLICY",
    "bar_start_is_rth",
    "expected_rth_minute_keys",
    "filter_raw_rows_rth",
    "iter_us_equity_session_dates",
    "ohlc_row_valid",
    "parse_moomoo_time_key_local",
]
