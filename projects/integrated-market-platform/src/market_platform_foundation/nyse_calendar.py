"""Versioned NYSE regular-session calendar: the execution-session authority (AUD-003, AUD-006).

One table of full-day closures and 13:00 ET early closes for the years it covers. Outside that coverage every
question raises ``CalendarUnavailable`` ("CALENDAR_UNAVAILABLE"): a date is never guessed.

Sources (NYSE holidays and trading hours, nyse.com/markets/hours-calendars, and the yearly ICE/NYSE calendars):
  * 2025: published 2025 NYSE calendar, plus the 2025-01-09 closure for the national day of mourning for President
    Carter (NYSE/ICE announcement, 2024-12-30).
  * 2026: ICE_NYSE_2026_Yearly_Trading_Calendar.pdf (the same dates as the frozen reporting calendar, version 1).
  * 2027: published NYSE 2027 holiday schedule, cross-checked against NYSE Rule 7.2 (a Saturday holiday is observed
    on the Friday before, a Sunday holiday on the Monday after; New Year's Day on a Saturday is not observed on the
    preceding December 31).

The frozen EVIDENCE-01 continuity calendar (intelligence/forward_qualification/evidence01/continuity.py) is
deliberately NOT this table and is not changed by it: frozen qualification evidence keeps its own semantics
(AUD-023, AUD-030). Extending coverage means adding a year here and bumping ``VERSION``.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

VERSION = "nyse-execution-sessions/2025-2027/1"
ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)
CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)

HOLIDAYS: frozenset[str] = frozenset((
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-11-25", "2027-12-24",
))
EARLY_CLOSES: frozenset[str] = frozenset((
    "2025-07-03", "2025-11-28", "2025-12-24",
    "2026-11-27", "2026-12-24",
    "2027-11-26",
))
COVERED_YEARS: frozenset[int] = frozenset((2025, 2026, 2027))
COVERAGE_END = date(max(COVERED_YEARS), 12, 31)
# A controller still running this close to the end of coverage reports it, so the table is extended before it lapses.
EXPIRY_WARNING_DAYS = 60


class CalendarUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("CALENDAR_UNAVAILABLE")


def covers(day: date) -> bool:
    return day.year in COVERED_YEARS


def _require(day: date) -> None:
    if not covers(day):
        raise CalendarUnavailable()


def is_trading_day(day: date) -> bool:
    _require(day)
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS


def is_early_close(day: date) -> bool:
    return is_trading_day(day) and day.isoformat() in EARLY_CLOSES


def session_close(day: date) -> time:
    if not is_trading_day(day):
        raise ValueError("NOT_A_TRADING_SESSION")
    return EARLY_CLOSE if day.isoformat() in EARLY_CLOSES else CLOSE


def session_bounds(day: date) -> tuple[datetime, datetime]:
    """Regular-session open and close as aware America/New_York datetimes."""
    close = session_close(day)
    return datetime.combine(day, OPEN, ET), datetime.combine(day, close, ET)


def close_minutes(day: date) -> int:
    close = session_close(day)
    return close.hour * 60 + close.minute


def previous_trading_day(day: date) -> date:
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def sessions_after(day: date, count: int) -> list[date]:
    result: list[date] = []
    while len(result) < count:
        day += timedelta(days=1)
        if is_trading_day(day):
            result.append(day)
    return result


def coverage(day: date) -> dict:
    """What a caller should know about the table on ``day``: version, last covered date, and an expiry warning."""
    remaining = (COVERAGE_END - day).days
    return dict(calendar_version=VERSION, calendar_coverage_end=COVERAGE_END.isoformat(),
                calendar_expiry_warning=covers(day) and remaining <= EXPIRY_WARNING_DAYS)
