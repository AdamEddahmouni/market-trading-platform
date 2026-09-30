"""Official CFTC COT release schedule — do not assume Tuesday+3 days.

The CFTC publishes its release dates one calendar year at a time on
``SCHEDULE_URL`` (a date marked ``*`` is delayed by a federal holiday). The 2026
table below is a vendored snapshot of that page; :class:`ReleaseCalendar` adds any
further year parsed from the live page (:func:`parse_official_schedule_html`), so a
new year needs no code edit. A position date no official table covers gets a
conservative, labelled inference (:meth:`ReleaseCalendar.publication`): Friday
15:30 ET in a week without a federal holiday, otherwise the next business day
after that Friday — never earlier than a holiday-delayed official release.
"""

from __future__ import annotations

import calendar as _calendar
import html as _html
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
COT_RELEASE_HOUR_ET = 15
COT_RELEASE_MINUTE_ET = 30


@dataclass(frozen=True, slots=True)
class CotRelease:
    """Maps position-as-of Tuesday to official publication date."""

    position_date: date
    publication_date: date
    delayed: bool = False
    note: str = ""


# Official CFTC 2026 release schedule: (publication_date, position_date, delayed)
OFFICIAL_2026_RELEASES: tuple[tuple[date, date, bool], ...] = (
    (date(2026, 1, 5), date(2025, 12, 30), True),
    (date(2026, 1, 9), date(2026, 1, 6), False),
    (date(2026, 1, 16), date(2026, 1, 13), False),
    (date(2026, 1, 23), date(2026, 1, 20), False),
    (date(2026, 1, 30), date(2026, 1, 27), False),
    (date(2026, 2, 6), date(2026, 2, 3), False),
    (date(2026, 2, 13), date(2026, 2, 10), False),
    (date(2026, 2, 20), date(2026, 2, 17), False),
    (date(2026, 2, 27), date(2026, 2, 24), False),
    (date(2026, 3, 6), date(2026, 3, 3), False),
    (date(2026, 3, 13), date(2026, 3, 10), False),
    (date(2026, 3, 20), date(2026, 3, 17), False),
    (date(2026, 3, 27), date(2026, 3, 24), False),
    (date(2026, 4, 3), date(2026, 3, 31), False),
    (date(2026, 4, 10), date(2026, 4, 7), False),
    (date(2026, 4, 17), date(2026, 4, 14), False),
    (date(2026, 4, 24), date(2026, 4, 21), False),
    (date(2026, 5, 1), date(2026, 4, 28), False),
    (date(2026, 5, 8), date(2026, 5, 5), False),
    (date(2026, 5, 15), date(2026, 5, 12), False),
    (date(2026, 5, 22), date(2026, 5, 19), False),
    (date(2026, 5, 29), date(2026, 5, 26), False),
    (date(2026, 6, 5), date(2026, 6, 2), False),
    (date(2026, 6, 12), date(2026, 6, 9), False),
    (date(2026, 6, 22), date(2026, 6, 16), True),
    (date(2026, 6, 26), date(2026, 6, 23), False),
    (date(2026, 7, 6), date(2026, 6, 30), True),
    (date(2026, 7, 10), date(2026, 7, 7), False),
    (date(2026, 7, 17), date(2026, 7, 14), False),
    (date(2026, 7, 24), date(2026, 7, 21), False),
    (date(2026, 7, 31), date(2026, 7, 28), False),
    (date(2026, 8, 7), date(2026, 8, 4), False),
    (date(2026, 8, 14), date(2026, 8, 11), False),
    (date(2026, 8, 21), date(2026, 8, 18), False),
    (date(2026, 8, 28), date(2026, 8, 25), False),
    (date(2026, 9, 4), date(2026, 9, 1), False),
    (date(2026, 9, 11), date(2026, 9, 8), False),
    (date(2026, 9, 18), date(2026, 9, 15), False),
    (date(2026, 9, 25), date(2026, 9, 22), False),
    (date(2026, 10, 2), date(2026, 9, 29), False),
    (date(2026, 10, 9), date(2026, 10, 6), False),
    (date(2026, 10, 16), date(2026, 10, 13), False),
    (date(2026, 10, 23), date(2026, 10, 20), False),
    (date(2026, 10, 30), date(2026, 10, 27), False),
    (date(2026, 11, 6), date(2026, 11, 3), False),
    (date(2026, 11, 16), date(2026, 11, 10), True),
    (date(2026, 11, 20), date(2026, 11, 17), False),
    (date(2026, 11, 30), date(2026, 11, 24), True),  # Thanksgiving week
    (date(2026, 12, 4), date(2026, 12, 1), False),
    (date(2026, 12, 11), date(2026, 12, 8), False),
    (date(2026, 12, 18), date(2026, 12, 15), False),
    (date(2026, 12, 28), date(2026, 12, 22), True),
)

