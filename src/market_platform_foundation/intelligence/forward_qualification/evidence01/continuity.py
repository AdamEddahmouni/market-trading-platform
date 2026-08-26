"""Expected-observation-window-aware continuity gap computation for EVIDENCE-01."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_NS = 1_000_000_000
_OPEN_MINUTES = 9 * 60 + 30
_CLOSE_MINUTES = 16 * 60

# Frozen US equity holidays for EVIDENCE-01 forward qualification scope.
_DEFAULT_HOLIDAYS: frozenset[str] = frozenset(
    {
        "2025-01-01",
        "2025-01-20",
        "2025-02-17",
        "2025-04-18",
        "2025-05-26",
        "2025-06-19",
        "2025-07-04",
        "2025-09-01",
        "2025-11-27",
        "2025-12-25",
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    }
)


def _et_date(epoch_ns: int) -> date:
    return datetime.fromtimestamp(epoch_ns / _NS, tz=_ET).date()


def _session_bounds_ns(day: date) -> tuple[int, int]:
    open_dt = datetime.combine(day, datetime.min.time(), tzinfo=_ET).replace(
        hour=_OPEN_MINUTES // 60, minute=_OPEN_MINUTES % 60
    )
    close_dt = datetime.combine(day, datetime.min.time(), tzinfo=_ET).replace(
        hour=_CLOSE_MINUTES // 60, minute=_CLOSE_MINUTES % 60
    )
    return int(open_dt.timestamp() * _NS), int(close_dt.timestamp() * _NS)


def is_trading_day(day: date, *, holidays: frozenset[str] = _DEFAULT_HOLIDAYS) -> bool:
    return day.weekday() < 5 and day.isoformat() not in holidays


def expected_observation_windows_between(
    start_ns: int,
    end_ns: int,
    *,
    holidays: frozenset[str] = _DEFAULT_HOLIDAYS,
) -> list[tuple[int, int]]:
    """Return expected regular-session observation windows overlapping (start_ns, end_ns)."""
    if end_ns <= start_ns:
        return []
    windows: list[tuple[int, int]] = []
    day = _et_date(start_ns)
    end_day = _et_date(end_ns)
    while day <= end_day:
        if is_trading_day(day, holidays=holidays):
            open_ns, close_ns = _session_bounds_ns(day)
            window_start = max(open_ns, start_ns)
            window_end = min(close_ns, end_ns)
            if window_start < window_end:
                windows.append((window_start, window_end))
        day += timedelta(days=1)
    return windows


def qualifying_gap_ns(
    prev_decision_ns: int,
    next_decision_ns: int,
    *,
    holidays: frozenset[str] = _DEFAULT_HOLIDAYS,
) -> int:
    """Policy-relevant gap: longest span within expected observation windows between decisions."""
    if next_decision_ns <= prev_decision_ns:
        return 0
    windows = expected_observation_windows_between(prev_decision_ns, next_decision_ns, holidays=holidays)
    if not windows:
        return 0
    max_span = 0
    for window_start, window_end in windows:
        span = window_end - window_start
        max_span = max(max_span, span)
    return max_span


def maximum_qualifying_gap_ns(
    decision_times_ns: list[int],
    *,
    holidays: frozenset[str] = _DEFAULT_HOLIDAYS,
) -> int:
    if len(decision_times_ns) < 2:
        return 0
    sorted_times = sorted(decision_times_ns)
    max_gap = 0
    for prev, nxt in zip(sorted_times, sorted_times[1:]):
        max_gap = max(max_gap, qualifying_gap_ns(prev, nxt, holidays=holidays))
    return max_gap
