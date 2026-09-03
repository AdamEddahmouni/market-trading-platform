from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import MarketSession


class FixtureOrigin(StrEnum):
    SANITIZED_RECORDED_SAMPLE = "SANITIZED_RECORDED_SAMPLE"
    SANITIZED_REPRESENTATIVE_SAMPLE = "SANITIZED_REPRESENTATIVE_SAMPLE"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"


class TradeQuoteRecordType(StrEnum):
    TRADE = "TRADE"
    QUOTE = "QUOTE"


class TradeQuoteLifecycleStatus(StrEnum):
    ORIGINAL = "ORIGINAL"
    CORRECTED = "CORRECTED"
    CANCELLED = "CANCELLED"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


class SequenceScope(StrEnum):
    PROVIDER_GLOBAL = "PROVIDER_GLOBAL"
    SYMBOL = "SYMBOL"
    VENUE = "VENUE"
    CHANNEL = "CHANNEL"
    SESSION = "SESSION"
    UNKNOWN = "UNKNOWN"


class MarketScope(StrEnum):
    VENUE = "VENUE"
    NBBO = "NBBO"
    CONSOLIDATED = "CONSOLIDATED"
    PROVIDER_AGGREGATED = "PROVIDER_AGGREGATED"
    UNKNOWN = "UNKNOWN"


class SizeUnit(StrEnum):
    SHARES = "SHARES"
    CONTRACTS = "CONTRACTS"
    UNITS = "UNITS"
    UNKNOWN = "UNKNOWN"


class QuoteMarketState(StrEnum):
    NORMAL = "NORMAL"
    LOCKED = "LOCKED"
    CROSSED = "CROSSED"
    UNKNOWN = "UNKNOWN"


class UnknownAvailabilityPolicy(StrEnum):
    STRICT = "STRICT"
    CAPTURE_AS_UNCERTAIN_PLACEHOLDER = "CAPTURE_AS_UNCERTAIN_PLACEHOLDER"
    RECEIPT_AS_UNCERTAIN_PLACEHOLDER = "RECEIPT_AS_UNCERTAIN_PLACEHOLDER"


class TradeQuoteRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["TRADE_QUOTE_V1"]
    record_type: TradeQuoteRecordType
    fixture_origin: FixtureOrigin
    provider: str
    provider_record_id: str
    symbol: str
    asset_class: Literal["EQUITY"]
    exchange: str | None = None
    venue: str | None = None
    sequence_number: int | None = Field(default=None, ge=0)
    sequence_scope: SequenceScope = SequenceScope.UNKNOWN
    sequence_channel: str | None = None
    sequence_session: str | None = None
    sequence_reset: bool = False
    event_timestamp: str | datetime | None = None
    publication_timestamp: str | datetime | None = None
    capture_timestamp: str | datetime | None = None
    unknown_availability_policy: UnknownAvailabilityPolicy = UnknownAvailabilityPolicy.STRICT
    market_session: MarketSession = MarketSession.UNKNOWN
    status: TradeQuoteLifecycleStatus = TradeQuoteLifecycleStatus.ORIGINAL
    revision_number: int | None = Field(default=None, ge=0)
    supersedes_provider_record_id: str | None = None
    price: str | int | float | None = None
    size: int | None = Field(default=None, ge=0)
    size_unit: SizeUnit = SizeUnit.UNKNOWN
    trade_conditions: tuple[str, ...] = ()
    sale_condition: str | None = None
    bid_price: str | int | float | None = None
    bid_size: int | None = Field(default=None, ge=0)
    ask_price: str | int | float | None = None
    ask_size: int | None = Field(default=None, ge=0)
    bid_side_id: str | None = None
    ask_side_id: str | None = None
    quote_condition: str | None = None
    quote_source: str | None = None
    market_scope: MarketScope = MarketScope.UNKNOWN
    source_shape: Literal["PROVIDER_NEUTRAL"] = "PROVIDER_NEUTRAL"
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider", "provider_record_id", "symbol")
    @classmethod
    def nonblank_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identity value must not be blank")
        return normalized

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange", "venue", "sequence_channel", "sequence_session")
    @classmethod
    def normalize_optional_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
