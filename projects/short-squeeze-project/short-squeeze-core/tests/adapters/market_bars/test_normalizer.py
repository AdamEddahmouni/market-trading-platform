from datetime import UTC, datetime
from decimal import Decimal

import pytest

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.market_bars import (
    normalize_market_bar_record,
    normalize_market_bar_records,
)
from squeeze_core.contracts import (
    Completeness,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSession,
    ObservationKind,
    PayloadType,
    QualityState,
)

from .test_models_and_parsing import record_values


def context(at="2026-01-15T14:31:02Z"):
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider="market-bars-offline",
        adapter_version="1.0.0",
        normalization_version="market-bars-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="sanitized-market-bar-fixture",
    )


def test_complete_bar_normalizes_to_unchanged_canonical_payload():
    result = normalize_market_bar_record(record_values(), context())
    assert result.accepted is True
    assert result.rejection is None
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.event_type is EventType.BAR
    assert observation.payload_type is PayloadType.BAR
    assert observation.symbol == "TESTA"
    assert observation.market_session is MarketSession.REGULAR
    assert observation.observation_kind is ObservationKind.MARKET_OBSERVED
    assert observation.source_timestamp == datetime(2026, 1, 15, 14, 31, 1, tzinfo=UTC)
    assert observation.received_timestamp == datetime(2026, 1, 15, 14, 31, 2, tzinfo=UTC)
    assert observation.effective_timestamp == datetime(2026, 1, 15, 14, 31, 2, tzinfo=UTC)
    assert observation.payload.timeframe == "1_MINUTE"
    assert observation.payload.open == Decimal("10.10")
    assert observation.payload.high == Decimal("10.30")
    assert observation.payload.low == Decimal("10.00")
    assert observation.payload.close == Decimal("10.25")
    assert observation.payload.volume == 1000
    assert observation.payload.trade_count == 25
    assert observation.payload.vwap == Decimal("10.20")
    metadata = observation.provenance.provider_metadata
    assert metadata["bar_start"] == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert metadata["bar_end"] == datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
    assert metadata["bar_end_exclusive"] is True
    assert metadata["interval_kind"] == "FIXED"
    assert metadata["session_date"] == "2026-01-15"
    assert metadata["status"] == "COMPLETED"


def test_exact_decimal_values_do_not_use_float_math():
    result = normalize_market_bar_record(
        record_values(open="0.1", high="0.3", low="0.1", close="0.2", vwap="0.2"),
        context(),
    )
    assert result.observations[0].payload.close == Decimal("0.2")


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_missing_required_ohlc_rejects_without_calculation(field):
    result = normalize_market_bar_record(record_values(**{field: None}), context())
    assert result.accepted is False
    assert result.rejection.code.value == f"BAR_MISSING_{field.upper()}"


def test_invalid_ohlc_relationship_rejects():
    result = normalize_market_bar_record(record_values(high="9.99"), context())
    assert result.accepted is False
    assert result.rejection.code.value == "BAR_INVALID_OHLC"


def test_missing_and_zero_volume_remain_distinct():
    missing = normalize_market_bar_record(record_values(volume=None), context())
    zero = normalize_market_bar_record(record_values(volume="0"), context())
    assert missing.observations[0].payload.volume is None
    assert zero.observations[0].payload.volume == 0
    assert "BAR_MISSING_VOLUME" in {item.code.value for item in missing.diagnostics}
    assert "BAR_ZERO_VOLUME" in {item.code.value for item in zero.diagnostics}


def test_explicit_zero_trade_count_is_preserved_and_diagnosed():
    result = normalize_market_bar_record(record_values(trade_count="0"), context())
    assert result.accepted
    assert result.observations[0].payload.trade_count == 0
    assert "BAR_ZERO_TRADE_COUNT" in {item.code.value for item in result.diagnostics}


@pytest.mark.parametrize("value", ["-1", "1.5"])
def test_negative_or_fractional_volume_rejects(value):
    result = normalize_market_bar_record(record_values(volume=value), context())
    assert result.accepted is False
    assert result.rejection.code.value == "BAR_INVALID_VOLUME"


def test_missing_trade_count_and_vwap_remain_null():
    result = normalize_market_bar_record(
        record_values(trade_count=None, vwap=None), context()
    )
    payload = result.observations[0].payload
    assert payload.trade_count is None
    assert payload.vwap is None
    assert {item.code.value for item in result.diagnostics} >= {
        "BAR_MISSING_TRADE_COUNT",
        "BAR_MISSING_VWAP",
    }


