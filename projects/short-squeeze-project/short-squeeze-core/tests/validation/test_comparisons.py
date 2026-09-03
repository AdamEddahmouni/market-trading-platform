from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.validation import (
    ComparisonState,
    OriginalFieldValue,
    OriginalValueState,
    build_field_comparison,
    classify_comparison,
    serialize_field_comparison,
)

from .conftest import recovered_field


def test_exact_match():
    original = recovered_field("price", Decimal("4.20"), unit="USD")
    assert (
        classify_comparison(original, Decimal("4.20"), rebuilt_unit="USD") is ComparisonState.MATCH
    )


def test_match_after_unit_normalization():
    original = recovered_field("float", Decimal("5.1"), unit="MILLION_SHARES")
    assert (
        classify_comparison(original, Decimal("5100000"), rebuilt_unit="SHARES")
        is ComparisonState.MATCH_WITH_NORMALIZATION
    )


def test_different_value():
    original = recovered_field("price", Decimal("4.20"), unit="USD")
    assert (
        classify_comparison(original, Decimal("9.99"), rebuilt_unit="USD")
        is ComparisonState.DIFFERENT_VALUE
    )


def test_short_float_percent_versus_share_count_is_a_semantic_mismatch():
    """The BIYA mislabeling in miniature: a percent-of-float and an absolute share
    count can never agree, so this must never be reported as DIFFERENT_VALUE."""

    original = recovered_field("short_interest", Decimal("4.5"), unit="PERCENT_OF_FLOAT")
    assert (
        classify_comparison(original, Decimal("450000"), rebuilt_unit="SHARES")
        is ComparisonState.DIFFERENT_SEMANTICS
    )


def test_original_missing():
    missing = OriginalFieldValue(
        field_id="days_to_cover", state=OriginalValueState.MISSING_IN_ARTIFACT
    )
    assert classify_comparison(missing, Decimal("3")) is ComparisonState.ORIGINAL_MISSING


def test_rebuilt_unavailable():
    original = recovered_field("days_to_cover", Decimal("3"), unit="DAYS")
    assert (
        classify_comparison(original, None, rebuilt_available=False)
        is ComparisonState.REBUILT_UNAVAILABLE
    )


def test_original_default_substitution():
    substituted = OriginalFieldValue(
        field_id="news_published_at",
        state=OriginalValueState.DEFAULT_SUBSTITUTED,
        value="Unknown time",
        substituted_default="Unknown time",
    )
    assert (
        classify_comparison(substituted, "2026-07-17T10:00:00Z")
        is ComparisonState.ORIGINAL_DEFAULT_SUBSTITUTION
    )


def test_original_mislabeled_takes_precedence_over_numeric_agreement():
    original = recovered_field("short_interest", Decimal("4.5"), unit="PERCENT_OF_FLOAT")
    assert (
        classify_comparison(original, Decimal("4.5"), rebuilt_unit="PERCENT_OF_FLOAT", mislabeled=True)
        is ComparisonState.ORIGINAL_MISLABELED
    )


def test_ambiguous_original_is_incomparable():
    ambiguous = OriginalFieldValue(
        field_id="float",
        state=OriginalValueState.AMBIGUOUS,
        value="5.1",
        ambiguity_note="units not recorded",
    )
    assert classify_comparison(ambiguous, Decimal("5100000")) is ComparisonState.INCOMPARABLE


def test_unknown_on_both_sides():
    unknown = OriginalFieldValue(field_id="price", state=OriginalValueState.UNKNOWN)
    assert classify_comparison(unknown, None, rebuilt_available=False) is ComparisonState.UNKNOWN


def test_unknown_original_with_a_rebuilt_value_reports_original_missing():
    unknown = OriginalFieldValue(field_id="price", state=OriginalValueState.UNKNOWN)
    assert classify_comparison(unknown, Decimal("4.20")) is ComparisonState.ORIGINAL_MISSING


