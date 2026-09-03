from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from squeeze_core.adapters import AdapterContext, DiagnosticCode
from squeeze_core.adapters.finra import (
    normalize_finra_short_interest_record,
    normalize_finra_short_interest_records,
)
from squeeze_core.contracts import (
    DataFreshness,
    EntitlementState,
    EventType,
    IngestionMethod,
    PayloadType,
    PublishedShortInterestPayload,
    QualityState,
)
from squeeze_core.serialization import canonical_hash


def context(ingested_at: str = "2026-01-22T20:00:00Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(ingested_at.replace("Z", "+00:00")),
        source_timezone=None,
        provider="finra-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="finra-short-interest-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="representative-short-interest-file",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "finra-original-001",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "symbol": "TESTA",
        "short_shares": "2500000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-22T14:00:00-05:00",
        "previous_short_shares": "2250000",
        "average_daily_volume": "1000000",
        "average_daily_volume_reference": "provider-defined trailing average",
        "days_to_cover": "2.5",
        "float_shares": "20000000",
        "short_float_percent": "12.5%",
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING",
        "market": "US EQUITY",
        "exchange": "TESTX",
        "revision_status": "ORIGINAL",
        "revision_number": 0,
        "provider_record_id": "provider-row-001",
        "provider_timestamp": "2026-01-22T14:05:00-05:00",
        "capture_timestamp": "2026-01-22T19:30:00Z",
    }
    value.update(overrides)
    return value


def diagnostic_codes(result) -> tuple[DiagnosticCode, ...]:
    return tuple(item.code for item in result.diagnostics)


def test_complete_record_emits_one_canonical_published_short_interest_observation() -> None:
    raw = record()
    result = normalize_finra_short_interest_record(raw, context())

    assert result.accepted is True
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.event_type is EventType.PUBLISHED_SHORT_INTEREST
    assert observation.payload_type is PayloadType.PUBLISHED_SHORT_INTEREST
    assert observation.source_timestamp == datetime(2026, 1, 22, 19, tzinfo=UTC)
    assert observation.received_timestamp == datetime(2026, 1, 22, 20, tzinfo=UTC)
    assert observation.effective_timestamp == datetime(2026, 1, 22, 20, tzinfo=UTC)
    assert observation.data_freshness is DataFreshness.HISTORICAL
    assert observation.quality.state is QualityState.KNOWN_VALUE
    assert observation.payload == PublishedShortInterestPayload(
        short_shares=2500000,
        float_shares=20000000,
        short_float_percent=Decimal("12.5"),
        settlement_date=date(2026, 1, 15),
        publication_date=date(2026, 1, 22),
        days_to_cover=Decimal("2.5"),
    )
    assert observation.raw_payload_hash == canonical_hash(raw)
    assert observation.provenance.provider_metadata["revision_status"] == "ORIGINAL"
    assert observation.provenance.provider_metadata["previous_short_shares"] == 2250000
    assert observation.provenance.provider_metadata["average_daily_volume"] == 1000000
    assert observation.normalization_version == "finra-short-interest-v1"


def test_missing_short_shares_is_partial_and_not_zero() -> None:
    result = normalize_finra_short_interest_record(record(short_shares=None), context())

    assert result.accepted is True
    assert result.observations[0].payload.short_shares is None
    assert result.observations[0].quality.state is QualityState.MISSING
    assert DiagnosticCode.FINRA_MISSING_SHORT_SHARES in diagnostic_codes(result)
    assert DiagnosticCode.FINRA_PARTIAL_RECORD in diagnostic_codes(result)


def test_explicit_zero_short_shares_and_days_to_cover_are_known_values() -> None:
    result = normalize_finra_short_interest_record(
        record(short_shares="0", days_to_cover="0"), context()
    )

    assert result.observations[0].payload.short_shares == 0
    assert result.observations[0].payload.days_to_cover == 0
    assert result.observations[0].quality.state is QualityState.KNOWN_VALUE


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"settlement_date": None}, DiagnosticCode.FINRA_MISSING_SETTLEMENT_DATE),
        ({"settlement_date": "bad"}, DiagnosticCode.FINRA_INVALID_SETTLEMENT_DATE),
        (
            {"publication_date": None, "capture_timestamp": None},
            DiagnosticCode.FINRA_MISSING_PUBLICATION_DATE,
        ),
        (
            {"publication_date": None, "capture_timestamp": "2026-01-22T19:00:00Z"},
            DiagnosticCode.FINRA_CAPTURE_TIMESTAMP_ONLY,
        ),
    ],
)
def test_ambiguous_required_date_semantics_reject(
    overrides: dict[str, object], code: DiagnosticCode
) -> None:
    result = normalize_finra_short_interest_record(record(**overrides), context())

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.code is code
    assert result.observations == ()


def test_provider_timestamp_can_explicitly_supply_missing_publication_availability() -> None:
    result = normalize_finra_short_interest_record(
        record(
            publication_date=None,
            provider_timestamp="2026-01-22T19:00:00Z",
            provider_timestamp_is_publication=True,
        ),
        context(),
    )

    assert result.accepted is True
    assert result.observations[0].source_timestamp == datetime(2026, 1, 22, 19, tzinfo=UTC)
    assert result.observations[0].payload.publication_date == date(2026, 1, 22)


