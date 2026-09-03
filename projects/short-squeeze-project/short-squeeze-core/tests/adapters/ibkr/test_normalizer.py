from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters import AdapterContext, DiagnosticCode
from squeeze_core.adapters.ibkr import (
    IbkrBorrowRecord,
    normalize_ibkr_borrow_record,
    normalize_ibkr_borrow_records,
)
from squeeze_core.contracts import (
    DataFreshness,
    EntitlementState,
    EventType,
    IngestionMethod,
    ObservationKind,
    QualityState,
    ReplayMode,
)
from squeeze_core.replay import ReplayEngine
from squeeze_core.serialization import canonical_hash, serialize_jsonl, serialize_observation


def context(*, timezone: str | None = "-05:00") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime(2026, 1, 2, 15, 5, tzinfo=UTC),
        source_timezone=timezone,
        provider="INTERACTIVE_BROKERS",
        adapter_version="ibkr-offline-v1",
        normalization_version="ibkr-normalization-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        expected_delay_ms=900_000,
        source_endpoint_name="short-stock-file-shape",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "ibkr-representative-001",
        "symbol": "TESTA",
        "fee_rate": "0.325",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "12000",
        "lender_count": "3",
        "hard_to_borrow": True,
        "provider_timestamp": "2026-01-02T09:45:00",
        "provider_timezone": "-05:00",
        "delay_status": "KNOWN_DELAYED",
    }
    value.update(overrides)
    return value


def by_type(result, event_type: EventType):
    return next(item for item in result.observations if item.event_type is event_type)


def codes(result) -> set[DiagnosticCode]:
    return {item.code for item in result.diagnostics}


def test_complete_record_produces_separate_canonical_observations() -> None:
    result = normalize_ibkr_borrow_record(record(), context())

    assert result.accepted is True
    assert [item.event_type for item in result.observations] == [
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
    ]
    fee = by_type(result, EventType.BORROW_FEE)
    availability = by_type(result, EventType.BORROW_AVAILABILITY)
    assert fee.payload.annualized_fee_percent == Decimal("0.325")
    assert availability.payload.available_shares == 12000
    assert availability.payload.lender_count == 3
    assert availability.payload.hard_to_borrow is True
    assert fee.observation_kind is ObservationKind.PROVIDER_PUBLISHED
    assert fee.source_timestamp == datetime(2026, 1, 2, 14, 45, tzinfo=UTC)
    assert fee.received_timestamp == context().ingested_at
    assert fee.data_freshness is DataFreshness.DELAYED
    assert fee.quality.state is QualityState.DELAYED
    assert fee.raw_payload_hash == canonical_hash(IbkrBorrowRecord.model_validate(record()))
    assert fee.provenance.provider_metadata["adapter_version"] == "ibkr-offline-v1"
    assert fee.normalization_version == "ibkr-normalization-v1"
    assert ObservationKind.PROVIDER_PUBLISHED is fee.provenance.origin_kind


