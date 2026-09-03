from datetime import UTC, datetime

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.metrics import MetricDiagnosticCode, MetricSelectionRequest, resolve_bar_at_boundary
from squeeze_core.metrics.selection import bar_end, bar_start

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 20, 22, 0, tzinfo=UTC)


def _request(**overrides) -> MetricSelectionRequest:
    values = dict(symbol="TESTA", as_of=AS_OF, source_interval=BarInterval.ONE_DAY)
    values.update(overrides)
    return MetricSelectionRequest(**values)


def test_symbol_filter_excludes_non_matching_symbols():
    wanted = make_bar(source_record_id="sel-symbol-1", symbol="TESTA")
    other = make_bar(source_record_id="sel-symbol-2", symbol="TESTB", bar_start=bar_boundary(wanted)[0].isoformat())
    start, end = bar_boundary(wanted)
    resolution = resolve_bar_at_boundary([wanted, other], _request(), target_start=start, target_end=end)
    assert resolution.observation is not None
    assert resolution.observation.symbol == "TESTA"


def test_interval_filter_excludes_a_different_interval_at_the_same_date():
    daily = make_bar(source_record_id="sel-interval-daily")
    start, end = bar_boundary(daily)
    resolution = resolve_bar_at_boundary(
        [daily], _request(source_interval=BarInterval.ONE_MINUTE), target_start=start, target_end=end
    )
    assert resolution.observation is None
    assert any(d.code is MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS for d in resolution.diagnostics)


def test_session_filter_excludes_an_adjacent_premarket_bar():
    premarket = make_bar(
        source_record_id="sel-session-premarket",
        interval="1_MINUTE",
        session="PREMARKET",
        bar_start="2026-01-15T08:00:00-05:00",
        bar_end="2026-01-15T08:01:00-05:00",
        publication_timestamp="2026-01-15T08:01:01-05:00",
    )
    start, end = bar_boundary(premarket)
    resolution = resolve_bar_at_boundary(
        [premarket],
        _request(source_interval=BarInterval.ONE_MINUTE, session_scope=(BarSession.REGULAR,)),
        target_start=start,
        target_end=end,
    )
    assert resolution.observation is None


def test_explicit_provider_selects_only_that_providers_bar():
    a = make_bar(source_record_id="sel-provider-a", provider="ALPACA_SHAPED")
    b = make_bar(source_record_id="sel-provider-b", provider="SCHWAB_SHAPED")
    start, end = bar_boundary(a)
    resolution = resolve_bar_at_boundary(
        [a, b], _request(provider="ALPACA_SHAPED"), target_start=start, target_end=end
    )
    assert resolution.observation is not None
    assert resolution.observation.observation_id == a.observation_id


def test_omitted_provider_is_ambiguous_with_two_providers():
    a = make_bar(source_record_id="sel-provider-a2", provider="ALPACA_SHAPED")
    b = make_bar(source_record_id="sel-provider-b2", provider="SCHWAB_SHAPED")
    start, end = bar_boundary(a)
    resolution = resolve_bar_at_boundary([a, b], _request(), target_start=start, target_end=end)
    assert resolution.observation is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in resolution.diagnostics)


def test_omitted_provider_is_fine_with_one_provider():
    a = make_bar(source_record_id="sel-provider-a3", provider="ALPACA_SHAPED")
    start, end = bar_boundary(a)
    resolution = resolve_bar_at_boundary([a], _request(), target_start=start, target_end=end)
    assert resolution.observation is not None


def test_point_in_time_event_before_publication_after_as_of_is_excluded():
    bar = make_bar(source_record_id="sel-pit-1", publication_timestamp="2026-01-25T16:01:00-05:00")
    start, end = bar_boundary(bar)
    resolution = resolve_bar_at_boundary([bar], _request(), target_start=start, target_end=end)
    assert resolution.observation is None


def test_point_in_time_publication_before_receipt_after_as_of_is_excluded():
    bar = make_bar(source_record_id="sel-pit-2", ingested_at="2026-01-25T22:00:00Z")
    start, end = bar_boundary(bar)
    resolution = resolve_bar_at_boundary([bar], _request(), target_start=start, target_end=end)
    assert resolution.observation is None


def test_point_in_time_fully_eligible_bar_is_selected():
    bar = make_bar(source_record_id="sel-pit-3")
    start, end = bar_boundary(bar)
    resolution = resolve_bar_at_boundary([bar], _request(), target_start=start, target_end=end)
    assert resolution.observation is not None


def test_partial_excluded_when_a_completed_version_is_also_eligible():
    partial = make_bar(source_record_id="sel-lifecycle-partial", status="PARTIAL", revision_number=0)
    completed = make_bar(
        source_record_id="sel-lifecycle-completed",
        provider_record_id="sel-completed-id",
        status="COMPLETED",
        revision_number=1,
    )
    start, end = bar_boundary(partial)
    resolution = resolve_bar_at_boundary([partial, completed], _request(), target_start=start, target_end=end)
    assert resolution.observation is not None
    assert resolution.observation.observation_id == completed.observation_id


def test_correction_visible_only_after_its_own_eligibility():
    original = make_bar(source_record_id="sel-lifecycle-orig", provider_record_id="sel-orig", ingested_at="2026-01-15T21:02:00Z")
    corrected = make_bar(
        source_record_id="sel-lifecycle-corrected",
        provider_record_id="sel-corrected",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="sel-orig",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    start, end = bar_boundary(original)
    before = resolve_bar_at_boundary(
        [original, corrected], _request(as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC)), target_start=start, target_end=end
    )
    after = resolve_bar_at_boundary([original, corrected], _request(), target_start=start, target_end=end)
    assert before.observation.observation_id == original.observation_id
    assert after.observation.observation_id == corrected.observation_id


def test_deterministic_order_independent_of_input_shuffling():
    a = make_bar(source_record_id="sel-order-a")
    b = make_bar(source_record_id="sel-order-b", provider_record_id="b-id", bar_start="2026-01-16T00:00:00-05:00", bar_end="2026-01-17T00:00:00-05:00", session_date="2026-01-16", publication_timestamp="2026-01-16T16:01:00-05:00")
    start, end = bar_boundary(a)
    forward = resolve_bar_at_boundary([a, b], _request(), target_start=start, target_end=end)
    backward = resolve_bar_at_boundary([b, a], _request(), target_start=start, target_end=end)
    assert forward.observation.observation_id == backward.observation.observation_id


def test_provider_ambiguity_is_order_independent():
    a = make_bar(source_record_id="sel-amb-a", provider="ALPACA_SHAPED")
    b = make_bar(source_record_id="sel-amb-b", provider="SCHWAB_SHAPED")
    start, end = bar_boundary(a)
    forward = resolve_bar_at_boundary([a, b], _request(), target_start=start, target_end=end)
    backward = resolve_bar_at_boundary([b, a], _request(), target_start=start, target_end=end)
    assert forward.observation is None and backward.observation is None
    assert {d.code for d in forward.diagnostics} == {d.code for d in backward.diagnostics}


def test_bar_start_and_bar_end_accessors_round_trip_metadata():
    bar = make_bar(source_record_id="sel-accessor")
    start, end = bar_boundary(bar)
    assert bar_start(bar) == start
    assert bar_end(bar) == end
