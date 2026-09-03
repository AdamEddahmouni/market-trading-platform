from datetime import datetime

from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.evidence import (
    BarExpectation,
    BarExpectationState,
    BarSeriesDiagnosticCode,
    BarSeriesPolicy,
    build_bar_series,
)

from tests.adapters.market_bars.test_models_and_parsing import record_values
from tests.adapters.market_bars.test_normalizer import context


def _bar(provider_id, *, receipt="2026-01-15T14:40:00Z", **updates):
    raw = record_values(
        provider_record_id=provider_id,
        source_record_id=provider_id,
        **updates,
    )
    return normalize_market_bar_record(raw, context(receipt)).observations[0]


def _policy(**updates):
    values = {
        "symbol": "testa",
        "as_of": datetime.fromisoformat("2026-01-15T14:45:00+00:00"),
        "interval": "1_MINUTE",
    }
    values.update(updates)
    return BarSeriesPolicy(**values)


def test_series_filters_symbol_interval_and_session_without_calculation():
    regular = _bar("regular")
    premarket = _bar(
        "premarket",
        session="PREMARKET",
        session_date="2026-01-15",
        bar_start="2026-01-15T08:00:00-05:00",
        bar_end="2026-01-15T08:01:00-05:00",
        publication_timestamp="2026-01-15T08:01:01-05:00",
    )
    other_interval = _bar(
        "five-minute",
        interval="5_MINUTES",
        bar_end="2026-01-15T09:35:00-05:00",
        publication_timestamp="2026-01-15T09:35:01-05:00",
    )
    other_symbol = _bar("other", symbol="TESTB")
    series = build_bar_series(
        (premarket, other_interval, other_symbol, regular),
        _policy(sessions=("REGULAR",)),
    )
    assert [item.source_record_id for item in series.observations] == ["regular"]
    dumped = series.model_dump(mode="json")
    forbidden = {"return", "rvol", "momentum", "indicator", "score", "rank", "signal"}
    assert forbidden.isdisjoint(dumped)


def test_series_orders_by_bar_start_then_source_identity_stably():
    later = _bar(
        "later",
        bar_start="2026-01-15T09:31:00-05:00",
        bar_end="2026-01-15T09:32:00-05:00",
        publication_timestamp="2026-01-15T09:32:01-05:00",
    )
    earlier_b = _bar("earlier-b", provider="YAHOO_SHAPED")
    earlier_a = _bar("earlier-a", provider="IBKR_SHAPED")
    first = build_bar_series((later, earlier_b, earlier_a), _policy())
    second = build_bar_series((earlier_a, later, earlier_b), _policy())
    assert first == second
    assert [item.source_record_id for item in first.observations] == [
        "earlier-a",
        "earlier-b",
        "later",
    ]
    assert first.latest_observation_id == later.observation_id


def test_future_publication_and_receipt_are_excluded():
    future_publication = _bar(
        "future-publication",
        publication_timestamp="2026-01-15T10:00:00-05:00",
        receipt="2026-01-15T14:40:00Z",
    )
    future_receipt = _bar("future-receipt", receipt="2026-01-15T15:00:00Z")
    series = build_bar_series((future_publication, future_receipt), _policy())
    assert series.observations == ()
    assert {item.code for item in series.diagnostics} >= {
        BarSeriesDiagnosticCode.NOT_YET_PUBLISHED,
        BarSeriesDiagnosticCode.NOT_YET_RECEIVED,
    }


def test_duplicate_boundary_is_diagnosed_without_suppression():
    left = _bar("left", provider="SCHWAB_SHAPED")
    right = _bar("right", provider="IBKR_SHAPED")
    series = build_bar_series((left, right), _policy())
    assert len(series.observations) == 2
    assert BarSeriesDiagnosticCode.DUPLICATE_BOUNDARY in {item.code for item in series.diagnostics}


