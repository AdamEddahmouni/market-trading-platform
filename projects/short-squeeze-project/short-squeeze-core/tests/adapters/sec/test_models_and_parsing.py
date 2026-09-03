from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.sec import (
    DateOnlyAvailabilityPolicy,
    SecFilingRecord,
    SecParseError,
    parse_accession_number,
    parse_cik,
    parse_document_count,
    parse_form_type,
    parse_period_of_report,
    parse_public_availability,
    sanitize_primary_document,
)


def base_record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "testa-10q-original",
        "provider_schema": "SEC_FILING_V1",
        "record_type": "SEC_FILING",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "ticker": " testa ",
        "cik": "1",
        "form": "10-q",
        "accession_number": "0000000001-26-000001",
        "filed_date": "2026-01-20",
        "acceptance_datetime": "2026-01-20T14:30:00Z",
        "period_of_report": "2026-01-15",
        "primary_document": "testa-20260115x10q.htm",
    }
    value.update(overrides)
    return value


def test_provider_model_accepts_documented_aliases_and_normalizes_symbol() -> None:
    record = SecFilingRecord.model_validate(base_record())

    assert record.symbol == "TESTA"
    assert record.issuer_cik == "1"
    assert record.form_type == "10-q"
    assert record.accepted_at == "2026-01-20T14:30:00Z"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_schema", "SEC_FILING_V2"),
        ("record_type", "FILING_DOCUMENT"),
        ("fixture_origin", "RECORDED"),
    ],
)
def test_provider_model_rejects_unsupported_structure(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        SecFilingRecord.model_validate(base_record(**{field: value}))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0000000001", "0000000001"), ("1", "0000000001"), ("123456789", "0123456789")],
)
def test_cik_is_a_zero_padded_string(raw: str, expected: str) -> None:
    assert parse_cik(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "12A", "12345678901"])
def test_invalid_or_missing_cik_is_diagnosed(raw: str | None) -> None:
    with pytest.raises(SecParseError) as raised:
        parse_cik(raw)
    assert raised.value.code in {DiagnosticCode.SEC_MISSING_CIK, DiagnosticCode.SEC_INVALID_CIK}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0000000001-26-000001", "0000000001-26-000001"),
        ("000000000126000001", "0000000001-26-000001"),
    ],
)
def test_accession_normalization_is_unambiguous(raw: str, expected: str) -> None:
    assert parse_accession_number(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "0001-26-1", "0000000001-AA-000001", "00000000012600000"])
def test_invalid_or_missing_accession_is_rejected(raw: str | None) -> None:
    with pytest.raises(SecParseError) as raised:
        parse_accession_number(raw)
    assert raised.value.code in {
        DiagnosticCode.SEC_MISSING_ACCESSION,
        DiagnosticCode.SEC_INVALID_ACCESSION,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("10-q", "10-Q"), (" s-1/a ", "S-1/A"), ("DEF 14A", "DEF 14A")],
)
def test_form_type_is_conservatively_normalized(raw: str, expected: str) -> None:
    assert parse_form_type(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "10_Q", "../../8-K", "8-K?x=1"])
def test_missing_or_malformed_form_is_rejected(raw: str | None) -> None:
    with pytest.raises(SecParseError):
        parse_form_type(raw)


def test_period_count_and_primary_document_parsing() -> None:
    assert str(parse_period_of_report("2026-01-15")) == "2026-01-15"
    assert parse_period_of_report(None) is None
    assert parse_document_count("3") == 3
    assert parse_document_count(None) is None
    assert sanitize_primary_document("testa-10q.htm") == "testa-10q.htm"


@pytest.mark.parametrize("raw", ["-1", "1.5", "not-a-number"])
def test_invalid_document_count_is_rejected(raw: str) -> None:
    with pytest.raises(SecParseError) as raised:
        parse_document_count(raw)
    assert raised.value.code is DiagnosticCode.SEC_INVALID_DOCUMENT_COUNT


@pytest.mark.parametrize("raw", ["../secret.txt", "C:\\private\\filing.htm", "https://sec.invalid/x.htm", "a.htm?token=x"])
def test_primary_document_rejects_paths_urls_and_queries(raw: str) -> None:
    with pytest.raises(SecParseError) as raised:
        sanitize_primary_document(raw)
    assert raised.value.code is DiagnosticCode.SEC_REMOTE_URL_SANITIZED


def test_exact_publication_precedes_acceptance_as_availability() -> None:
    availability = parse_public_availability(
        published_at="2026-01-20T14:35:00Z",
        publication_timezone=None,
        accepted_at="2026-01-20T14:30:00Z",
        acceptance_timezone=None,
        date_only_policy=DateOnlyAvailabilityPolicy.STRICT_REJECT,
        received_at=datetime(2026, 1, 20, 15, tzinfo=UTC),
    )

    assert availability.timestamp == datetime(2026, 1, 20, 14, 35, tzinfo=UTC)
    assert availability.basis == "PUBLICATION_TIMESTAMP"
    assert not availability.uncertain


def test_exact_acceptance_is_fallback_public_availability() -> None:
    availability = parse_public_availability(
        published_at=None,
        publication_timezone=None,
        accepted_at="2026-01-20T09:30:00-05:00",
        acceptance_timezone=None,
        date_only_policy=DateOnlyAvailabilityPolicy.STRICT_REJECT,
        received_at=datetime(2026, 1, 20, 15, tzinfo=UTC),
    )
    assert availability.timestamp == datetime(2026, 1, 20, 14, 30, tzinfo=UTC)
    assert availability.basis == "SEC_ACCEPTANCE_TIMESTAMP"


def test_date_only_publication_uses_conservative_explicit_policy() -> None:
    availability = parse_public_availability(
        published_at="2026-01-20",
        publication_timezone="-05:00",
        accepted_at=None,
        acceptance_timezone=None,
        date_only_policy=DateOnlyAvailabilityPolicy.END_OF_DATE,
        received_at=datetime(2026, 1, 22, tzinfo=UTC),
    )
    assert availability.timestamp == datetime(2026, 1, 21, 5, tzinfo=UTC)
    assert availability.uncertain


def test_missing_or_capture_only_availability_is_rejected() -> None:
    with pytest.raises(SecParseError) as raised:
        parse_public_availability(
            published_at=None,
            publication_timezone=None,
            accepted_at=None,
            acceptance_timezone=None,
            date_only_policy=DateOnlyAvailabilityPolicy.STRICT_REJECT,
            received_at=datetime(2026, 1, 20, 15, tzinfo=UTC),
        )
    assert raised.value.code is DiagnosticCode.SEC_UNKNOWN_AVAILABILITY_TIME
