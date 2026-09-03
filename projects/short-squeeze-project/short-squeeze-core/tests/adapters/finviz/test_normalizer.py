from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters import AdapterContext, DiagnosticCode
from squeeze_core.adapters.finviz import (
    normalize_finviz_snapshot_record,
    normalize_finviz_snapshot_records,
)
from squeeze_core.contracts import (
    DataFreshness,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSnapshotPayload,
    ObservationKind,
    QualityState,
    ReplayMode,
)
from squeeze_core.replay import ReplayEngine
from squeeze_core.serialization import canonical_hash, serialize_jsonl


def context() -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime(2026, 1, 15, 15, 5, tzinfo=UTC),
        source_timezone="America/New_York",
        provider="FINVIZ_REPRESENTATIVE",
        adapter_version="finviz-offline-v1",
        normalization_version="finviz-normalization-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="screener-export-shape",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "finviz-representative-001",
        "provider_schema": "FINVIZ_SCREENER_V1",
        "record_type": "CANDIDATE_SNAPSHOT",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "Ticker": "TESTA",
        "Price": "5.25",
        "Prev Close": "4.75",
        "Change": "10.5%",
        "change_percent_unit": "FORMATTED_PERCENT_STRING",
        "Volume": "125000",
        "Avg Volume": "25000",
        "Relative Volume": "5.0",
        "Shares Float": "8000000",
        "Shares Outstanding": "12000000",
        "Short Float": "12.5%",
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING",
        "Short Ratio": "2.75",
        "Market Cap": "63000000",
        "Sector": "Synthetic Sector",
        "Industry": "Synthetic Industry",
        "Country": "Synthetic Country",
        "Exchange": "XTEST",
        "Earnings": "2026-02-02 BMO",
        "provider_timestamp": "2026-01-15T10:00:00-05:00",
        "capture_timestamp": "2026-01-15T10:01:00-05:00",
        "delay_status": "UNKNOWN",
        "screener_name": "synthetic-candidate-screen",
        "applied_filters": ["price-under-20", "float-under-20m"],
    }
    value.update(overrides)
    return value


def codes(result) -> set[DiagnosticCode]:
    return {item.code for item in result.diagnostics}


def test_complete_row_produces_one_provider_neutral_market_snapshot() -> None:
    raw = record()
    result = normalize_finviz_snapshot_record(raw, context())

    assert result.accepted is True
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.event_type is EventType.MARKET_SNAPSHOT
    assert isinstance(observation.payload, MarketSnapshotPayload)
    assert observation.payload.last_price == Decimal("5.25")
    assert observation.payload.float_shares == 8000000
    assert observation.payload.short_float_percent == Decimal("12.5")
    assert observation.observation_kind is ObservationKind.PROVIDER_PUBLISHED
    assert observation.source_timestamp == datetime(2026, 1, 15, 15, 0, tzinfo=UTC)
    assert observation.effective_timestamp == observation.source_timestamp
    assert observation.received_timestamp == context().ingested_at
    assert observation.data_freshness is DataFreshness.UNKNOWN
    assert observation.raw_payload_hash == canonical_hash(raw)
    assert observation.provenance.source_timestamp_representation == raw["provider_timestamp"]
    assert observation.provenance.provider_metadata["capture_timestamp"] == raw["capture_timestamp"]
    assert DiagnosticCode.FINVIZ_RELATIVE_VOLUME_REFERENCE_UNKNOWN in codes(result)
    assert DiagnosticCode.FINVIZ_DATE_ONLY_EARNINGS in codes(result)


def test_provider_capture_received_and_effective_times_remain_distinct() -> None:
    result = normalize_finviz_snapshot_record(record(), context())
    observation = result.observations[0]

    assert observation.source_timestamp.isoformat() == "2026-01-15T15:00:00+00:00"
    assert observation.provenance.provider_metadata["capture_timestamp_utc"] == (
        "2026-01-15T15:01:00.000000Z"
    )
    assert observation.received_timestamp.isoformat() == "2026-01-15T15:05:00+00:00"


def test_capture_time_is_only_uncertain_placeholder_when_provider_time_is_absent() -> None:
    result = normalize_finviz_snapshot_record(record(provider_timestamp=None), context())
    observation = result.observations[0]

    assert observation.source_timestamp == datetime(2026, 1, 15, 15, 1, tzinfo=UTC)
    assert observation.effective_timestamp == observation.source_timestamp
    assert observation.provenance.source_timestamp_representation is None
    assert observation.provenance.provider_metadata["effective_time_basis"] == (
        "CAPTURE_TIME_UNCERTAIN_PLACEHOLDER"
    )
    assert observation.quality.state is QualityState.MISSING
    assert observation.data_freshness is DataFreshness.UNKNOWN
    assert DiagnosticCode.FINVIZ_CAPTURE_TIME_PLACEHOLDER in codes(result)


