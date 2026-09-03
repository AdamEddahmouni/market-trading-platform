from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.trades_quotes import (
    FixtureOrigin,
    MarketScope,
    QuoteMarketState,
    SequenceScope,
    SizeUnit,
    TradeQuoteLifecycleStatus,
    TradeQuoteRecord,
    TradeQuoteRecordType,
    TradeQuoteValidationError,
    UnknownAvailabilityPolicy,
    parse_trade_quote_timestamp,
    quote_market_state,
)


def record_values(**updates):
    values = {
        "schema_version": "TRADE_QUOTE_V1",
        "record_type": "TRADE",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "provider": "REPRESENTATIVE_FEED",
        "provider_record_id": "trade-1",
        "symbol": "TESTA",
        "asset_class": "EQUITY",
        "exchange": "XTEST",
        "venue": "XTEST",
        "sequence_number": 100,
        "sequence_scope": "VENUE",
        "event_timestamp": "2026-01-15T09:30:00.100000-05:00",
        "publication_timestamp": "2026-01-15T09:30:00.200000-05:00",
        "capture_timestamp": "2026-01-15T09:30:00.250000-05:00",
        "market_session": "REGULAR",
        "status": "ORIGINAL",
        "revision_number": 0,
        "price": "10.25",
        "size": 100,
        "size_unit": "SHARES",
        "trade_conditions": ["REGULAR", "ODD_LOT"],
        "sale_condition": "REGULAR",
        "market_scope": "VENUE",
        "source_shape": "PROVIDER_NEUTRAL",
        "provider_metadata": {"channel": "A"},
    }
    values.update(updates)
    return values


def test_trade_record_is_strict_immutable_and_typed():
    record = TradeQuoteRecord.model_validate(record_values())
    assert record.record_type is TradeQuoteRecordType.TRADE
    assert record.fixture_origin is FixtureOrigin.SANITIZED_REPRESENTATIVE_SAMPLE
    assert record.sequence_scope is SequenceScope.VENUE
    assert record.size_unit is SizeUnit.SHARES
    assert record.market_scope is MarketScope.VENUE
    assert record.status is TradeQuoteLifecycleStatus.ORIGINAL
    with pytest.raises(ValidationError):
        record.provider = "changed"


def test_unknown_fields_and_alias_shapes_reject():
    with pytest.raises(ValidationError, match="Extra inputs"):
        TradeQuoteRecord.model_validate(record_values(lastPrice="10.25"))


@pytest.mark.parametrize("field", ["provider", "provider_record_id", "symbol"])
def test_required_identity_fields_reject_blank(field):
    with pytest.raises(ValidationError):
        TradeQuoteRecord.model_validate(record_values(**{field: " "}))


def test_fractional_and_negative_sequence_or_size_reject():
    for updates in (
        {"sequence_number": -1},
        {"sequence_number": Decimal("1.5")},
        {"size": -1},
        {"size": Decimal("1.5")},
    ):
        with pytest.raises(ValidationError):
            TradeQuoteRecord.model_validate(record_values(**updates))


def test_quote_record_preserves_independent_sides_and_scope():
    record = TradeQuoteRecord.model_validate(
        record_values(
            record_type="QUOTE",
            provider_record_id="quote-1",
            price=None,
            size=None,
            trade_conditions=[],
            sale_condition=None,
            bid_price="10.24",
            bid_size=0,
            ask_price=None,
            ask_size=None,
            bid_side_id="bid-A",
            ask_side_id=None,
            quote_condition="REGULAR",
            quote_source="VENUE_BOOK",
            market_scope="VENUE",
        )
    )
    assert record.record_type is TradeQuoteRecordType.QUOTE
    assert record.bid_price == "10.24"
    assert record.bid_size == 0
    assert record.ask_price is None
    assert record.bid_side_id == "bid-A"


def test_timestamp_parser_keeps_exact_instant_and_requires_timezone_for_naive_value():
    parsed = parse_trade_quote_timestamp(
        "2026-01-15T09:30:00.100000-05:00", source_timezone=None
    )
    assert parsed == datetime(2026, 1, 15, 14, 30, 0, 100000, tzinfo=UTC)
    with pytest.raises(TradeQuoteValidationError) as error:
        parse_trade_quote_timestamp("2026-01-15T09:30:00", source_timezone=None)
    assert error.value.code == "TRADE_QUOTE_MISSING_TIMEZONE"


def test_timestamp_parser_supports_explicit_numeric_source_offset():
    parsed = parse_trade_quote_timestamp(
        "2026-01-15T09:30:00", source_timezone="-05:00"
    )
    assert parsed == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("bid", "ask", "expected"),
    [
        (Decimal("10.00"), Decimal("10.01"), QuoteMarketState.NORMAL),
        (Decimal("10.01"), Decimal("10.01"), QuoteMarketState.LOCKED),
        (Decimal("10.02"), Decimal("10.01"), QuoteMarketState.CROSSED),
        (Decimal("10.00"), None, QuoteMarketState.UNKNOWN),
        (None, Decimal("10.01"), QuoteMarketState.UNKNOWN),
    ],
)
def test_quote_market_state_is_structural_only(bid, ask, expected):
    assert quote_market_state(bid, ask) is expected


def test_all_required_enum_values_are_explicit():
    assert {item.value for item in SequenceScope} == {
        "PROVIDER_GLOBAL", "SYMBOL", "VENUE", "CHANNEL", "SESSION", "UNKNOWN"
    }
    assert {item.value for item in MarketScope} == {
        "VENUE", "NBBO", "CONSOLIDATED", "PROVIDER_AGGREGATED", "UNKNOWN"
    }
    assert {item.value for item in UnknownAvailabilityPolicy} == {
        "STRICT", "CAPTURE_AS_UNCERTAIN_PLACEHOLDER", "RECEIPT_AS_UNCERTAIN_PLACEHOLDER"
    }
