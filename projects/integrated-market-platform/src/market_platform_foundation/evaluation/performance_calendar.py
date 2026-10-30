"""Reporting-only NYSE calendar for Paper performance evaluation.

Version 1 ("paper-performance-nyse-2026/1") was frozen from the official 2026 calendar
(https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf) and expired on 2026-12-31, so a
20-session enrollment window starting after 2026-12-04 could not be formed (AUD-003). Version 2 reads the same
dates from the versioned execution-session table (nyse_calendar.py): the 2026 holidays and early closes are
unchanged, and 2027 is added. Runs record the version they were enrolled under; version-1 runs keep their meaning.
Never used to authorize execution.
"""
from datetime import date, datetime, timedelta

from .. import nyse_calendar

VERSION = "paper-performance-nyse/2"
ET = nyse_calendar.ET
NS = 1_000_000_000
HOLIDAYS = nyse_calendar.HOLIDAYS
EARLY = nyse_calendar.EARLY_CLOSES

def trading_day(day: date) -> bool:
    return nyse_calendar.is_trading_day(day)

def session_bounds(day: date) -> tuple[int,int]:
    opening,closing = nyse_calendar.session_bounds(day)
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
