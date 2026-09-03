import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.contracts.enums import QualityState
from squeeze_core.validation import (
    OutcomeWindow,
    OutcomeWindowObservation,
    ValidationDiagnosticCode,
    build_outcome_observation,
    build_outcome_window,
    serialize_outcome_observation,
    unobserved_outcome,
)

REFERENCE = Decimal("10.00")
REF_TIME = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)

# No field in a retrospective observation may imply a simulated trade or a causal
# verdict. These are checked against serialized keys so a future field cannot slip in.
FORBIDDEN_KEY_SUBSTRINGS = (
    "pnl",
    "profit",
    "entry",
    "exit",
    "fill",
    "position",
    "stop_loss",
    "target",
    "return_on",
    "squeeze_confirmed",
    "recommend",
)


def _window(window, high, low, close, volume=1000):
    return build_outcome_window(
        window,
        reference_price=REFERENCE,
        window_end_time=REF_TIME,
        high_price=Decimal(high),
        low_price=Decimal(low),
        close_price=Decimal(close),
        volume=volume,
    )


def test_positive_subsequent_movement():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=REFERENCE, reference_price_time=REF_TIME,
    )
    assert result.maximum_observed_price == Decimal("13.00")
    assert result.maximum_observed_return_percent == Decimal("30")


def test_negative_subsequent_movement():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "10.10", "7.00", "7.50"),),
        reference_price=REFERENCE, reference_price_time=REF_TIME,
    )
    assert result.maximum_adverse_move_percent == Decimal("-30")


def test_flat_movement():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "10.00", "10.00", "10.00"),),
        reference_price=REFERENCE, reference_price_time=REF_TIME,
    )
    assert result.maximum_observed_return_percent == Decimal("0")
    assert result.maximum_adverse_move_percent == Decimal("0")


def test_maximum_and_minimum_span_every_observed_window():
    result = build_outcome_observation(
        "TEST",
        (
            _window(OutcomeWindow.MINUTES_15, "11.00", "9.50", "10.20"),
            _window(OutcomeWindow.HOUR_1, "14.00", "8.00", "13.00"),
        ),
        reference_price=REFERENCE, reference_price_time=REF_TIME,
    )
    assert result.maximum_observed_price == Decimal("14.00")
    assert result.minimum_observed_price == Decimal("8.00")


def test_time_to_maximum_is_carried_when_supplied():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=REFERENCE, time_to_maximum_seconds=1800,
    )
    assert result.time_to_maximum_seconds == 1800


def test_missing_window_is_reported_not_dropped_or_zeroed():
    missing = build_outcome_window(OutcomeWindow.NEXT_SESSION_CLOSE)
    assert missing.observed is False
    assert missing.close_price is None
    assert missing.return_percent is None
    assert missing.limitations


def test_missing_window_emits_the_incomplete_diagnostic():
    result = build_outcome_observation(
        "TEST",
        (
            _window(OutcomeWindow.HOUR_1, "11.00", "9.00", "10.50"),
            build_outcome_window(OutcomeWindow.NEXT_SESSION_CLOSE),
        ),
        reference_price=REFERENCE,
    )
    codes = {item.code for item in result.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_OUTCOME_DATA_INCOMPLETE in codes


def test_an_unobserved_window_cannot_carry_prices():
    with pytest.raises(ValidationError, match="unobserved window cannot carry"):
        OutcomeWindowObservation(
            window=OutcomeWindow.HOUR_1, observed=False, close_price=Decimal("10")
        )


def test_halt_events_are_recorded_separately_from_price():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=REFERENCE, halt_events=("LUDP volatility halt 14:02Z",),
    )
    assert result.halt_events == ("LUDP volatility halt 14:02Z",)


def test_no_halt_event_is_an_empty_tuple_not_a_claim():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=REFERENCE,
    )
    assert result.halt_events == ()


def test_detection_window_rather_than_exact_time_is_supported():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        detection_time_evidence_id="det-bounded", reference_price=REFERENCE,
    )
    assert result.detection_time_evidence_id == "det-bounded"


def test_causal_interpretation_is_never_inferred_from_price():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "30.00", "9.80", "29.00"),),
        reference_price=REFERENCE,
    )
    # A 190% move must not auto-populate a causal claim.
    assert result.causal_interpretation is None


def test_serialized_observation_has_no_trade_or_pnl_field():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=REFERENCE,
    )
    payload = json.loads(serialize_outcome_observation(result))
    keys = {key.lower() for key in payload}
    for forbidden in FORBIDDEN_KEY_SUBSTRINGS:
        assert not any(forbidden in key for key in keys), (
            f"outcome observation gained a {forbidden!r} key: {sorted(keys)}"
        )


def test_output_is_deterministic():
    args = ("TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),))
    first = build_outcome_observation(*args, reference_price=REFERENCE)
    second = build_outcome_observation(*args, reference_price=REFERENCE)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_outcome_observation(first) == serialize_outcome_observation(second)


def test_window_ordering_is_stable_under_permutation():
    windows = (
        _window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),
        _window(OutcomeWindow.MINUTES_15, "11.00", "9.90", "10.50"),
    )
    forward = build_outcome_observation("TEST", windows, reference_price=REFERENCE)
    reverse = build_outcome_observation("TEST", tuple(reversed(windows)), reference_price=REFERENCE)
    assert forward.deterministic_id == reverse.deterministic_id


def test_biya_style_unobserved_outcome_computes_nothing():
    result = unobserved_outcome("BIYA", detection_time_evidence_id="det-biya")
    assert len(result.subsequent_windows) == len(list(OutcomeWindow))
    assert all(not window.observed for window in result.subsequent_windows)
    assert result.maximum_observed_price is None
    assert result.maximum_observed_return_percent is None
    assert result.minimum_observed_price is None
    assert result.quality.state is QualityState.MISSING
    codes = {item.code for item in result.diagnostics}
    assert codes == {ValidationDiagnosticCode.VALIDATION_OUTCOME_DATA_INCOMPLETE}


def test_zero_reference_price_does_not_raise():
    result = build_outcome_observation(
        "TEST", (_window(OutcomeWindow.HOUR_1, "13.00", "9.80", "12.50"),),
        reference_price=Decimal("0"),
    )
    assert result.maximum_observed_return_percent is None