def test_explicit_lifecycle_progression_is_not_duplicate_boundary():
    partial = _bar("partial", status="PARTIAL")
    complete = _bar("complete", supersedes_provider_record_id="partial")
    series = build_bar_series((partial, complete), _policy())
    assert BarSeriesDiagnosticCode.DUPLICATE_BOUNDARY not in {item.code for item in series.diagnostics}


def test_overlapping_intervals_are_diagnosed_without_resampling():
    first = _bar(
        "first-five",
        interval="5_MINUTES",
        bar_end="2026-01-15T09:35:00-05:00",
        publication_timestamp="2026-01-15T09:35:01-05:00",
    )
    overlap = _bar(
        "overlap-five",
        interval="5_MINUTES",
        bar_start="2026-01-15T09:34:00-05:00",
        bar_end="2026-01-15T09:39:00-05:00",
        publication_timestamp="2026-01-15T09:39:01-05:00",
    )
    series = build_bar_series((first, overlap), _policy(interval="5_MINUTES"))
    assert BarSeriesDiagnosticCode.OVERLAPPING_INTERVAL in {item.code for item in series.diagnostics}
    assert len(series.observations) == 2


def test_explicit_expected_missing_closed_and_unknown_intervals_are_distinct():
    start = datetime.fromisoformat("2026-01-15T14:30:00+00:00")
    end = datetime.fromisoformat("2026-01-15T14:31:00+00:00")
    expectations = (
        BarExpectation(start=start, end=end, state=BarExpectationState.EXPECTED),
        BarExpectation(
            start=datetime.fromisoformat("2026-01-15T14:31:00+00:00"),
            end=datetime.fromisoformat("2026-01-15T14:32:00+00:00"),
            state=BarExpectationState.SESSION_CLOSED,
        ),
        BarExpectation(
            start=datetime.fromisoformat("2026-01-15T14:32:00+00:00"),
            end=datetime.fromisoformat("2026-01-15T14:33:00+00:00"),
            state=BarExpectationState.UNKNOWN_EXPECTATION,
        ),
    )
    series = build_bar_series((), _policy(expectations=expectations))
    assert {item.code for item in series.diagnostics} == {
        BarSeriesDiagnosticCode.EXPECTED_INTERVAL_MISSING,
        BarSeriesDiagnosticCode.SESSION_CLOSED,
        BarSeriesDiagnosticCode.UNKNOWN_EXPECTATION,
    }


def test_present_expected_interval_is_not_reported_missing():
    bar = _bar("present")
    metadata = bar.provenance.provider_metadata
    expectation = BarExpectation(
        start=metadata["bar_start"],
        end=metadata["bar_end"],
        state=BarExpectationState.EXPECTED,
    )
    series = build_bar_series((bar,), _policy(expectations=(expectation,)))
    assert BarSeriesDiagnosticCode.EXPECTED_INTERVAL_MISSING not in {item.code for item in series.diagnostics}


def test_same_clock_boundary_on_different_session_dates_does_not_collide():
    first = _bar("day-one")
    second = _bar(
        "day-two",
        session_date="2026-01-16",
        bar_start="2026-01-16T09:30:00-05:00",
        bar_end="2026-01-16T09:31:00-05:00",
        publication_timestamp="2026-01-16T09:31:01-05:00",
        receipt="2026-01-16T14:31:02Z",
    )
    series = build_bar_series(
        (second, first),
        _policy(as_of=datetime.fromisoformat("2026-01-16T15:00:00+00:00")),
    )
    assert len(series.observations) == 2
    assert BarSeriesDiagnosticCode.DUPLICATE_BOUNDARY not in {item.code for item in series.diagnostics}


def test_series_hash_changes_only_with_objective_series_content():
    bar = _bar("stable")
    first = build_bar_series((bar,), _policy())
    second = build_bar_series((bar,), _policy())
    assert first.series_hash == second.series_hash
    assert first.series_id == second.series_id