def test_ingestion_time_is_uncertain_placeholder_when_both_source_times_are_absent() -> None:
    result = normalize_finviz_snapshot_record(
        record(provider_timestamp=None, capture_timestamp=None), context()
    )
    observation = result.observations[0]

    assert observation.source_timestamp == context().ingested_at
    assert observation.provenance.source_timestamp_representation is None
    assert observation.provenance.provider_metadata["effective_time_basis"] == (
        "INGESTION_TIME_UNCERTAIN_PLACEHOLDER"
    )
    assert DiagnosticCode.FINVIZ_MISSING_TIMESTAMP in codes(result)


def test_missing_values_and_known_zero_values_remain_distinct() -> None:
    zero = normalize_finviz_snapshot_record(
        record(Volume="0", **{"Shares Float": None, "Short Float": "0%"}), context()
    ).observations[0]
    missing = normalize_finviz_snapshot_record(
        record(
            source_record_id="finviz-representative-002",
            Volume=None,
            **{"Shares Float": None, "Short Float": None},
        ),
        context(),
    ).observations[0]

    assert zero.payload.volume == 0
    assert zero.payload.float_shares is None
    assert zero.payload.short_float_percent == 0
    assert missing.payload.volume is None
    assert missing.payload.float_shares is None
    assert missing.payload.short_float_percent is None


def test_abbreviated_quantities_are_estimated_and_diagnosed() -> None:
    result = normalize_finviz_snapshot_record(
        record(Volume="125K", **{"Shares Float": "8M"}), context()
    )
    observation = result.observations[0]

    assert observation.payload.volume == 125000
    assert observation.payload.float_shares == 8000000
    assert observation.quality.state is QualityState.ESTIMATED
    assert DiagnosticCode.FINVIZ_APPROXIMATE_QUANTITY in codes(result)


def test_invalid_price_does_not_discard_other_unambiguous_descriptive_fields() -> None:
    result = normalize_finviz_snapshot_record(record(Price="not-a-price"), context())
    observation = result.observations[0]

    assert result.accepted is True
    assert observation.payload.last_price is None
    assert observation.payload.volume == 125000
    assert observation.quality.state is QualityState.INVALID
    assert DiagnosticCode.FINVIZ_INVALID_PRICE in codes(result)
    assert DiagnosticCode.FINVIZ_PARTIAL_RECORD in codes(result)


def test_explicit_zero_price_is_preserved_but_invalid() -> None:
    result = normalize_finviz_snapshot_record(record(Price="0"), context())

    assert result.observations[0].payload.last_price == 0
    assert result.observations[0].quality.state is QualityState.INVALID
    assert DiagnosticCode.FINVIZ_ZERO_PRICE in codes(result)


def test_known_delay_is_not_claimed_live() -> None:
    result = normalize_finviz_snapshot_record(record(delay_status="KNOWN_DELAYED"), context())

    assert result.observations[0].data_freshness is DataFreshness.DELAYED
    assert result.observations[0].quality.state is QualityState.DELAYED


def test_same_record_and_context_are_byte_identical_and_strictly_replayable() -> None:
    first = normalize_finviz_snapshot_record(record(), context())
    second = normalize_finviz_snapshot_record(record(), context())

    assert serialize_jsonl(first.observations) == serialize_jsonl(second.observations)
    assert ReplayEngine(mode=ReplayMode.STRICT).replay(first.observations).to_bytes() == (
        ReplayEngine(mode=ReplayMode.STRICT).replay(second.observations).to_bytes()
    )


def test_batch_suppresses_exact_duplicates_and_preserves_conflicts() -> None:
    duplicate = normalize_finviz_snapshot_records([record(), record()], context())
    conflict = normalize_finviz_snapshot_records(
        [record(), record(source_record_id="finviz-conflict-002", Price="7.25")], context()
    )

    assert len(duplicate.observations) == 1
    assert DiagnosticCode.FINVIZ_DUPLICATE_RECORD in codes(duplicate)
    assert len(conflict.observations) == 2
    assert all(item.quality.state is QualityState.CONFLICTED for item in conflict.observations)
    assert len({item.correlation_id for item in conflict.observations}) == 1
    assert DiagnosticCode.FINVIZ_CONFLICTING_RECORD in codes(conflict)
