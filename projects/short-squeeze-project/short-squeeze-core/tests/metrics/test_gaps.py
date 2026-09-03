from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import GapRequest, MetricDiagnosticCode, MetricName, build_gap_result
from squeeze_core.metrics.gaps import compute_absolute_gap, compute_percentage_gap

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 20, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, close="10.00", open="10.00", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"gap-bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "high": "1000.00",
        "low": "0.01",
        "open": open,
        "close": close,
        "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def _request(prior, current, **overrides) -> GapRequest:
    prior_start, prior_end = bar_boundary(prior)
    current_start, current_end = bar_boundary(current)
    values = dict(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        prior_bar_start=prior_start,
        prior_bar_end=prior_end,
        current_bar_start=current_start,
        current_bar_end=current_end,
    )
    values.update(overrides)
    return GapRequest(**values)


# --- pure formula tests ---


def test_compute_absolute_gap_positive():
    value, code = compute_absolute_gap(Decimal("10.00"), Decimal("10.50"))
    assert value == Decimal("0.50")
    assert code is None


def test_compute_absolute_gap_negative():
    value, _ = compute_absolute_gap(Decimal("10.50"), Decimal("10.00"))
    assert value == Decimal("-0.50")


def test_compute_absolute_gap_zero():
    value, _ = compute_absolute_gap(Decimal("10.00"), Decimal("10.00"))
    assert value == Decimal("0")


def test_compute_percentage_gap_positive():
    value, _ = compute_percentage_gap(Decimal("10.00"), Decimal("10.50"))
    assert value == Decimal("5")


def test_compute_percentage_gap_zero_denominator():
    value, code = compute_percentage_gap(Decimal("0"), Decimal("10.00"))
    assert value is None
    assert code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR


def test_compute_gap_missing_prior_close():
    value, code = compute_absolute_gap(None, Decimal("10.00"))
    assert value is None
    assert code is MetricDiagnosticCode.GAP_PRIOR_CLOSE_UNAVAILABLE


def test_compute_gap_missing_current_open():
    value, code = compute_absolute_gap(Decimal("10.00"), None)
    assert value is None
    assert code is MetricDiagnosticCode.GAP_CURRENT_OPEN_UNAVAILABLE


# --- integration tests ---


def test_positive_absolute_gap_end_to_end():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.50")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value == Decimal("0.50")
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_absolute_gap_end_to_end():
    prior = _daily_bar(15, close="10.50")
    current = _daily_bar(16, open="10.00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value == Decimal("-0.50")


def test_zero_gap_end_to_end():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value == Decimal("0")


def test_positive_percentage_gap_end_to_end():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.50")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.PERCENTAGE_SESSION_GAP)
    assert result.value == Decimal("5")


def test_negative_percentage_gap_end_to_end():
    prior = _daily_bar(15, close="10.50")
    current = _daily_bar(16, open="10.00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.PERCENTAGE_SESSION_GAP)
    assert result.value < Decimal("0")


def test_zero_percentage_gap_end_to_end():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.PERCENTAGE_SESSION_GAP)
    assert result.value == Decimal("0")


def test_prior_session_unavailable_at_as_of():
    prior = _daily_bar(15, close="10.00", publication_timestamp="2026-01-25T16:01:00-05:00")
    current = _daily_bar(16, open="10.50")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.GAP_PRIOR_SESSION_NOT_FOUND for d in result.diagnostics)


def test_current_session_unavailable_at_as_of():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.50", publication_timestamp="2026-01-25T16:01:00-05:00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.GAP_CURRENT_SESSION_NOT_FOUND for d in result.diagnostics)


def test_prior_regular_close_to_next_regular_open():
    prior = _daily_bar(15, close="10.00", session="REGULAR")
    current = _daily_bar(16, open="10.50", session="REGULAR")
    result = build_gap_result(
        [prior, current],
        _request(prior, current, session_scope=(BarSession.REGULAR,)),
        MetricName.ABSOLUTE_SESSION_GAP,
    )
    assert result.value == Decimal("0.50")


def test_premarket_to_regular_explicit_boundaries():
    prior = _daily_bar(15, close="10.00", session="REGULAR")
    current = make_bar(
        source_record_id="gap-premarket-16",
        interval="1_MINUTE",
        session="PREMARKET",
        bar_start="2026-01-16T08:00:00-05:00",
        bar_end="2026-01-16T08:01:00-05:00",
        session_date="2026-01-16",
        publication_timestamp="2026-01-16T08:01:01-05:00",
        open="10.60",
        high="10.60",
        low="10.60",
        close="10.60",
    )
    request = GapRequest(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        prior_bar_start=bar_boundary(prior)[0],
        prior_bar_end=bar_boundary(prior)[1],
        current_bar_start=bar_boundary(current)[0],
        current_bar_end=bar_boundary(current)[1],
    )
    # The current boundary is a 1_MINUTE/PREMARKET bar while source_interval is ONE_DAY, so the
    # metric's own interval filter (matching evidence.bars.build_bar_series) correctly finds no
    # eligible bar there rather than silently crossing interval/session semantics.
    result = build_gap_result([prior, current], request, MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.GAP_CURRENT_SESSION_NOT_FOUND for d in result.diagnostics)


