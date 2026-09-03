from datetime import UTC, date, datetime

import pytest

from squeeze_core.metrics.source_age import build_source_age

from .conftest import make_borrow_fee, make_short_interest


def test_availability_age_is_as_of_minus_effective_time():
    observation = make_short_interest()
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    age = build_source_age(observation, as_of, reporting_period_end=observation.payload.settlement_date)
    assert age.effective_time == observation.effective_timestamp
    assert age.availability_age_seconds == int((as_of - observation.effective_timestamp).total_seconds())
    assert age.availability_age_seconds >= 0


def test_reporting_period_age_uses_calendar_days_not_seconds():
    observation = make_short_interest(settlement_date="2026-01-01")
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    age = build_source_age(observation, as_of, reporting_period_end=date(2026, 1, 1))
    assert age.reporting_period_age_days == (date(2026, 3, 1) - date(2026, 1, 1)).days


def test_publication_lag_is_publication_time_minus_reporting_period_midnight():
    observation = make_short_interest(settlement_date="2026-01-01", publication_date="2026-01-10")
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    age = build_source_age(observation, as_of, reporting_period_end=date(2026, 1, 1))
    assert age.publication_lag_seconds is not None
    assert age.publication_lag_seconds > 0


def test_borrow_observation_has_no_reporting_period_concept():
    observation = make_borrow_fee()
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    age = build_source_age(observation, as_of)
    assert age.reporting_period_end is None
    assert age.reporting_period_age_days is None
    assert age.publication_lag_seconds is None


def test_two_age_concepts_stay_independent():
    # An old reporting period received recently: availability_age is small, reporting_period_age
    # is large -- the two must never collapse into one number.
    observation = make_short_interest(settlement_date="2020-01-01", publication_date="2026-02-01")
    as_of = datetime(2026, 2, 16, tzinfo=UTC)
    age = build_source_age(observation, as_of, reporting_period_end=date(2020, 1, 1))
    assert age.reporting_period_age_days > 2000
    assert age.availability_age_seconds < 2 * 24 * 3600
