from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AssetClass,
    DataFreshness,
    EventType,
    MarketSession,
    ObservationKind,
    PayloadType,
)
from .identifiers import deterministic_observation_id
from .payloads import (
    BarPayload,
    BorrowAvailabilityPayload,
    BorrowFeePayload,
    CorporateActionPayload,
    DerivedIndicatorPayload,
    NewsItemPayload,
    Payload,
    PublishedShortInterestPayload,
    QuotePayload,
    SecFilingPayload,
    SourceStatusPayload,
    MarketSnapshotPayload,
    TradePayload,
    TradingHaltPayload,
)
from .provenance import Provenance
from .quality import Quality
from .validation import require_aware_utc


PAYLOAD_BINDINGS: dict[EventType, tuple[PayloadType, type[BaseModel]]] = {
    EventType.TRADE: (PayloadType.TRADE, TradePayload),
    EventType.QUOTE: (PayloadType.QUOTE, QuotePayload),
    EventType.BAR: (PayloadType.BAR, BarPayload),
    EventType.PUBLISHED_SHORT_INTEREST: (
        PayloadType.PUBLISHED_SHORT_INTEREST,
        PublishedShortInterestPayload,
    ),
    EventType.BORROW_AVAILABILITY: (PayloadType.BORROW_AVAILABILITY, BorrowAvailabilityPayload),
    EventType.BORROW_FEE: (PayloadType.BORROW_FEE, BorrowFeePayload),
    EventType.NEWS_ITEM: (PayloadType.NEWS_ITEM, NewsItemPayload),
    EventType.SEC_FILING: (PayloadType.SEC_FILING, SecFilingPayload),
    EventType.TRADING_HALT: (PayloadType.TRADING_HALT, TradingHaltPayload),
    EventType.CORPORATE_ACTION: (PayloadType.CORPORATE_ACTION, CorporateActionPayload),
    EventType.DERIVED_INDICATOR: (PayloadType.DERIVED_INDICATOR, DerivedIndicatorPayload),
    EventType.SOURCE_STATUS: (PayloadType.SOURCE_STATUS, SourceStatusPayload),
    EventType.MARKET_SNAPSHOT: (PayloadType.MARKET_SNAPSHOT, MarketSnapshotPayload),
}


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"]
    observation_id: str | None = None
    event_type: EventType
    symbol: str | None
    asset_class: AssetClass
    source: str
    source_record_id: str
    source_timestamp: datetime
    received_timestamp: datetime
    effective_timestamp: datetime
    market_session: MarketSession
    data_freshness: DataFreshness
    observation_kind: ObservationKind
    quality: Quality
    payload_type: PayloadType
    payload: Payload
    provenance: Provenance
    sequence_number: int | None = Field(default=None, ge=0)
    exchange: str | None = None
    currency: str | None = None
    timezone: str | None = None
    correlation_id: str | None = None
    parent_observation_ids: tuple[str, ...] = ()
    raw_payload_hash: str | None = None
    normalization_version: str | None = None
    notes: str | None = None

    @field_validator("source_timestamp", "received_timestamp", "effective_timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "Observation":
        expected_payload_type, expected_model = PAYLOAD_BINDINGS[self.event_type]
        if self.payload_type is not expected_payload_type:
            raise ValueError("payload_type does not match event_type")
        if not isinstance(self.payload, expected_model):
            raise ValueError("payload model does not match event_type")
        if self.provenance.origin_kind is not self.observation_kind:
            raise ValueError("provenance origin_kind must match observation_kind")
        if self.observation_id is None:
            identity = {
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "symbol": self.symbol,
                "source": self.source,
                "source_record_id": self.source_record_id,
                "source_timestamp": self.source_timestamp,
                "payload_type": self.payload_type,
                "payload": self.payload.model_dump(mode="python"),
            }
            object.__setattr__(self, "observation_id", deterministic_observation_id(identity))
        return self
