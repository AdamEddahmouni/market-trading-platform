"""Final Screener closure: the CFTC release calendar is no longer 2026-only.

Official tables come from the CFTC release-schedule page (vendored 2026 snapshot plus any year parsed
from the live page); a date no official table covers is inferred conservatively and labelled.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc import release_schedule as rs  # noqa: E402
from market_platform_foundation.cftc.screener_positioning import (  # noqa: E402
    POSITIONING_MARKETS,
    build_positioning,
    latest_scheduled_report_date,
    publication_for,
)

PAGE = (ROOT / "tests" / "fixtures" / "cftc" / "release_schedule_page_20260929.html").read_text(encoding="utf-8")


def synthetic_page(year: int, releases: list[tuple[date, bool]]) -> str:
    """A page shaped like the official one (month rows, ``*`` for a delayed date)."""

    rows = []
    for month in range(1, 13):
        cells = "".join(f"<td>{day.day:02d}{'*' if delayed else ''}</td>" for day, delayed in releases if day.month == month)
        rows.append(f"<tr><td>{rs._calendar.month_name[month]}</td>{cells}<td>&nbsp;</td></tr>")
    return (f"<p>tentative schedule</p><h3><strong>{year} Release Schedule</strong></h3><table><tbody>"
            f"<tr><td>Month</td><td colspan='5'>Dates</td></tr>{''.join(rows)}</tbody></table>")


def es_row(report_date: str) -> dict:
    return {"cftc_contract_market_code": "13874A", "report_date_as_yyyy_mm_dd": f"{report_date}T00:00:00.000",
            "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", "id": f"{report_date}-ES",
            "open_interest_all": "2000000"}


class OfficialPageTests(unittest.TestCase):
    def test_the_official_page_parses_to_the_vendored_2026_table(self):
        parsed = rs.parse_official_schedule_html(PAGE)
        self.assertEqual(list(parsed), [2026])
        self.assertEqual(parsed[2026], rs.OFFICIAL_2026_RELEASES)
        self.assertEqual(sum(1 for *_, delayed in parsed[2026] if delayed), 6)

    def test_position_date_is_the_tuesday_before_the_release(self):
        self.assertEqual(rs.position_date_for_publication(date(2026, 1, 5)), date(2025, 12, 30))   # delayed Monday
        self.assertEqual(rs.position_date_for_publication(date(2026, 9, 25)), date(2026, 9, 22))   # Friday
        self.assertEqual(rs.position_date_for_publication(date(2026, 11, 30)), date(2026, 11, 24))

    def test_incomplete_or_implausible_pages_fail_closed(self):
        for page, code in (("<p>no schedule here</p>", "NO_SCHEDULE_HEADING"),
                           (PAGE.replace("</table>", ""), "NO_TABLE_2026"),
                           (synthetic_page(2027, [(date(2027, 1, 8), False)]), "RELEASE_COUNT_2027_1"),
                           (PAGE.replace(">09<", ">9x<", 1), "UNREADABLE_DATE_2026"),
                           (PAGE.replace(">16<", ">16*<", 1), "IMPLAUSIBLE_RELEASE_DAY_2026-01-16")):
            with self.subTest(code), self.assertRaises(rs.ScheduleParseError) as caught:
                rs.parse_official_schedule_html(page)
            self.assertEqual(str(caught.exception), code)

    def test_a_new_year_needs_no_code_edit(self):
        # A future page listing 2027: its dates become official, not inferred.
        fridays = [date(2027, 1, 8) + timedelta(days=7 * week) for week in range(51)]
        releases = [(day + timedelta(days=3), True) if day == date(2027, 11, 26) else (day, False) for day in fridays]
        calendar = rs.ReleaseCalendar.vendored().with_official(
            rs.parse_official_schedule_html(synthetic_page(2027, releases)), "CFTC_RELEASE_SCHEDULE_PAGE")
        self.assertEqual(calendar.describe()["official_years"], [2026, 2027])
        self.assertEqual(calendar.describe()["sources"], {"2026": "VENDORED_OFFICIAL_SNAPSHOT",
                                                          "2027": "CFTC_RELEASE_SCHEDULE_PAGE"})
        self.assertEqual(calendar.publication(date(2027, 3, 2)),
                         (datetime(2027, 3, 5, 20, 30, tzinfo=UTC), rs.BASIS_OFFICIAL))
        self.assertEqual(calendar.publication(date(2027, 11, 23)),
                         (datetime(2027, 11, 29, 20, 30, tzinfo=UTC), rs.BASIS_OFFICIAL_DELAYED))


class InferenceTests(unittest.TestCase):
    def test_the_inference_reproduces_every_official_2026_release(self):
        bare = rs.ReleaseCalendar({}, {})
        for publication, position, delayed in rs.OFFICIAL_2026_RELEASES:
            with self.subTest(position=position):
                released, basis = bare.publication(position)
                self.assertEqual(released.astimezone(rs.ET).date(), publication)
                self.assertEqual(basis, rs.BASIS_INFERRED_HOLIDAY if delayed else rs.BASIS_INFERRED_STANDARD)

    def test_federal_holidays_follow_observance_rules(self):
        self.assertIn(date(2027, 12, 31), rs.federal_holidays(2027))       # Saturday 1 Jan 2028, observed Friday
        self.assertNotIn(date(2028, 1, 1), rs.federal_holidays(2028))
        self.assertIn(date(2027, 6, 18), rs.federal_holidays(2027))        # Juneteenth on a Saturday
        self.assertIn(date(2027, 11, 25), rs.federal_holidays(2027))       # fourth Thursday of November
        self.assertIn(date(2026, 1, 19), rs.federal_holidays(2026))        # MLK Day (a Monday: no delay)

    def test_unscheduled_holiday_weeks_are_never_released_early(self):
        calendar = rs.ReleaseCalendar.vendored()
        # Thanksgiving 2027 (no official 2027 table): the next business day after Friday.
        self.assertEqual(calendar.publication(date(2027, 11, 23)),
                         (datetime(2027, 11, 29, 20, 30, tzinfo=UTC), rs.BASIS_INFERRED_HOLIDAY))
        # The week spanning New Year 2027 is outside the 2026 table too.
        self.assertEqual(calendar.publication(date(2026, 12, 29)),
                         (datetime(2027, 1, 4, 20, 30, tzinfo=UTC), rs.BASIS_INFERRED_HOLIDAY))
        # A normal 2027 week keeps the S12 basis name.
        self.assertEqual(calendar.publication(date(2027, 3, 2))[1], rs.BASIS_INFERRED_STANDARD)

    def test_latest_visible_position_crosses_the_year_boundary(self):
        self.assertEqual(latest_scheduled_report_date(datetime(2027, 1, 1, 21, 0, tzinfo=UTC)), date(2026, 12, 22))
        self.assertEqual(latest_scheduled_report_date(datetime(2027, 1, 4, 20, 30, tzinfo=UTC)), date(2026, 12, 29))
        self.assertEqual(latest_scheduled_report_date(datetime(2027, 1, 8, 20, 29, tzinfo=UTC)), date(2026, 12, 29))
        self.assertEqual(latest_scheduled_report_date(datetime(2027, 1, 8, 20, 30, tzinfo=UTC)), date(2027, 1, 5))
        self.assertEqual(latest_scheduled_report_date(datetime(2027, 6, 12, tzinfo=UTC)), date(2027, 6, 8))


class ScreenerVisibilityTests(unittest.TestCase):
    def test_a_2027_holiday_week_report_is_not_shown_on_the_usual_friday(self):
        rows = [es_row("2027-11-23"), es_row("2027-11-16")]
        market = POSITIONING_MARKETS["ES"]
        friday = build_positioning(rows, market, now=datetime(2027, 11, 26, 21, 0, tzinfo=UTC))
        self.assertEqual(friday["report_date"], "2027-11-16")
        monday = build_positioning(rows, market, now=datetime(2027, 11, 29, 20, 30, tzinfo=UTC))
        self.assertEqual((monday["report_date"], monday["publication_basis"]),
                         ("2027-11-23", rs.BASIS_INFERRED_HOLIDAY))
        self.assertEqual(monday["latest_scheduled_report_date"], "2027-11-23")

    def test_publication_for_uses_the_given_calendar(self):
        self.assertEqual(publication_for(date(2026, 11, 24))[1], rs.BASIS_OFFICIAL_DELAYED)
        self.assertEqual(publication_for(date(2026, 11, 24), rs.ReleaseCalendar({}, {}))[1], rs.BASIS_INFERRED_HOLIDAY)


if __name__ == "__main__":
    unittest.main()
