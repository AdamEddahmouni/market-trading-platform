"""Official CFTC 2026 COT release schedule — do not assume Tuesday+3 days."""

from __future__ import annotations

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


# Deterministic acceptance fixtures
PIT_FIXTURE_POSITION = date(2026, 8, 18)  # Tuesday
PIT_FIXTURE_PUBLICATION = date(2026, 8, 21)  # Friday per official schedule
HOLIDAY_FIXTURE_POSITION = date(2026, 11, 24)  # Tuesday before Thanksgiving
HOLIDAY_FIXTURE_PUBLICATION = date(2026, 11, 30)  # Delayed Monday per official schedule


__all__ = [
    "COT_RELEASE_HOUR_ET",
    "COT_RELEASE_MINUTE_ET",
    "CotRelease",
    "ET",
    "HOLIDAY_FIXTURE_POSITION",
    "HOLIDAY_FIXTURE_PUBLICATION",
    "OFFICIAL_2026_PUBLICATION_DATES",
    "PIT_FIXTURE_POSITION",
    "PIT_FIXTURE_PUBLICATION",
    "infer_position_date",
    "is_visible_at",
    "latest_published_release",
    "next_expected_release",
    "publication_datetime_et",
    "publication_time_utc",
    "release_for_position_date",
]