# Backward-compatible alias
OFFICIAL_2026_PUBLICATION_DATES: tuple[tuple[date, bool], ...] = tuple(
    (pub, delayed) for pub, _, delayed in OFFICIAL_2026_RELEASES
)


def publication_datetime_et(publication_date: date) -> datetime:
    return datetime(
        publication_date.year,
        publication_date.month,
        publication_date.day,
        COT_RELEASE_HOUR_ET,
        COT_RELEASE_MINUTE_ET,
        tzinfo=ET,
    )


def publication_time_utc(publication_date: date) -> str:
    return publication_datetime_et(publication_date).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def infer_position_date(publication_date: date) -> date:
    """Infer Tuesday position date from publication date using official schedule."""
    for pub, position, _delayed in OFFICIAL_2026_RELEASES:
        if pub == publication_date:
            return position
    # Conservative fallback for dates outside published schedule window
    weekday = publication_date.weekday()
    if weekday == 4:  # Friday
        return publication_date - timedelta(days=3)
    if weekday == 0:  # Monday delayed release
        return publication_date - timedelta(days=6)
    return publication_date - timedelta(days=3)


def release_for_position_date(position_date: date) -> CotRelease | None:
    for pub, pos, delayed in OFFICIAL_2026_RELEASES:
        if pos == position_date:
            return CotRelease(
                position_date=position_date,
                publication_date=pub,
                delayed=delayed,
                note="official_2026_schedule" if delayed else "",
            )
    return None


def next_expected_release(after: date | None = None) -> date | None:
    today = after or date.today()
    for pub, _ in OFFICIAL_2026_PUBLICATION_DATES:
        if pub >= today:
            return pub
    return None


def latest_published_release(before: date | None = None) -> date | None:
    today = before or date.today()
    latest: date | None = None
    for pub, _ in OFFICIAL_2026_PUBLICATION_DATES:
        if pub <= today:
            latest = pub
    return latest


def is_visible_at(
    publication_date: date,
    query_time: datetime,
) -> bool:
    """PIT visibility — data invisible until official 15:30 ET publication."""
    pub_dt = publication_datetime_et(publication_date)
    if query_time.tzinfo is None:
        query_time = query_time.replace(tzinfo=timezone.utc)
    return query_time.astimezone(ET) >= pub_dt


# ------------------------------------------------------------------ calendar (final Screener closure)
SCHEDULE_URL = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm"

BASIS_OFFICIAL = "CFTC_OFFICIAL_SCHEDULE"
BASIS_OFFICIAL_DELAYED = "CFTC_OFFICIAL_SCHEDULE_DELAYED"
#: No official table covers the date and no federal holiday falls Tuesday–Friday: the usual Friday release.
BASIS_INFERRED_STANDARD = "PUBLICATION_TIME_INFERRED_TUESDAY_PLUS_3"
#: No official table covers the date and a federal holiday falls Tuesday–Friday: the next business day after
#: that Friday (every 2026 holiday delay was exactly that). Later, never earlier, than the likely release.
BASIS_INFERRED_HOLIDAY = "PUBLICATION_TIME_INFERRED_HOLIDAY_DELAY"

