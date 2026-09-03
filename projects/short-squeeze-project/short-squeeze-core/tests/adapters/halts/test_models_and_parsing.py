from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.halts import (
    HaltLifecycleStatus,
    HaltParseError,
    TradingHaltRecord,
    halt_event_key,
    parse_halt_code,
    parse_halt_timestamp,
    parse_public_availability,
    parse_session_date,
)


def base_record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "testa-halt-001",
        "provider_schema": "TRADING_HALT_V1",
        "record_type": "TRADING_HALT",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "ticker": " testa ",
        "market": " xtest ",
        "provider_halt_id": "halt-001",
        "reason_code": " t1 ",
        "reason": "News pending",
        "announcement_datetime": "2026-01-15T10:01:00-05:00",
        "halt_datetime": "10:00:00",
        "session_date": "2026-01-15",
        "timezone": "-05:00",
        "published_at": "2026-01-15T15:01:00Z",
        "record_status": "HALT_ACTIVE",
    }
    value.update(overrides)
    return value


def test_model_accepts_aliases_and_normalizes_identity() -> None:
    record = TradingHaltRecord.model_validate(base_record())

    assert record.symbol == "TESTA"
    assert record.exchange == "XTEST"
    assert record.halt_code == " t1 "
    assert record.status is HaltLifecycleStatus.HALT_ACTIVE


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_schema", "TRADING_HALT_V2"),
        ("record_type", "MARKET_STATUS"),
        ("fixture_origin", "RECORDED"),
        ("ticker", "bad symbol"),
    ],
)
def test_model_rejects_unsupported_structure(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TradingHaltRecord.model_validate(base_record(**{field: value}))


def test_code_and_session_date_parsing_are_conservative() -> None:
    assert parse_halt_code(" t1 ") == "T1"
    assert parse_halt_code(None) is None
    assert parse_session_date("2026-01-15").isoformat() == "2026-01-15"


@pytest.mark.parametrize("raw", ["", "bad code", "T1/BUY"])
def test_invalid_halt_code_rejects(raw: str) -> None:
    with pytest.raises(HaltParseError) as raised:
        parse_halt_code(raw)
    assert raised.value.code is DiagnosticCode.HALT_UNKNOWN_CODE


def test_exact_and_time_only_timestamps_normalize_to_utc() -> None:
    exact = parse_halt_timestamp(
        "2026-01-15T10:00:00-05:00",
        session_date=None,
        timezone_name=None,
        field="halt_at",
    )
    time_only = parse_halt_timestamp(
        "10:00:00",
        session_date=parse_session_date("2026-01-15"),
        timezone_name="-05:00",
        field="halt_at",
    )
    assert exact.timestamp == datetime(2026, 1, 15, 15, tzinfo=UTC)
    assert time_only.timestamp == exact.timestamp
    assert time_only.time_only


@pytest.mark.parametrize(
    ("raw", "session", "timezone_name", "code"),
    [
        ("10:00:00", None, "America/New_York", DiagnosticCode.HALT_TIME_ONLY_VALUE),
        ("10:00:00", "2026-01-15", None, DiagnosticCode.HALT_UNKNOWN_TIMEZONE),
        ("2026-01-15T10:00:00", None, None, DiagnosticCode.HALT_UNKNOWN_TIMEZONE),
        ("not-a-time", None, None, DiagnosticCode.INVALID_NUMERIC_VALUE),
        ("2026-01-15", None, None, DiagnosticCode.HALT_DATE_ONLY_VALUE),
    ],
)
def test_ambiguous_timestamps_reject(
    raw: str,
    session: str | None,
    timezone_name: str | None,
    code: DiagnosticCode,
) -> None:
    with pytest.raises(HaltParseError) as raised:
        parse_halt_timestamp(
            raw,
            session_date=None if session is None else parse_session_date(session),
            timezone_name=timezone_name,
            field="halt_at",
        )
    assert raised.value.code is code


def test_publication_precedes_announcement_and_capture_is_not_availability() -> None:
    availability = parse_public_availability(
        publication_at="2026-01-15T15:02:00Z",
        announcement_at="2026-01-15T15:01:00Z",
        timezone_name=None,
    )
    assert availability.timestamp == datetime(2026, 1, 15, 15, 2, tzinfo=UTC)
    assert availability.basis == "PUBLICATION_TIMESTAMP"

    with pytest.raises(HaltParseError) as raised:
        parse_public_availability(
            publication_at=None,
            announcement_at=None,
            timezone_name="America/New_York",
        )
    assert raised.value.code is DiagnosticCode.HALT_MISSING_ANNOUNCEMENT_TIMESTAMP


def test_event_key_prefers_provider_halt_id_and_never_uses_session_alone() -> None:
    assert halt_event_key(
        symbol="TESTA",
        exchange="XTEST",
        provider_halt_id="halt-001",
        session_date=parse_session_date("2026-01-15"),
        halt_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
    ) == "provider:halt-001"
    first = halt_event_key(
        symbol="TESTA",
        exchange="XTEST",
        provider_halt_id=None,
        session_date=parse_session_date("2026-01-15"),
        halt_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    second = halt_event_key(
        symbol="TESTA",
        exchange="XTEST",
        provider_halt_id=None,
        session_date=parse_session_date("2026-01-15"),
        halt_at=datetime(2026, 1, 15, 16, tzinfo=UTC),
    )
    assert first != second