def test_date_only_uncertain_placeholder_is_accepted_but_not_precise() -> None:
    result = normalize_finra_short_interest_record(
        record(
            publication_date="2026-01-22",
            date_only_publication_policy="INGESTION_TIME_UNCERTAIN_PLACEHOLDER",
        ),
        context(),
    )

    observation = result.observations[0]
    assert observation.source_timestamp == observation.received_timestamp
    assert observation.quality.state is QualityState.MISSING
    assert DiagnosticCode.FINRA_DATE_ONLY_PUBLICATION in diagnostic_codes(result)
    assert observation.provenance.provider_metadata["publication_time_uncertain"] is True


def test_publication_after_receipt_is_diagnosed_and_controls_effective_time() -> None:
    result = normalize_finra_short_interest_record(
        record(publication_date="2026-01-22T22:00:00Z"), context()
    )

    observation = result.observations[0]
    assert observation.received_timestamp == datetime(2026, 1, 22, 20, tzinfo=UTC)
    assert observation.effective_timestamp == datetime(2026, 1, 22, 22, tzinfo=UTC)
    assert DiagnosticCode.FINRA_RECEIVED_BEFORE_PUBLICATION in diagnostic_codes(result)


def test_invalid_optional_numeric_fields_are_omitted_with_invalid_quality() -> None:
    result = normalize_finra_short_interest_record(
        record(
            short_shares="1.5",
            float_shares="0",
            short_float_percent="12.5",
            days_to_cover="bad",
        ),
        context(),
    )

    observation = result.observations[0]
    assert observation.payload.short_shares is None
    assert observation.payload.float_shares is None
    assert observation.payload.short_float_percent is None
    assert observation.payload.days_to_cover is None
    assert observation.quality.state is QualityState.INVALID


def test_daily_short_volume_shape_is_rejected_as_unsupported() -> None:
    raw = {
        **record(),
        "record_type": "DAILY_SHORT_VOLUME",
        "short_volume": 100000,
        "total_volume": 500000,
    }
    result = normalize_finra_short_interest_record(raw, context())

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.code is DiagnosticCode.FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED


def test_exact_duplicate_is_emitted_once_with_diagnostic() -> None:
    raw = record()
    result = normalize_finra_short_interest_records([raw, dict(raw)], context())

    assert len(result.observations) == 1
    assert DiagnosticCode.FINRA_DUPLICATE_RECORD in diagnostic_codes(result)


def test_correction_is_new_immutable_observation_linked_to_original() -> None:
    original = record()
    correction = record(
        source_record_id="finra-correction-001",
        provider_record_id="provider-row-002",
        short_shares="2600000",
        publication_date="2026-01-29T14:00:00-05:00",
        revision_status="CORRECTED",
        revision_number=1,
        supersedes_source_record_id="finra-original-001",
    )
    result = normalize_finra_short_interest_records(
        [original, correction], context("2026-01-30T15:00:00Z")
    )

    assert len(result.observations) == 2
    first, second = result.observations
    assert first.payload.short_shares == 2500000
    assert second.payload.short_shares == 2600000
    assert second.parent_observation_ids == (first.observation_id,)
    assert first.correlation_id == second.correlation_id
    assert DiagnosticCode.FINRA_CORRECTED_RECORD in diagnostic_codes(result)


def test_missing_revision_link_preserves_revision_and_diagnoses_relationship() -> None:
    revision = record(
        source_record_id="finra-revision-001",
        revision_status="REVISED",
        supersedes_source_record_id="absent-record",
    )
    result = normalize_finra_short_interest_records([revision], context())

    assert len(result.observations) == 1
    assert result.observations[0].parent_observation_ids == ()
    assert DiagnosticCode.FINRA_REVISION_LINK_MISSING in diagnostic_codes(result)


def test_unlinked_same_period_conflict_preserves_both_without_winner() -> None:
    left = record()
    right = record(
        source_record_id="finra-other-001",
        provider_record_id="provider-row-other",
        short_shares="2700000",
    )
    result = normalize_finra_short_interest_records([left, right], context())

    assert len(result.observations) == 2
    assert all(item.quality.state is QualityState.CONFLICTED for item in result.observations)
    assert result.observations[0].correlation_id == result.observations[1].correlation_id
    assert DiagnosticCode.FINRA_CONFLICTING_RECORD in diagnostic_codes(result)


def test_different_settlement_periods_are_not_adapter_conflicts() -> None:
    later = record(
        source_record_id="finra-period-002",
        settlement_date="2026-01-31",
        publication_date="2026-02-07T19:00:00Z",
    )
    result = normalize_finra_short_interest_records(
        [record(), later], context("2026-02-08T15:00:00Z")
    )

    assert len(result.observations) == 2
    assert all(item.quality.state is QualityState.KNOWN_VALUE for item in result.observations)
    assert DiagnosticCode.FINRA_CONFLICTING_RECORD not in diagnostic_codes(result)


def test_normalization_is_byte_deterministic_and_diagnostics_are_sorted() -> None:
    raw = record(short_shares=None, float_shares=None, days_to_cover=None)
    first = normalize_finra_short_interest_record(raw, context())
    second = normalize_finra_short_interest_record(dict(raw), context())

    assert first == second
    assert diagnostic_codes(first) == tuple(sorted(diagnostic_codes(first), key=str))
