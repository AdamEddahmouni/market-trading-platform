"""Official WPSR / WNGSR release schedules — period end != knowledge availability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .contracts import EnergyReleaseFamily

ET = ZoneInfo("America/New_York")

WPSR_RELEASE_HOUR_ET = 10
WPSR_RELEASE_MINUTE_ET = 30
WNGSR_RELEASE_HOUR_ET = 10
WNGSR_RELEASE_MINUTE_ET = 30


@dataclass(frozen=True, slots=True)
class EnergyRelease:
    release_family: EnergyReleaseFamily
    period_end: date
    publication_date: date
    publication_hour_et: int = 10
    publication_minute_et: int = 30
    holiday_adjusted: bool = False
    note: str = ""


# Official EIA 2026 WPSR publication dates (week ending Friday -> publication date/time).
# Source: eia.gov/petroleum/supply/weekly release schedule (DOCUMENTED/OBSERVED hybrid).
OFFICIAL_2026_WPSR_RELEASES: tuple[EnergyRelease, ...] = (
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 1, 2), date(2026, 1, 7)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 1, 9), date(2026, 1, 14)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 1, 16), date(2026, 1, 22), holiday_adjusted=True, note="mlk_week"),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 1, 23), date(2026, 1, 28)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 1, 30), date(2026, 2, 4)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 2, 6), date(2026, 2, 11)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 2, 13), date(2026, 2, 19), holiday_adjusted=True, note="presidents_day_week"),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 2, 20), date(2026, 2, 25)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 2, 27), date(2026, 3, 4)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 3, 6), date(2026, 3, 11)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 3, 13), date(2026, 3, 18)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 3, 20), date(2026, 3, 25)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 3, 27), date(2026, 4, 1)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 4, 3), date(2026, 4, 8)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 4, 10), date(2026, 4, 15)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 4, 17), date(2026, 4, 22)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 4, 24), date(2026, 4, 29)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 5, 1), date(2026, 5, 6)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 5, 8), date(2026, 5, 13)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 5, 15), date(2026, 5, 20)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 5, 22), date(2026, 5, 28), holiday_adjusted=True, note="memorial_day_week"),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 5, 29), date(2026, 6, 3)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 6, 5), date(2026, 6, 10)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 6, 12), date(2026, 6, 17)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 6, 19), date(2026, 6, 24)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 6, 26), date(2026, 7, 1)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 7, 3), date(2026, 7, 9), holiday_adjusted=True, note="independence_day_week"),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 7, 10), date(2026, 7, 15)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 7, 17), date(2026, 7, 22)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 7, 24), date(2026, 7, 29)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 7, 31), date(2026, 8, 5)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 8, 7), date(2026, 8, 12)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 8, 14), date(2026, 8, 19)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 8, 21), date(2026, 8, 26)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 8, 28), date(2026, 9, 2)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 9, 4), date(2026, 9, 10), holiday_adjusted=True, note="labor_day_week"),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 9, 11), date(2026, 9, 16)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 9, 18), date(2026, 9, 23)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 9, 25), date(2026, 9, 30)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 10, 2), date(2026, 10, 7)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 10, 9), date(2026, 10, 14)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 10, 16), date(2026, 10, 21)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 10, 23), date(2026, 10, 28)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 10, 30), date(2026, 11, 4)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 11, 6), date(2026, 11, 12)),
    EnergyRelease(
        EnergyReleaseFamily.WPSR,
        date(2026, 11, 13),
        date(2026, 11, 19),
        holiday_adjusted=True,
        note="thanksgiving_week_thursday",
    ),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 11, 20), date(2026, 11, 25)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 11, 27), date(2026, 12, 2)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 12, 4), date(2026, 12, 9)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 12, 11), date(2026, 12, 16)),
    EnergyRelease(EnergyReleaseFamily.WPSR, date(2026, 12, 18), date(2026, 12, 23)),
    EnergyRelease(
        EnergyReleaseFamily.WPSR,
        date(2026, 12, 25),
        date(2026, 12, 30),
        holiday_adjusted=True,
        note="christmas_week",
    ),
)

# Official EIA 2026 WNGSR publication dates.
OFFICIAL_2026_WNGSR_RELEASES: tuple[EnergyRelease, ...] = (
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 1, 2), date(2026, 1, 8)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 1, 9), date(2026, 1, 15)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 1, 16), date(2026, 1, 22), holiday_adjusted=True, note="mlk_week_wednesday"),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 1, 23), date(2026, 1, 29)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 1, 30), date(2026, 2, 5)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 2, 6), date(2026, 2, 12)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 2, 13), date(2026, 2, 19), holiday_adjusted=True, note="presidents_day_week_wednesday"),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 2, 20), date(2026, 2, 26)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 2, 27), date(2026, 3, 5)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 3, 6), date(2026, 3, 12)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 3, 13), date(2026, 3, 19)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 3, 20), date(2026, 3, 26)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 3, 27), date(2026, 4, 2)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 4, 3), date(2026, 4, 9)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 4, 10), date(2026, 4, 16)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 4, 17), date(2026, 4, 23)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 4, 24), date(2026, 4, 30)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 5, 1), date(2026, 5, 7)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 5, 8), date(2026, 5, 14)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 5, 15), date(2026, 5, 21)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 5, 22), date(2026, 5, 28), holiday_adjusted=True, note="memorial_day_week_wednesday"),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 5, 29), date(2026, 6, 4)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 6, 5), date(2026, 6, 11)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 6, 12), date(2026, 6, 18)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 6, 19), date(2026, 6, 25)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 6, 26), date(2026, 7, 2)),
    EnergyRelease(
        EnergyReleaseFamily.WNGSR,
        date(2026, 7, 3),
        date(2026, 7, 10),
        holiday_adjusted=True,
        note="independence_day_week_friday",
    ),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 7, 10), date(2026, 7, 16)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 7, 17), date(2026, 7, 23)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 7, 24), date(2026, 7, 30)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 7, 31), date(2026, 8, 6)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 8, 7), date(2026, 8, 13)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 8, 14), date(2026, 8, 20)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 8, 21), date(2026, 8, 27)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 8, 28), date(2026, 9, 3)),
    EnergyRelease(
        EnergyReleaseFamily.WNGSR,
        date(2026, 9, 4),
        date(2026, 9, 10),
        holiday_adjusted=True,
        note="labor_day_week_thursday",
    ),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 9, 11), date(2026, 9, 17)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 9, 18), date(2026, 9, 24)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 9, 25), date(2026, 10, 1)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 10, 2), date(2026, 10, 8)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 10, 9), date(2026, 10, 15)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 10, 16), date(2026, 10, 22)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 10, 23), date(2026, 10, 29)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 10, 30), date(2026, 11, 5)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 11, 6), date(2026, 11, 12)),
    EnergyRelease(
        EnergyReleaseFamily.WNGSR,
        date(2026, 11, 13),
        date(2026, 11, 25),
        publication_hour_et=12,
        publication_minute_et=0,
        holiday_adjusted=True,
        note="thanksgiving_week_wednesday_noon",
    ),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 11, 20), date(2026, 11, 26)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 11, 27), date(2026, 12, 3)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 12, 4), date(2026, 12, 10)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 12, 11), date(2026, 12, 17)),
    EnergyRelease(EnergyReleaseFamily.WNGSR, date(2026, 12, 18), date(2026, 12, 24)),
    EnergyRelease(
        EnergyReleaseFamily.WNGSR,
        date(2026, 12, 25),
        date(2026, 12, 31),
        holiday_adjusted=True,
        note="christmas_week_wednesday",
    ),
)


def _schedule(release_family: EnergyReleaseFamily) -> tuple[EnergyRelease, ...]:
    if release_family == EnergyReleaseFamily.WPSR:
        return OFFICIAL_2026_WPSR_RELEASES
    return OFFICIAL_2026_WNGSR_RELEASES


def publication_datetime_et(release: EnergyRelease) -> datetime:
    return datetime(
        release.publication_date.year,
        release.publication_date.month,
        release.publication_date.day,
        release.publication_hour_et,
        release.publication_minute_et,
        tzinfo=ET,
    )


def publication_time_utc(release: EnergyRelease) -> str:
    return publication_datetime_et(release).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def release_for_period_end(
    period_end: date,
    release_family: EnergyReleaseFamily,
) -> EnergyRelease | None:
    for release in _schedule(release_family):
        if release.period_end == period_end:
            return release
    return None


def next_expected_release(
    release_family: EnergyReleaseFamily,
    after: date | None = None,
) -> EnergyRelease | None:
    today = after or date.today()
    for release in _schedule(release_family):
        if release.publication_date >= today:
            return release
    return None


def latest_published_release(
    release_family: EnergyReleaseFamily,
    before: date | None = None,
) -> EnergyRelease | None:
    today = before or date.today()
    latest: EnergyRelease | None = None
    for release in _schedule(release_family):
        if release.publication_date <= today:
            latest = release
    return latest


def is_visible_at(release: EnergyRelease, query_time: datetime) -> bool:
    pub_dt = publication_datetime_et(release)
    if query_time.tzinfo is None:
        query_time = query_time.replace(tzinfo=timezone.utc)
    return query_time.astimezone(ET) >= pub_dt


def naive_wednesday_would_leak(release: EnergyRelease) -> bool:
    """True when generic Wednesday 10:30 logic would leak before actual holiday release."""
    if not release.holiday_adjusted:
        return False
    naive = datetime(
        release.period_end.year,
        release.period_end.month,
        release.period_end.day,
        10,
        30,
        tzinfo=ET,
    ) + timedelta(days=5)
    actual = publication_datetime_et(release)
    return naive < actual


# Deterministic acceptance fixtures
PIT_FIXTURE_WPSR_PERIOD_END = date(2026, 8, 14)
PIT_FIXTURE_WPSR_PUBLICATION = date(2026, 8, 19)
WPSR_HOLIDAY_FIXTURE_PERIOD_END = date(2026, 11, 13)
WPSR_HOLIDAY_FIXTURE_PUBLICATION = date(2026, 11, 19)
PIT_FIXTURE_WNGSR_PERIOD_END = date(2026, 8, 14)
PIT_FIXTURE_WNGSR_PUBLICATION = date(2026, 8, 20)
WNGSR_HOLIDAY_FIXTURE_PERIOD_END = date(2026, 11, 13)
WNGSR_HOLIDAY_FIXTURE_PUBLICATION = date(2026, 11, 25)
WNGSR_HOLIDAY_FIXTURE_HOUR_ET = 12
WNGSR_HOLIDAY_FIXTURE_MINUTE_ET = 0


__all__ = [
    "ET",
    "EnergyRelease",
    "OFFICIAL_2026_WNGSR_RELEASES",
    "OFFICIAL_2026_WPSR_RELEASES",
    "PIT_FIXTURE_WNGSR_PERIOD_END",
    "PIT_FIXTURE_WNGSR_PUBLICATION",
    "PIT_FIXTURE_WPSR_PERIOD_END",
    "PIT_FIXTURE_WPSR_PUBLICATION",
    "WNGSR_HOLIDAY_FIXTURE_HOUR_ET",
    "WNGSR_HOLIDAY_FIXTURE_MINUTE_ET",
    "WNGSR_HOLIDAY_FIXTURE_PERIOD_END",
    "WNGSR_HOLIDAY_FIXTURE_PUBLICATION",
    "WPSR_HOLIDAY_FIXTURE_PERIOD_END",
    "WPSR_HOLIDAY_FIXTURE_PUBLICATION",
    "is_visible_at",
    "latest_published_release",
    "naive_wednesday_would_leak",
    "next_expected_release",
    "publication_datetime_et",
    "publication_time_utc",
    "release_for_period_end",
]