def test_partial_bar_is_explicitly_partial_and_not_completed():
    result = normalize_market_bar_record(record_values(status="PARTIAL"), context())
    observation = result.observations[0]
    assert observation.quality.state is QualityState.KNOWN_VALUE
    assert observation.quality.completeness is Completeness.PARTIAL
    assert observation.provenance.completeness is Completeness.PARTIAL
    assert "BAR_PARTIAL_RECORD" in {item.code.value for item in result.diagnostics}


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("COMPLETED", "BAR_COMPLETED_RECORD"),
        ("CORRECTED", "BAR_CORRECTED_RECORD"),
        ("CANCELLED", "BAR_CANCELLED_RECORD"),
    ],
)
def test_lifecycle_status_has_stable_diagnostic(status, code):
    result = normalize_market_bar_record(record_values(status=status), context())
    assert code in {item.code.value for item in result.diagnostics}


def test_publication_after_receipt_waits_for_publication():
    result = normalize_market_bar_record(
        record_values(publication_timestamp="2026-01-15T09:31:05-05:00"), context()
    )
    observation = result.observations[0]
    assert observation.effective_timestamp == datetime(2026, 1, 15, 14, 31, 5, tzinfo=UTC)
    assert "BAR_PUBLICATION_AFTER_RECEIPT" in {item.code.value for item in result.diagnostics}


def test_missing_publication_rejects_unknown_availability():
    result = normalize_market_bar_record(record_values(publication_timestamp=None), context())
    assert result.accepted is False
    assert result.rejection.code.value == "BAR_UNKNOWN_AVAILABILITY"


def test_session_date_mismatch_rejects():
    result = normalize_market_bar_record(record_values(session_date="2026-01-16"), context())
    assert result.accepted is False
    assert result.rejection.code.value == "BAR_SESSION_DATE_MISMATCH"


def test_exact_duplicate_is_emitted_once():
    raw = record_values()
    result = normalize_market_bar_records([raw, dict(raw)], context())
    assert len(result.observations) == 1
    assert "BAR_DUPLICATE_RECORD" in {item.code.value for item in result.diagnostics}


def test_same_provider_id_changed_content_is_preserved_as_conflict():
    first = record_values()
    second = record_values(close="10.26", source_record_id="bar-fixture-2")
    result = normalize_market_bar_records([first, second], context())
    assert len(result.observations) == 2
    assert all(item.quality.state is QualityState.CONFLICTED for item in result.observations)
    assert len({item.correlation_id for item in result.observations}) == 1
    assert "BAR_CONFLICTING_RECORD" in {item.code.value for item in result.diagnostics}


def test_partial_complete_correction_links_are_immutable():
    partial = record_values(
        provider_record_id="bar-partial",
        source_record_id="partial",
        status="PARTIAL",
        publication_timestamp="2026-01-15T09:30:30-05:00",
    )
    completed = record_values(
        provider_record_id="bar-complete",
        source_record_id="complete",
        status="COMPLETED",
        supersedes_provider_record_id="bar-partial",
    )
    corrected = record_values(
        provider_record_id="bar-corrected",
        source_record_id="corrected",
        status="CORRECTED",
        close="10.26",
        publication_timestamp="2026-01-15T09:35:00-05:00",
        supersedes_provider_record_id="bar-complete",
    )
    result = normalize_market_bar_records([corrected, partial, completed], context("2026-01-15T14:35:01Z"))
    by_id = {item.source_record_id: item for item in result.observations}
    assert by_id["bar-partial"].parent_observation_ids == ()
    assert by_id["bar-complete"].parent_observation_ids == (by_id["bar-partial"].observation_id,)
    assert by_id["bar-corrected"].parent_observation_ids == (by_id["bar-complete"].observation_id,)
    assert by_id["bar-partial"].payload.close == Decimal("10.25")
    assert by_id["bar-corrected"].payload.close == Decimal("10.26")


def test_revision_without_prior_record_is_diagnosed_but_preserved():
    result = normalize_market_bar_records(
        [record_values(status="CORRECTED", supersedes_provider_record_id="missing")],
        context(),
    )
    assert len(result.observations) == 1
    assert "BAR_REVISION_LINK_MISSING" in {item.code.value for item in result.diagnostics}


def test_repeated_normalization_is_byte_identical():
    first = normalize_market_bar_record(record_values(), context())
    second = normalize_market_bar_record(record_values(), context())
    assert first == second
