"""Reporting-only NYSE calendar, frozen from the official 2026 calendar.
Source: https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf
Never used to authorize execution or to extend the execution calendar.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

VERSION = "paper-performance-nyse-2026/1"
ET = ZoneInfo("America/New_York")
NS = 1_000_000_000
HOLIDAYS = frozenset(("2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25",
                      "2026-06-19","2026-07-03","2026-09-07","2026-11-26","2026-12-25"))
EARLY = frozenset(("2026-11-27","2026-12-24"))

def trading_day(day: date) -> bool:
    if day.year != 2026:
        raise ValueError("CALENDAR_UNAVAILABLE")
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS

def session_bounds(day: date) -> tuple[int,int]:
    if not trading_day(day):
        raise ValueError("NOT_A_TRADING_SESSION")
    opening = datetime.combine(day,time(9,30),ET)
    closing = datetime.combine(day,time(13 if day.isoformat() in EARLY else 16),ET)
    return int(opening.timestamp())*NS,int(closing.timestamp())*NS

def sessions_after(day: date, count: int) -> list[date]:
    result=[]
    while len(result)<count:
        day += timedelta(days=1)
        if trading_day(day):
            result.append(day)
    return result

def local_date(epoch_ns: int) -> date:
    return datetime.fromtimestamp(epoch_ns/NS,ET).date()