def test_days_to_cover_numerator_mismatch():
    entry = build_field_comparison(
        "days_to_cover_numerator",
        recovered_field("days_to_cover_numerator", Decimal("1000000"), unit="SHARES"),
        rebuilt_value=Decimal("1200000"),
        rebuilt_unit="SHARES",
        issues=("short-interest numerator differs between original and rebuilt",),
    )
    assert entry.comparison_state is ComparisonState.DIFFERENT_VALUE
    assert any("numerator" in issue for issue in entry.issues)


def test_days_to_cover_denominator_mismatch():
    entry = build_field_comparison(
        "days_to_cover_denominator",
        recovered_field("days_to_cover_denominator", Decimal("400000"), unit="SHARES"),
        rebuilt_value=Decimal("500000"),
        rebuilt_unit="SHARES",
    )
    assert entry.comparison_state is ComparisonState.DIFFERENT_VALUE


def test_short_interest_reporting_period_mismatch_is_recorded():
    entry = build_field_comparison(
        "short_interest",
        recovered_field("short_interest", Decimal("1000000"), unit="SHARES"),
        rebuilt_value=Decimal("1000000"),
        rebuilt_unit="SHARES",
        reporting_period=None,
        issues=("original reporting period unrecorded; rebuilt settled 2026-07-15",),
    )
    assert entry.comparison_state is ComparisonState.MATCH
    assert entry.issues


def test_news_time_mismatch():
    entry = build_field_comparison(
        "news_published_at",
        recovered_field("news_published_at", "2026-07-17T09:00:00Z"),
        rebuilt_value="2026-07-17T13:00:00Z",
        available_at_detection=False,
    )
    assert entry.comparison_state is ComparisonState.DIFFERENT_VALUE
    assert entry.available_at_detection is False


def test_provider_mismatch_is_carried_without_changing_the_state():
    entry = build_field_comparison(
        "short_interest",
        recovered_field("short_interest", Decimal("10"), unit="PERCENT", provider="yfinance"),
        rebuilt_value=Decimal("10"),
        rebuilt_unit="PERCENT",
        rebuilt_provider="finra",
    )
    assert entry.comparison_state is ComparisonState.MATCH
    assert entry.original_provider == "yfinance"
    assert entry.rebuilt_provider == "finra"


def test_ordering_is_stable_and_identity_is_deterministic():
    first = build_field_comparison(
        "price", recovered_field("price", Decimal("4.20"), unit="USD"),
        rebuilt_value=Decimal("4.20"), rebuilt_unit="USD",
    )
    second = build_field_comparison(
        "price", recovered_field("price", Decimal("4.20"), unit="USD"),
        rebuilt_value=Decimal("4.20"), rebuilt_unit="USD",
    )
    assert first.deterministic_id == second.deterministic_id
    assert serialize_field_comparison(first) == serialize_field_comparison(second)


def test_different_comparison_states_yield_different_identities():
    matched = build_field_comparison(
        "price", recovered_field("price", Decimal("4.20"), unit="USD"),
        rebuilt_value=Decimal("4.20"), rebuilt_unit="USD",
    )
    differing = build_field_comparison(
        "price", recovered_field("price", Decimal("4.20"), unit="USD"),
        rebuilt_value=Decimal("9.99"), rebuilt_unit="USD",
    )
    assert matched.deterministic_id != differing.deterministic_id


def test_timing_fields_round_trip():
    entry = build_field_comparison(
        "short_interest",
        recovered_field("short_interest", Decimal("10"), unit="PERCENT"),
        rebuilt_value=Decimal("10"),
        rebuilt_unit="PERCENT",
        rebuilt_source_time=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
        availability_age_seconds=3600,
        reporting_period_age_seconds=172800,
        publication_lag_seconds=86400,
    )
    assert entry.availability_age_seconds == 3600
    assert entry.reporting_period_age_seconds == 172800
    assert entry.publication_lag_seconds == 86400