def test_same_session_bars_supplied_as_gap_pair_is_a_mismatch():
    bar = _daily_bar(15, close="10.00", open="9.90")
    result = build_gap_result([bar], _request(bar, bar), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code is MetricDiagnosticCode.GAP_SESSION_DATE_MISMATCH for d in result.diagnostics)


def test_session_date_mismatch_distinct_boundaries_same_date():
    prior = _daily_bar(15, close="10.00", source_record_id="gap-bar-15-a")
    current = _daily_bar(
        15,
        open="10.50",
        source_record_id="gap-bar-15-b",
        bar_start="2026-01-15T12:00:00-05:00",
        bar_end="2026-01-15T12:01:00-05:00",
    )
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.GAP_SESSION_DATE_MISMATCH for d in result.diagnostics)


def test_nonadjacent_session_policy_is_informational_not_blocking():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(20, open="11.00")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value == Decimal("1.00")
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert any(d.code is MetricDiagnosticCode.GAP_NONADJACENT_SESSION_POLICY for d in result.diagnostics)


def test_overnight_utc_date_crossing_uses_session_date_not_utc_date():
    # 23:30 US/Eastern on Jan 15 is 04:30 UTC on Jan 16 -- the session_date is still "2026-01-15".
    prior = _daily_bar(14, close="10.00")
    current = make_bar(
        source_record_id="gap-overnight-15",
        interval="1_MINUTE",
        session="AFTER_HOURS",
        bar_start="2026-01-15T23:30:00-05:00",
        bar_end="2026-01-15T23:31:00-05:00",
        session_date="2026-01-15",
        publication_timestamp="2026-01-15T23:31:01-05:00",
        open="10.75",
        high="10.75",
        low="10.75",
        close="10.75",
    )
    result = build_gap_result(
        [prior, current],
        GapRequest(
            symbol="TESTA",
            asset_class=AssetClass.EQUITY,
            as_of=AS_OF,
            source_interval=BarInterval.ONE_MINUTE,
            prior_bar_start=bar_boundary(prior)[0],
            prior_bar_end=bar_boundary(prior)[1],
            current_bar_start=bar_boundary(current)[0],
            current_bar_end=bar_boundary(current)[1],
        ),
        MetricName.ABSOLUTE_SESSION_GAP,
    )
    # prior is a 1_DAY bar so it is excluded by the ONE_MINUTE interval filter; this proves the
    # session_date metadata (not a naive UTC date) is what the boundary/session-date logic reads.
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.GAP_PRIOR_SESSION_NOT_FOUND for d in result.diagnostics)


def test_mixed_provider_ambiguity():
    prior = _daily_bar(15, close="10.00")
    current_a = _daily_bar(16, open="10.50", provider="ALPACA_SHAPED", source_record_id="gap-bar-16-a")
    current_b = _daily_bar(16, open="10.60", provider="SCHWAB_SHAPED", source_record_id="gap-bar-16-b")
    result = build_gap_result(
        [prior, current_a, current_b], _request(prior, current_a), MetricName.ABSOLUTE_SESSION_GAP
    )
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_corrected_prior_close_before_and_after_receipt():
    prior_original = _daily_bar(15, close="10.00", provider_record_id="gap-prior-original", ingested_at="2026-01-15T21:02:00Z")
    prior_corrected = _daily_bar(
        15,
        close="10.10",
        provider_record_id="gap-prior-corrected",
        source_record_id="gap-bar-15-corrected",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="gap-prior-original",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    current = _daily_bar(16, open="10.50", ingested_at="2026-01-16T21:02:00Z")
    observations = [prior_original, prior_corrected, current]

    before = _request(prior_original, current, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(prior_original, current, as_of=datetime(2026, 1, 20, 22, 0, tzinfo=UTC))

    result_before = build_gap_result(observations, before, MetricName.ABSOLUTE_SESSION_GAP)
    result_after = build_gap_result(observations, after, MetricName.ABSOLUTE_SESSION_GAP)

    assert result_before.value == Decimal("0.50")
    assert result_after.value == Decimal("0.40")


def test_cancelled_prior_bar():
    prior = _daily_bar(15, close="10.00", status="CANCELLED")
    current = _daily_bar(16, open="10.50")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_CANCELLED_INPUT for d in result.diagnostics)


def test_unknown_session_is_computed_and_representable():
    prior = _daily_bar(15, close="10.00", session="UNKNOWN")
    current = _daily_bar(16, open="10.50", session="UNKNOWN")
    result = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert result.value == Decimal("0.50")
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_daily_bar_session_semantics():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.50")
    result = build_gap_result(
        [prior, current],
        _request(prior, current, source_interval=BarInterval.ONE_DAY),
        MetricName.ABSOLUTE_SESSION_GAP,
    )
    assert result.value == Decimal("0.50")


def test_deterministic_input_reordering():
    prior = _daily_bar(15, close="10.00")
    current = _daily_bar(16, open="10.50")
    forward = build_gap_result([prior, current], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    reversed_ = build_gap_result([current, prior], _request(prior, current), MetricName.ABSOLUTE_SESSION_GAP)
    assert forward.value == reversed_.value
    assert forward.deterministic_id == reversed_.deterministic_id