Release = tuple[date, date, bool]   # (publication_date, position_date, delayed)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, _calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    return day - timedelta(days=1) if day.weekday() == 5 else day + timedelta(days=1) if day.weekday() == 6 else day


def federal_holidays(year: int) -> frozenset[date]:
    """US federal holidays (5 U.S.C. 6103) as observed: Saturday → Friday, Sunday → Monday."""

    fixed = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4), date(year, 11, 11), date(year, 12, 25)]
    days = {_observed(day) for day in fixed}
    days |= {_nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), _last_weekday(year, 5, 0),
             _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 10, 0, 2), _nth_weekday(year, 11, 3, 4)}
    # A Saturday 1 January of the next year is observed on 31 December of this one.
    if _observed(date(year + 1, 1, 1)).year == year:
        days.add(_observed(date(year + 1, 1, 1)))
    return frozenset(day for day in days if day.year == year)


def _is_holiday(day: date) -> bool:
    return day in federal_holidays(day.year)


def position_date_for_publication(publication: date) -> date:
    """The position Tuesday a release reports: the latest Tuesday before the release day."""

    day = publication - timedelta(days=1)
    return day - timedelta(days=(day.weekday() - 1) % 7)


_MONTHS = {name.lower(): number for number, name in enumerate(_calendar.month_name) if name}
_HEADING = re.compile(r"(\d{4})\s+Release\s+Schedule", re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)


class ScheduleParseError(ValueError):
    """The official page did not yield a complete, consistent year: nothing from it is used."""


def _text(fragment: str) -> str:
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ").split())


def parse_official_schedule_html(page: str) -> dict[int, tuple[Release, ...]]:
    """Every ``<year> Release Schedule`` table on the CFTC page, validated; the whole page fails closed.

    A year must list 48–54 releases, each on a weekday, strictly increasing in release and position
    date, and a ``*``-marked (delayed) release must not fall on a Friday.
    """

    headings = list(_HEADING.finditer(page))
    if not headings:
        raise ScheduleParseError("NO_SCHEDULE_HEADING")
    years: dict[int, tuple[Release, ...]] = {}
    for index, heading in enumerate(headings):
        year = int(heading.group(1))
        end = headings[index + 1].start() if index + 1 < len(headings) else len(page)
        block = page[heading.end():end]
        table_end = block.lower().find("</table>")
        if table_end < 0:
            raise ScheduleParseError(f"NO_TABLE_{year}")
        releases: list[Release] = []
        for row in _ROW.findall(block[:table_end]):
            cells = [_text(cell) for cell in _CELL.findall(row)]
            if not cells or cells[0].lower() not in _MONTHS:
                continue
            month = _MONTHS[cells[0].lower()]
            for cell in cells[1:]:
                if not cell:
                    continue
                match = re.fullmatch(r"(\d{1,2})(\*?)", cell)
                if match is None:
                    raise ScheduleParseError(f"UNREADABLE_DATE_{year}")
                try:
                    publication = date(year, month, int(match.group(1)))
                except ValueError as exc:
                    raise ScheduleParseError(f"INVALID_DATE_{year}") from exc
                releases.append((publication, position_date_for_publication(publication), bool(match.group(2))))
        if not 48 <= len(releases) <= 54:
            raise ScheduleParseError(f"RELEASE_COUNT_{year}_{len(releases)}")
        for position, (pub, pos, delayed) in enumerate(releases):
            if pub.weekday() > 4 or (delayed and pub.weekday() == 4):
                raise ScheduleParseError(f"IMPLAUSIBLE_RELEASE_DAY_{pub.isoformat()}")
            if position and (pub <= releases[position - 1][0] or pos <= releases[position - 1][1]):
                raise ScheduleParseError(f"NOT_INCREASING_{pub.isoformat()}")
        years[year] = tuple(releases)
    return years


