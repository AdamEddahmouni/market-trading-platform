"""AUD-003 / AUD-006: the versioned NYSE execution-session calendar and the controller facts built on it (fake clock)."""
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from market_platform_foundation import nyse_calendar
from market_platform_foundation.evaluation import performance_calendar
from market_platform_foundation.intelligence.inference.paper_automation import entry_risk_blockers
from market_platform_foundation.market_data.headless_supply import collection_session
from market_platform_foundation.ui_api import paper_automation as PA
from market_platform_foundation.ui_api.paper_automation import EOD_FLATTEN_MINUTES, OVERNIGHT_REVIEW_MINUTES, market_session

ET = ZoneInfo("America/New_York")
ENTRY_CUTOFF = 15  # the owner's no_new_entries_minutes_before_close in the live policy


def at(y, m, d, hh, mm):
    return market_session(datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def entries_blocked(session):
    policy = dict(risk=dict(allow_entries=True, max_open_positions=15, max_aggregate_exposure_minor=10**12,
                            max_daily_loss_minor=10**12),
                  schedule=dict(no_new_entries_minutes_before_close=ENTRY_CUTOFF))
    blockers = entry_risk_blockers(policy, positions=[], valuation=dict(quality='CURRENT', equity_minor=10**7),
                                   day_start_equity_minor=10**7, pending_orders=[],
                                   minutes_to_close=session['minutes_to_close'], session_label=session['label'],
                                   close_guard_minutes=EOD_FLATTEN_MINUTES)
    return 'ENTRY_WINDOW_CLOSED' in blockers


def eod_flatten_window(session):  # the predicate of PaperAutomationService._eod_flatten, unchanged
    minutes = session.get('minutes_to_close')
    return session['label'] == 'REGULAR' and minutes is not None and 0 <= minutes <= EOD_FLATTEN_MINUTES


class EarlyCloseTests(unittest.TestCase):
    def test_2026_11_27_closes_at_13_00(self):
        s = at(2026, 11, 27, 12, 50)
        self.assertEqual((s['label'], s['minutes_to_close'], s['early_close_metadata']), ('REGULAR', 10, 'EARLY_CLOSE'))
        self.assertTrue(eod_flatten_window(s))
        self.assertTrue(entries_blocked(s))
        s = at(2026, 11, 27, 12, 45)
        self.assertEqual(s['minutes_to_close'], 15)
        self.assertFalse(eod_flatten_window(s))
        self.assertTrue(entries_blocked(s))  # at the owner's 15-minute cutoff
        self.assertFalse(entries_blocked(at(2026, 11, 27, 12, 44)))
        self.assertTrue(EOD_FLATTEN_MINUTES < at(2026, 11, 27, 12, 20)['minutes_to_close'] <= OVERNIGHT_REVIEW_MINUTES)

    def test_after_an_early_close_the_regular_session_is_over(self):
        for hh, mm in ((13, 0), (13, 5), (15, 52)):
            s = at(2026, 11, 27, hh, mm)
            self.assertEqual(s['label'], 'AFTER_HOURS')
            self.assertIsNone(s['minutes_to_close'])
            self.assertFalse(eod_flatten_window(s))
            self.assertTrue(entries_blocked(s))

    def test_2026_12_24_and_2027_11_26(self):
        for y, m, d in ((2026, 12, 24), (2027, 11, 26)):
            self.assertEqual(at(y, m, d, 12, 50)['minutes_to_close'], 10)
            self.assertEqual(at(y, m, d, 13, 0)['label'], 'AFTER_HOURS')

    def test_a_normal_day_still_closes_at_16_00(self):
        s = at(2026, 12, 31, 15, 50)
        self.assertEqual((s['label'], s['minutes_to_close'], s['early_close_metadata']), ('REGULAR', 10, 'REGULAR_CLOSE'))
        self.assertEqual(at(2026, 11, 25, 12, 50)['minutes_to_close'], 190)
        self.assertTrue(eod_flatten_window(at(2026, 11, 25, 15, 52)))


class CoverageTests(unittest.TestCase):
    def test_the_year_transition_into_2027(self):
        s = at(2027, 1, 4, 10, 0)
        self.assertEqual((s['label'], s['trading_day'], s['minutes_to_close']), ('REGULAR', True, 360))
        self.assertEqual(at(2027, 1, 1, 10, 0)['label'], 'CLOSED')  # New Year's Day
        self.assertEqual(nyse_calendar.previous_trading_day(date(2027, 1, 4)), date(2026, 12, 31))
        self.assertTrue(nyse_calendar.is_trading_day(date(2027, 12, 31)))  # 2028-01-01 is a Saturday: not observed

    def test_2027_holidays_are_closed(self):
        for day in ('2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05',
                    '2027-09-06', '2027-11-25', '2027-12-24'):
            d = date.fromisoformat(day)
            self.assertEqual(d.weekday() < 5, True, day)
            s = at(d.year, d.month, d.day, 11, 0)
            self.assertEqual((s['label'], s['trading_day']), ('CLOSED', False), day)
        self.assertEqual(len([h for h in nyse_calendar.HOLIDAYS if h.startswith('2027')]), 10)
        self.assertTrue(nyse_calendar.is_trading_day(date(2027, 7, 2)))
        self.assertFalse(nyse_calendar.is_early_close(date(2027, 7, 2)))

    def test_weekends(self):
        self.assertEqual(at(2026, 11, 28, 11, 0)['label'], 'CLOSED')
        self.assertEqual(at(2027, 1, 3, 11, 0)['label'], 'CLOSED')

    def test_dst_boundaries(self):
        # 2026-11-01 and 2027-03-14 are Sundays; the next sessions open at 09:30 ET in the new offset.
        self.assertEqual(at(2026, 11, 2, 9, 30)['minutes_to_close'], 390)
        self.assertEqual(at(2027, 3, 15, 15, 50)['minutes_to_close'], 10)
        opening, closing = nyse_calendar.session_bounds(date(2027, 3, 15))
        self.assertEqual(closing.utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(nyse_calendar.session_bounds(date(2027, 3, 12))[0].utcoffset().total_seconds(), -5 * 3600)

    def test_beyond_coverage_fails_closed(self):
        s = at(2028, 1, 3, 10, 0)
        self.assertEqual((s['label'], s['trading_day'], s['minutes_to_close']), ('CALENDAR_UNAVAILABLE', False, None))
        self.assertTrue(entries_blocked(s))
        self.assertFalse(eod_flatten_window(s))
        with self.assertRaisesRegex(ValueError, 'CALENDAR_UNAVAILABLE'):
            nyse_calendar.is_trading_day(date(2028, 1, 3))
        self.assertEqual(collection_session('moomoo', datetime(2028, 1, 3, 10, tzinfo=ET).timestamp())['label'],
                         'CALENDAR_UNAVAILABLE')

    def test_expiry_warning_is_reported_near_the_end_of_coverage(self):
        self.assertFalse(at(2027, 10, 1, 10, 0)['calendar_expiry_warning'])
        s = at(2027, 11, 15, 10, 0)
        self.assertTrue(s['calendar_expiry_warning'])
        self.assertEqual((s['calendar_coverage_end'], s['calendar_version']), ('2027-12-31', nyse_calendar.VERSION))

    def test_collection_expects_us_equity_data_in_2027(self):
        self.assertTrue(collection_session('moomoo', datetime(2027, 1, 4, 10, tzinfo=ET).timestamp())['data_expected'])
        self.assertFalse(collection_session('moomoo', datetime(2027, 1, 18, 10, tzinfo=ET).timestamp())['data_expected'])


class ControllerCalendarTests(unittest.TestCase):
    def rollover(self, day, trading_day=True):
        seen = []
        stub = SimpleNamespace(session=None, _detect_unplanned_carry=lambda work, closing: seen.append(closing))
        PA.PaperAutomationService._carry_rollover(stub, {}, dict(label='REGULAR', session_date=day, trading_day=trading_day), 0)
        return seen

    def test_carry_detection_looks_at_the_real_previous_session(self):
        self.assertEqual(self.rollover('2027-01-04'), ['2026-12-31'])
        self.assertEqual(self.rollover('2027-01-19'), ['2027-01-15'])
        self.assertEqual(self.rollover('2026-11-30'), ['2026-11-27'])
        self.assertEqual(self.rollover('2025-01-02'), [])  # 2024 is outside coverage: nothing is guessed

    def test_hold_sessions_count_across_the_year_end(self):
        stub = SimpleNamespace()
        entry = int(datetime(2026, 12, 30, 10, tzinfo=ET).timestamp() * 1e9)
        held = PA.PaperAutomationService._hold_sessions(stub, dict(first_entry_time_ns=entry), dict(session_date='2027-01-04'))
        self.assertEqual(held, 3)  # 12-30, 12-31, 01-04
        held = PA.PaperAutomationService._hold_sessions(stub, dict(first_entry_time_ns=entry), dict(session_date='2028-01-03'))
        self.assertEqual(held, 999)


class ReportingCalendarTests(unittest.TestCase):
    def test_a_20_session_window_from_2026_12_04_resolves(self):
        dates = performance_calendar.sessions_after(date(2026, 12, 4), 20)
        self.assertEqual(dates[0], date(2026, 12, 7))
        self.assertEqual(dates[-1], date(2027, 1, 5))
        self.assertNotIn(date(2026, 12, 25), dates)
        self.assertNotIn(date(2027, 1, 1), dates)

    def test_reporting_and_execution_agree_on_2026(self):
        self.assertEqual({h for h in performance_calendar.HOLIDAYS if h.startswith('2026')},
                         {"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
                          "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"})
        self.assertEqual({e for e in performance_calendar.EARLY if e.startswith('2026')}, {"2026-11-27", "2026-12-24"})
        start, end = performance_calendar.session_bounds(date(2026, 12, 24))
        self.assertEqual(end, int(datetime(2026, 12, 24, 13, tzinfo=ET).timestamp()) * 10**9)

    def test_frozen_evidence01_calendar_is_unchanged(self):
        from market_platform_foundation.intelligence.forward_qualification.evidence01.continuity import (
            _DEFAULT_HOLIDAYS, is_trading_day)
        self.assertEqual(len(_DEFAULT_HOLIDAYS), 20)
        self.assertTrue(is_trading_day(date(2025, 1, 9)))  # AUD-023: frozen semantics preserved, not edited
        self.assertFalse(nyse_calendar.is_trading_day(date(2025, 1, 9)))


if __name__ == '__main__':
    unittest.main()
