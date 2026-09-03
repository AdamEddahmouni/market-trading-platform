from squeeze_core.metrics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics


def test_diagnostic_codes_are_stable_string_literals():
    # Regression guard: these codes are a public contract; an accidental rename must fail here.
    expected = {
        "METRIC_MISSING_SYMBOL",
        "METRIC_MISSING_AS_OF",
        "METRIC_UNSUPPORTED_METRIC",
        "METRIC_UNSUPPORTED_VERSION",
        "METRIC_NO_ELIGIBLE_BARS",
        "METRIC_AMBIGUOUS_PROVIDER",
        "METRIC_INCOMPATIBLE_INTERVAL",
        "METRIC_INCOMPATIBLE_SESSION",
        "METRIC_UNKNOWN_AVAILABILITY",
        "METRIC_CONFLICTED_INPUT",
        "METRIC_CANCELLED_INPUT",
        "METRIC_PARTIAL_INPUT",
        "METRIC_INSUFFICIENT_HISTORY",
        "METRIC_ZERO_DENOMINATOR",
        "METRIC_MISSING_START_PRICE",
        "METRIC_MISSING_END_PRICE",
        "METRIC_MISSING_HIGH",
        "METRIC_MISSING_LOW",
        "METRIC_MISSING_VOLUME",
        "METRIC_ZERO_VOLUME_SAMPLE",
        "METRIC_EXCLUDED_CURRENT_BAR",
        "RETURN_START_BAR_NOT_FOUND",
        "RETURN_END_BAR_NOT_FOUND",
        "RETURN_PRICE_FIELD_UNAVAILABLE",
        "RETURN_IDENTICAL_INPUT_BAR",
        "GAP_PRIOR_SESSION_NOT_FOUND",
        "GAP_CURRENT_SESSION_NOT_FOUND",
        "GAP_PRIOR_CLOSE_UNAVAILABLE",
        "GAP_CURRENT_OPEN_UNAVAILABLE",
        "GAP_SESSION_DATE_MISMATCH",
        "GAP_NONADJACENT_SESSION_POLICY",
        "RANGE_PARTIAL_BAR_UNSUPPORTED",
        "RANGE_ZERO_DENOMINATOR",
        "VOLUME_BASELINE_WINDOW_EMPTY",
        "VOLUME_BASELINE_INSUFFICIENT_SAMPLES",
        "VOLUME_BASELINE_MIXED_UNITS",
        "VOLUME_BASELINE_CURRENT_BAR_EXCLUDED",
        # Phase 2B additions (docs/phase-2b-design.md Section 16) -- every code above is
        # unchanged in value and meaning.
        "NORMALIZED_METRIC_ZERO_BASELINE",
        "NORMALIZED_METRIC_ZERO_VARIANCE",
        "NORMALIZED_METRIC_INSUFFICIENT_HISTORY",
        "RELATIVE_VOLUME_TARGET_NOT_FOUND",
        "RELATIVE_VOLUME_TARGET_MISSING_VOLUME",
        "RELATIVE_VOLUME_BASELINE_UNAVAILABLE",
        "RELATIVE_VOLUME_BASELINE_ZERO",
        "VOLUME_DISTRIBUTION_WINDOW_EMPTY",
        "VOLUME_DISTRIBUTION_INSUFFICIENT_SAMPLES",
        "VOLUME_DISTRIBUTION_ZERO_VARIANCE",
        "RETURN_DISTRIBUTION_WINDOW_EMPTY",
        "RETURN_DISTRIBUTION_INSUFFICIENT_BARS",
        "RETURN_DISTRIBUTION_INSUFFICIENT_RETURNS",
        "RETURN_DISTRIBUTION_ZERO_VARIANCE",
        "RETURN_TARGET_NOT_FOUND",
        "RETURN_TARGET_EXCLUDED_FROM_BASELINE",
        # Phase 2C additions (docs/phase-2c-design.md Section 13) -- every code above is
        # unchanged in value and meaning.
        "PRESSURE_METRIC_NO_ELIGIBLE_INPUT",
        "PRESSURE_METRIC_AMBIGUOUS_PROVIDER",
        "PRESSURE_METRIC_CONFLICTED_INPUT",
        "PRESSURE_METRIC_START_AFTER_END",
        "PRESSURE_METRIC_IDENTICAL_INPUT",
        "SHORT_INTEREST_START_NOT_FOUND",
        "SHORT_INTEREST_END_NOT_FOUND",
        "SHORT_INTEREST_MISSING_VALUE",
        "SHORT_INTEREST_ZERO_START_DENOMINATOR",
        "SHORT_INTEREST_CANCELLED_INPUT",
        "SHORT_INTEREST_REVISION_NOT_FOUND",
        "SHORT_INTEREST_REVISION_LINK_MISSING",
        "DAYS_TO_COVER_SHORT_INTEREST_NOT_FOUND",
        "DAYS_TO_COVER_VOLUME_BASELINE_UNAVAILABLE",
        "DAYS_TO_COVER_ZERO_VOLUME_BASELINE",
        "DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL",
        "BORROW_FEE_START_NOT_FOUND",
        "BORROW_FEE_END_NOT_FOUND",
        "BORROW_FEE_MISSING_VALUE",
        "BORROW_FEE_ZERO_START_DENOMINATOR",
        "BORROW_AVAILABILITY_START_NOT_FOUND",
        "BORROW_AVAILABILITY_END_NOT_FOUND",
        "BORROW_AVAILABILITY_MISSING_VALUE",
        "BORROW_AVAILABILITY_ZERO_START_DENOMINATOR",
    }
    actual = {item.value for item in MetricDiagnosticCode}
    assert actual == expected


def test_sort_diagnostics_is_deterministic_regardless_of_input_order():
    a = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_PARTIAL_INPUT, severity="WARNING", message="a", observation_ids=("1",))
    b = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_CANCELLED_INPUT, severity="WARNING", message="b", observation_ids=("2",))
    c = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER, severity="ERROR", message="c")
    forward = sort_diagnostics([a, b, c])
    backward = sort_diagnostics([c, b, a])
    shuffled = sort_diagnostics([b, a, c])
    assert forward == backward == shuffled
    assert [item.code for item in forward] == sorted(item.code.value for item in (a, b, c))


def test_sort_diagnostics_breaks_ties_by_observation_ids_then_message():
    a = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_PARTIAL_INPUT, severity="WARNING", message="z", observation_ids=("1",))
    b = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_PARTIAL_INPUT, severity="WARNING", message="a", observation_ids=("1",))
    c = MetricDiagnostic(code=MetricDiagnosticCode.METRIC_PARTIAL_INPUT, severity="WARNING", message="a", observation_ids=("0",))
    result = sort_diagnostics([a, b, c])
    assert result == (c, b, a)


def test_diagnostic_rejects_unknown_code():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MetricDiagnostic(code="NOT_A_REAL_CODE", severity="INFO", message="x")
