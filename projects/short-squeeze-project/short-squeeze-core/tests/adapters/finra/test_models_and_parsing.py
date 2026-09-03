from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.adapters import DiagnosticCode
from squeeze_core.adapters.finra import (
    DateOnlyPublicationPolicy,
    FinraParseError,
    FinraShortInterestRecord,
    PercentageUnit,
    RevisionStatus,
    parse_nonnegative_decimal,
    parse_nonnegative_integer,
    parse_percentage,
    parse_publication_availability,
    parse_settlement_date,
)
from squeeze_core.serialization import canonical_hash


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "finra-representative-001",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "Symbol": "testa",
        "Short Shares": "2500000",
        "Settlement Date": "2026-01-15",
        "Publication Date": "2026-01-22T14:00:00-05:00",
        "short_float_percent": "12.5%",
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING",
        "record_status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def test_record_accepts_narrow_representative_aliases_and_normalizes_identity() -> None:
    parsed = FinraShortInterestRecord.model_validate(record())

    assert parsed.symbol == "TESTA"
    assert parsed.short_shares == "2500000"
    assert parsed.settlement_date == "2026-01-15"
    assert parsed.publication_date == "2026-01-22T14:00:00-05:00"
    assert parsed.revision_status is RevisionStatus.ORIGINAL


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_schema", "FINRA_V2"),
        ("record_type", "DAILY_SHORT_VOLUME"),
        ("fixture_origin", "RECORDED"),
    ],
)
def test_record_rejects_unsupported_schema_type_and_origin(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        FinraShortInterestRecord.model_validate(record(**{field: value}))


def test_record_rejects_unknown_alias_and_raw_hash_uses_exact_input_shape() -> None:
    raw = record()
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FinraShortInterestRecord.model_validate({**raw, "Mystery": "value"})

    assert canonical_hash(raw) == canonical_hash(dict(raw))
    assert canonical_hash(raw) != canonical_hash({**raw, "Symbol": "TESTA"})


@pytest.mark.parametrize("raw", [0, "0", 25, "2500000", Decimal("12")])
def test_nonnegative_integer_is_exact(raw: object) -> None:
    assert parse_nonnegative_integer(raw, "short_shares") == int(Decimal(str(raw)))


@pytest.mark.parametrize("raw", [-1, "1.5", True, "1,000", "NaN", "shares"])
def test_nonnegative_integer_rejects_invalid_formats(raw: object) -> None:
    with pytest.raises(FinraParseError) as captured:
        parse_nonnegative_integer(raw, "short_shares")
    assert captured.value.code is DiagnosticCode.FINRA_INVALID_SHORT_SHARES


def test_missing_integer_and_explicit_zero_are_distinct() -> None:
    assert parse_nonnegative_integer(None, "short_shares") is None
    assert parse_nonnegative_integer("0", "short_shares") == 0


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        ("12.5", PercentageUnit.PERCENT_POINTS, Decimal("12.5")),
        ("0.125", PercentageUnit.DECIMAL_FRACTION, Decimal("12.5")),
        ("12.5%", PercentageUnit.FORMATTED_PERCENT_STRING, Decimal("12.5")),
        ("0%", PercentageUnit.FORMATTED_PERCENT_STRING, Decimal("0")),
    ],
)
def test_percentage_scaling_requires_explicit_units(
    raw: object, unit: PercentageUnit, expected: Decimal
) -> None:
    assert parse_percentage(raw, unit) == expected


@pytest.mark.parametrize(
    ("raw", "unit"),
    [("12.5", None), ("12.5%", PercentageUnit.PERCENT_POINTS), ("-1", PercentageUnit.PERCENT_POINTS)],
)
def test_percentage_rejects_absent_mismatched_or_negative_units(
    raw: object, unit: PercentageUnit | None
) -> None:
    with pytest.raises(FinraParseError):
        parse_percentage(raw, unit)


