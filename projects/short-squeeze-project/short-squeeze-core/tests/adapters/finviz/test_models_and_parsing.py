from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.adapters import DiagnosticCode
from squeeze_core.adapters.finviz import (
    EarningsSession,
    FinvizParseError,
    FinvizSnapshotRecord,
    PercentageUnit,
    parse_earnings,
    parse_percentage,
    parse_price,
    parse_quantity,
    parse_ratio,
)
from squeeze_core.serialization import canonical_hash


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "finviz-representative-001",
        "provider_schema": "FINVIZ_SCREENER_V1",
        "record_type": "CANDIDATE_SNAPSHOT",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "Ticker": "testa",
        "Price": "5.25",
        "Prev Close": "4.75",
        "Change": "10.5%",
        "change_percent_unit": "FORMATTED_PERCENT_STRING",
        "Volume": "125K",
        "Avg Volume": "25K",
        "Relative Volume": "5.0",
        "Shares Float": "8M",
        "Short Float": "12.5%",
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING",
    }
    value.update(overrides)
    return value


def test_record_accepts_only_evidence_backed_aliases_and_normalizes_symbol() -> None:
    parsed = FinvizSnapshotRecord.model_validate(record())

    assert parsed.symbol == "TESTA"
    assert parsed.price == "5.25"
    assert parsed.previous_close == "4.75"
    assert parsed.relative_volume == "5.0"
    assert parsed.float_shares == "8M"


def test_record_rejects_unknown_alias_schema_type_and_fixture_origin() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FinvizSnapshotRecord.model_validate(record(**{"Mystery Column": "value"}))
    with pytest.raises(ValidationError, match="FINVIZ_SCREENER_V1"):
        FinvizSnapshotRecord.model_validate(record(provider_schema="V2"))
    with pytest.raises(ValidationError, match="CANDIDATE_SNAPSHOT"):
        FinvizSnapshotRecord.model_validate(record(record_type="TRADE"))
    with pytest.raises(ValidationError, match="fixture_origin"):
        FinvizSnapshotRecord.model_validate(record(fixture_origin="SANITIZED_RECORDED_SAMPLE"))


def test_raw_record_hash_preserves_exact_alias_shape() -> None:
    raw = record()
    canonicalized = {**raw, "Ticker": "TESTA"}

    assert canonical_hash(raw) == canonical_hash(dict(raw))
    assert canonical_hash(raw) != canonical_hash(canonicalized)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(5, Decimal("5")), (Decimal("5.125"), Decimal("5.125")), ("5.125", Decimal("5.125"))],
)
def test_price_parsing_uses_decimal(raw: object, expected: Decimal) -> None:
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw", [-1, "not-a-price", "1,234.50", "$5.00"])
def test_price_rejects_negative_non_numeric_and_ambiguous_formats(raw: object) -> None:
    with pytest.raises(FinvizParseError) as captured:
        parse_price(raw)
    assert captured.value.code is DiagnosticCode.FINVIZ_INVALID_PRICE


def test_missing_and_zero_price_remain_distinct() -> None:
    assert parse_price(None) is None
    assert parse_price("0") == 0


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        ("12.5%", PercentageUnit.FORMATTED_PERCENT_STRING, Decimal("12.5")),
        ("12.5", PercentageUnit.PERCENT_POINTS, Decimal("12.5")),
        ("0.125", PercentageUnit.DECIMAL_FRACTION, Decimal("12.5")),
        ("-2.5%", PercentageUnit.FORMATTED_PERCENT_STRING, Decimal("-2.5")),
    ],
)
def test_percentage_scaling_is_explicit(raw: object, unit: PercentageUnit, expected: Decimal) -> None:
    assert parse_percentage(raw, unit, allow_negative=True) == expected


def test_percentage_zero_missing_malformed_and_unsupported_unit() -> None:
    assert parse_percentage("0%", PercentageUnit.FORMATTED_PERCENT_STRING) == 0
    assert parse_percentage(None, PercentageUnit.PERCENT_POINTS) is None
    with pytest.raises(FinvizParseError):
        parse_percentage("12.5", PercentageUnit.FORMATTED_PERCENT_STRING)
    with pytest.raises(FinvizParseError) as captured:
        parse_percentage("12.5", "BASIS_POINTS")
    assert captured.value.code is DiagnosticCode.FINVIZ_UNSUPPORTED_PERCENT_UNIT


@pytest.mark.parametrize(
    ("raw", "expected", "approximate"),
    [
        (125, 125, False),
        (Decimal("125"), 125, False),
        ("12.5K", 12500, True),
        ("3.2m", 3200000, True),
        ("1.4B", 1400000000, True),
        ("0.002T", 2000000000, True),
    ],
)
def test_quantity_parsing_uses_decimal_si_multipliers(
    raw: object, expected: int, approximate: bool
) -> None:
    parsed = parse_quantity(raw)
    assert parsed.value == expected
    assert parsed.approximate is approximate


@pytest.mark.parametrize("raw", ["1Q", "1.25", -1, "not-a-quantity"])
def test_quantity_rejects_unsupported_fractional_negative_and_malformed_values(raw: object) -> None:
    with pytest.raises(FinvizParseError):
        parse_quantity(raw)


def test_quantity_missing_and_explicit_zero_remain_distinct() -> None:
    assert parse_quantity(None).value is None
    assert parse_quantity("0").value == 0


def test_relative_volume_is_provider_ratio_and_not_recalculated() -> None:
    assert parse_ratio("5.0") == Decimal("5.0")
    assert parse_ratio(0) == 0
    assert parse_ratio(None) is None
    with pytest.raises(FinvizParseError):
        parse_ratio("invalid")


@pytest.mark.parametrize(
    ("raw", "expected_date", "expected_session"),
    [
        ("2026-02-02", date(2026, 2, 2), EarningsSession.UNKNOWN),
        ("2026-02-02 BMO", date(2026, 2, 2), EarningsSession.BEFORE_MARKET),
        ("2026-02-02 AMC", date(2026, 2, 2), EarningsSession.AFTER_MARKET),
        ("-", None, None),
        (None, None, None),
    ],
)
def test_earnings_parsing_preserves_date_precision_and_session(
    raw: object, expected_date: date | None, expected_session: EarningsSession | None
) -> None:
    parsed = parse_earnings(raw)
    assert parsed.earnings_date == expected_date
    assert parsed.session == expected_session


def test_earnings_ambiguous_text_is_rejected_without_inventing_time() -> None:
    with pytest.raises(FinvizParseError) as captured:
        parse_earnings("Next week")
    assert captured.value.code is DiagnosticCode.FINVIZ_AMBIGUOUS_EARNINGS_VALUE