def test_same_record_and_context_are_byte_identical_and_replayable() -> None:
    first = normalize_ibkr_borrow_record(record(), context())
    second = normalize_ibkr_borrow_record(record(), context())

    assert serialize_jsonl(first.observations) == serialize_jsonl(second.observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(first.observations)
    assert replay.to_bytes() == ReplayEngine(mode=ReplayMode.STRICT).replay(second.observations).to_bytes()


def test_raw_hash_preserves_the_exact_sanitized_input_shape() -> None:
    sparse_record = {
        "source_record_id": "sparse-record",
        "symbol": "TESTA",
        "fee_rate": "1",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "10",
        "provider_timestamp": "2026-01-02T09:45:00-05:00",
    }

    result = normalize_ibkr_borrow_record(sparse_record, context())

    assert all(item.raw_payload_hash == canonical_hash(sparse_record) for item in result.observations)


def test_explicit_zero_and_missing_values_remain_distinct() -> None:
    zero = normalize_ibkr_borrow_record(
        record(fee_rate="0", available_shares="0", delay_status="NOT_DELAYED"), context()
    )
    missing = normalize_ibkr_borrow_record(
        record(
            source_record_id="ibkr-representative-002",
            fee_rate=None,
            available_shares=None,
            delay_status="NOT_DELAYED",
        ),
        context(),
    )

    zero_fee = by_type(zero, EventType.BORROW_FEE)
    missing_fee = by_type(missing, EventType.BORROW_FEE)
    zero_availability = by_type(zero, EventType.BORROW_AVAILABILITY)
    missing_availability = by_type(missing, EventType.BORROW_AVAILABILITY)
    assert zero_fee.payload.annualized_fee_percent == 0
    assert zero_fee.quality.state is QualityState.KNOWN_VALUE
    assert missing_fee.payload.annualized_fee_percent is None
    assert missing_fee.quality.state is QualityState.MISSING
    assert zero_availability.payload.available_shares == 0
    assert zero_availability.quality.state is QualityState.KNOWN_VALUE
    assert missing_availability.payload.available_shares is None
    assert missing_availability.quality.state is QualityState.MISSING
    assert DiagnosticCode.EXPLICIT_ZERO_BORROW_FEE in codes(zero)
    assert DiagnosticCode.EXPLICIT_ZERO_AVAILABLE_SHARES in codes(zero)
    assert DiagnosticCode.MISSING_BORROW_FEE in codes(missing)
    assert DiagnosticCode.MISSING_AVAILABLE_SHARES in codes(missing)
    assert serialize_observation(zero_fee) != serialize_observation(missing_fee)


def test_percent_scaling_is_explicit_and_never_magnitude_inferred() -> None:
    percent_points = normalize_ibkr_borrow_record(record(), context())
    fraction = normalize_ibkr_borrow_record(
        record(source_record_id="fraction", fee_rate_unit="DECIMAL_FRACTION"), context()
    )

    assert by_type(percent_points, EventType.BORROW_FEE).payload.annualized_fee_percent == Decimal(
        "0.325"
    )
    assert by_type(fraction, EventType.BORROW_FEE).payload.annualized_fee_percent == Decimal("32.5")


def test_unsupported_unit_and_invalid_fee_preserve_valid_availability_as_partial_result() -> None:
    unsupported = normalize_ibkr_borrow_record(record(fee_rate_unit="BASIS_POINTS"), context())
    negative = normalize_ibkr_borrow_record(record(fee_rate="-1"), context())
    nonnumeric = normalize_ibkr_borrow_record(record(fee_rate="not-a-number"), context())

    for result in (unsupported, negative, nonnumeric):
        assert [item.event_type for item in result.observations] == [EventType.BORROW_AVAILABILITY]
        assert DiagnosticCode.PARTIAL_RECORD in codes(result)
    assert DiagnosticCode.UNSUPPORTED_PERCENT_UNIT in codes(unsupported)
    assert DiagnosticCode.INVALID_NUMERIC_VALUE in codes(negative)
    assert DiagnosticCode.INVALID_NUMERIC_VALUE in codes(nonnumeric)


def test_invalid_availability_does_not_become_zero_and_preserves_fee() -> None:
    for invalid in ("-1", "1.5", "not-a-number"):
        result = normalize_ibkr_borrow_record(record(available_shares=invalid), context())
        assert [item.event_type for item in result.observations] == [EventType.BORROW_FEE]
        assert DiagnosticCode.INVALID_NUMERIC_VALUE in codes(result)
        assert DiagnosticCode.PARTIAL_RECORD in codes(result)


def test_timestamp_with_offset_and_date_only_timestamp_are_explicit() -> None:
    offset = normalize_ibkr_borrow_record(
        record(provider_timestamp="2026-01-02T09:45:00-05:00", provider_timezone=None), context()
    )
    date_only = normalize_ibkr_borrow_record(
        record(source_record_id="date-only", provider_timestamp="2026-01-02"), context()
    )

    assert offset.observations[0].source_timestamp == datetime(2026, 1, 2, 14, 45, tzinfo=UTC)
    assert date_only.observations[0].source_timestamp == datetime(2026, 1, 2, 5, 0, tzinfo=UTC)
    assert DiagnosticCode.DATE_ONLY_PROVIDER_TIMESTAMP in codes(date_only)


def test_unknown_timezone_is_rejected_and_never_assigned() -> None:
    result = normalize_ibkr_borrow_record(
        record(provider_timezone=None), context(timezone=None)
    )

    assert result.accepted is False
    assert result.observations == ()
    assert result.rejection is not None
    assert result.rejection.code is DiagnosticCode.UNKNOWN_TIMEZONE
    assert DiagnosticCode.UNKNOWN_TIMEZONE in codes(result)


def test_missing_timestamp_continues_with_explicit_uncertainty() -> None:
    result = normalize_ibkr_borrow_record(record(provider_timestamp=None), context())

    assert DiagnosticCode.MISSING_PROVIDER_TIMESTAMP in codes(result)
    assert all(item.source_timestamp == context().ingested_at for item in result.observations)
    assert all(item.quality.state is QualityState.MISSING for item in result.observations)
    assert all(item.provenance.source_timestamp_representation is None for item in result.observations)


def test_unknown_delay_and_entitlement_generate_diagnostics() -> None:
    result = normalize_ibkr_borrow_record(record(delay_status="UNKNOWN"), context())

    assert DiagnosticCode.DELAY_STATUS_UNKNOWN in codes(result)
    assert DiagnosticCode.ENTITLEMENT_UNKNOWN in codes(result)
    assert all(item.data_freshness is DataFreshness.UNKNOWN for item in result.observations)


def test_batch_detects_duplicate_source_records_without_double_emission() -> None:
    result = normalize_ibkr_borrow_records([record(), record()], context())

    assert len(result.observations) == 2
    assert DiagnosticCode.DUPLICATE_SOURCE_RECORD in codes(result)


def test_batch_preserves_conflicting_records_and_marks_both_conflicted() -> None:
    result = normalize_ibkr_borrow_records(
        [record(), record(source_record_id="ibkr-representative-conflict", fee_rate="9.5")],
        context(),
    )

    fee_observations = [item for item in result.observations if item.event_type is EventType.BORROW_FEE]
    assert len(fee_observations) == 2
    assert {item.payload.annualized_fee_percent for item in fee_observations} == {
        Decimal("0.325"),
        Decimal("9.5"),
    }
    assert all(item.quality.state is QualityState.CONFLICTED for item in fee_observations)
    assert len({item.correlation_id for item in fee_observations}) == 1
    assert DiagnosticCode.CONFLICTING_SOURCE_RECORD in codes(result)