def test_days_to_cover_decimal_preserves_zero_missing_and_precision() -> None:
    assert parse_nonnegative_decimal(None, "days_to_cover") is None
    assert parse_nonnegative_decimal("0", "days_to_cover") == 0
    assert parse_nonnegative_decimal("2.750", "days_to_cover") == Decimal("2.750")
    with pytest.raises(FinraParseError):
        parse_nonnegative_decimal("-0.1", "days_to_cover")


def test_settlement_date_is_date_only_and_required_when_parsed() -> None:
    assert parse_settlement_date("2026-01-15") == date(2026, 1, 15)
    with pytest.raises(FinraParseError) as captured:
        parse_settlement_date(None)
    assert captured.value.code is DiagnosticCode.FINRA_MISSING_SETTLEMENT_DATE
    with pytest.raises(FinraParseError):
        parse_settlement_date("2026-01-15T12:00:00Z")


def test_full_publication_timestamp_preserves_timezone_and_normalizes_to_utc() -> None:
    result = parse_publication_availability(
        "2026-01-22T14:00:00-05:00",
        timezone_name=None,
        policy=DateOnlyPublicationPolicy.STRICT_REJECT,
        received_at=datetime(2026, 1, 22, 20, tzinfo=UTC),
    )

    assert result.timestamp == datetime(2026, 1, 22, 19, tzinfo=UTC)
    assert result.publication_date == date(2026, 1, 22)
    assert result.uncertain is False


def test_naive_publication_timestamp_requires_explicit_timezone() -> None:
    with pytest.raises(FinraParseError) as captured:
        parse_publication_availability(
            "2026-01-22T14:00:00",
            timezone_name=None,
            policy=DateOnlyPublicationPolicy.STRICT_REJECT,
            received_at=datetime(2026, 1, 22, 20, tzinfo=UTC),
        )
    assert captured.value.code is DiagnosticCode.FINRA_UNKNOWN_PUBLICATION_TIMEZONE


def test_date_only_publication_supports_strict_end_of_day_and_uncertain_policies() -> None:
    received = datetime(2026, 1, 23, 15, tzinfo=UTC)
    with pytest.raises(FinraParseError) as captured:
        parse_publication_availability(
            "2026-01-22",
            timezone_name="-05:00",
            policy=DateOnlyPublicationPolicy.STRICT_REJECT,
            received_at=received,
        )
    assert captured.value.code is DiagnosticCode.FINRA_DATE_ONLY_PUBLICATION

    conservative = parse_publication_availability(
        "2026-01-22",
        timezone_name="-05:00",
        policy=DateOnlyPublicationPolicy.END_OF_PUBLICATION_DATE,
        received_at=received,
    )
    assert conservative.timestamp == datetime(2026, 1, 23, 5, tzinfo=UTC)
    assert conservative.uncertain is True

    placeholder = parse_publication_availability(
        "2026-01-22",
        timezone_name=None,
        policy=DateOnlyPublicationPolicy.INGESTION_TIME_UNCERTAIN_PLACEHOLDER,
        received_at=received,
    )
    assert placeholder.timestamp == received
    assert placeholder.uncertain is True


def test_missing_publication_and_unknown_timezone_are_not_fabricated() -> None:
    received = datetime(2026, 1, 23, 15, tzinfo=UTC)
    with pytest.raises(FinraParseError) as missing:
        parse_publication_availability(
            None,
            timezone_name=None,
            policy=DateOnlyPublicationPolicy.STRICT_REJECT,
            received_at=received,
        )
    assert missing.value.code is DiagnosticCode.FINRA_MISSING_PUBLICATION_DATE

    with pytest.raises(FinraParseError) as timezone:
        parse_publication_availability(
            "2026-01-22",
            timezone_name="Unknown/Zone",
            policy=DateOnlyPublicationPolicy.END_OF_PUBLICATION_DATE,
            received_at=received,
        )
    assert timezone.value.code is DiagnosticCode.FINRA_UNKNOWN_PUBLICATION_TIMEZONE