@dataclass(frozen=True, slots=True)
class ReleaseCalendar:
    """Official release tables by year, plus a labelled conservative inference outside them (immutable)."""

    official: Mapping[int, tuple[Release, ...]]
    sources: Mapping[int, str]

    @classmethod
    def vendored(cls) -> ReleaseCalendar:
        return cls({2026: OFFICIAL_2026_RELEASES}, {2026: "VENDORED_OFFICIAL_SNAPSHOT"})

    def with_official(self, years: Mapping[int, Iterable[Release]], source: str) -> ReleaseCalendar:
        """A calendar where each given year's table replaces the one held (the newer official page wins)."""

        official = dict(self.official)
        sources = dict(self.sources)
        for year, releases in years.items():
            official[year] = tuple(releases)
            sources[year] = source
        return ReleaseCalendar(official, sources)

    def official_release(self, position: date) -> Release | None:
        for year in (position.year, position.year + 1):
            for release in self.official.get(year, ()):
                if release[1] == position:
                    return release
        return None

    def publication(self, position: date) -> tuple[datetime, str]:
        """UTC release time of a position date and its basis (official, or which inference)."""

        release = self.official_release(position)
        if release is not None:
            return (publication_datetime_et(release[0]).astimezone(timezone.utc),
                    BASIS_OFFICIAL_DELAYED if release[2] else BASIS_OFFICIAL)
        friday = position + timedelta(days=(4 - position.weekday()) % 7 or 7)
        week = [position + timedelta(days=offset) for offset in range((friday - position).days + 1)]
        if not any(_is_holiday(day) for day in week):
            return publication_datetime_et(friday).astimezone(timezone.utc), BASIS_INFERRED_STANDARD
        day = friday + timedelta(days=1)
        while day.weekday() > 4 or _is_holiday(day):
            day += timedelta(days=1)
        return publication_datetime_et(day).astimezone(timezone.utc), BASIS_INFERRED_HOLIDAY

    def is_visible(self, position: date, now: datetime) -> bool:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now >= self.publication(position)[0]

    def latest_visible_position(self, now: datetime) -> date | None:
        """The newest position Tuesday whose release time has passed at ``now`` (official or inferred)."""

        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        today = now.astimezone(ET).date()
        tuesday = today - timedelta(days=(today.weekday() - 1) % 7)
        for weeks in range(5):
            position = tuesday - timedelta(days=7 * weeks)
            if self.is_visible(position, now):
                return position
        return None

    def describe(self) -> dict[str, object]:
        return {"official_years": sorted(self.official),
                "sources": {str(year): source for year, source in sorted(self.sources.items())},
                "schedule_url": SCHEDULE_URL}


# Deterministic acceptance fixtures
PIT_FIXTURE_POSITION = date(2026, 8, 18)  # Tuesday
PIT_FIXTURE_PUBLICATION = date(2026, 8, 21)  # Friday per official schedule
HOLIDAY_FIXTURE_POSITION = date(2026, 11, 24)  # Tuesday before Thanksgiving
HOLIDAY_FIXTURE_PUBLICATION = date(2026, 11, 30)  # Delayed Monday per official schedule


__all__ = [
    "BASIS_INFERRED_HOLIDAY",
    "BASIS_INFERRED_STANDARD",
    "BASIS_OFFICIAL",
    "BASIS_OFFICIAL_DELAYED",
    "COT_RELEASE_HOUR_ET",
    "COT_RELEASE_MINUTE_ET",
    "CotRelease",
    "ET",
    "HOLIDAY_FIXTURE_POSITION",
    "HOLIDAY_FIXTURE_PUBLICATION",
    "OFFICIAL_2026_PUBLICATION_DATES",
    "PIT_FIXTURE_POSITION",
    "PIT_FIXTURE_PUBLICATION",
    "ReleaseCalendar",
    "SCHEDULE_URL",
    "ScheduleParseError",
    "federal_holidays",
    "parse_official_schedule_html",
    "position_date_for_publication",
    "infer_position_date",
    "is_visible_at",
    "latest_published_release",
    "next_expected_release",
    "publication_datetime_et",
    "publication_time_utc",
    "release_for_position_date",
]
