from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .validation import require_aware_utc
from .enums import EarningsSession


class PayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TradePayload(PayloadModel):
    price: Decimal = Field(gt=0)
    size: int | None = Field(default=None, ge=0)
    exchange: str | None = None
    conditions: tuple[str, ...] = ()


class QuotePayload(PayloadModel):
    bid_price: Decimal | None = Field(default=None, ge=0)
    bid_size: int | None = Field(default=None, ge=0)
    ask_price: Decimal | None = Field(default=None, ge=0)
    ask_size: int | None = Field(default=None, ge=0)
    exchange: str | None = None

    @property
    def is_crossed(self) -> bool:
        return (
            self.bid_price is not None
            and self.ask_price is not None
            and self.bid_price > self.ask_price
        )


class BarPayload(PayloadModel):
    timeframe: str
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int | None = Field(default=None, ge=0)
    trade_count: int | None = Field(default=None, ge=0)
    vwap: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_ohlc_bounds(self) -> "BarPayload":
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("bar high is below an OHLC value")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("bar low is above an OHLC value")
        return self


class PublishedShortInterestPayload(PayloadModel):
    short_shares: int | None = Field(default=None, ge=0)
    float_shares: int | None = Field(default=None, gt=0)
    short_float_percent: Decimal | None = Field(default=None, ge=0)
    settlement_date: date | None = None
    publication_date: date | None = None
    days_to_cover: Decimal | None = Field(default=None, ge=0)


class BorrowAvailabilityPayload(PayloadModel):
    available_shares: int | None = Field(default=None, ge=0)
    lender_count: int | None = Field(default=None, ge=0)
    hard_to_borrow: bool | None = None


class BorrowFeePayload(PayloadModel):
    annualized_fee_percent: Decimal | None = Field(default=None, ge=0)
    fee_type: str | None = None


class NewsItemPayload(PayloadModel):
    headline: str
    summary: str | None = None
    url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    associated_symbols: tuple[str, ...] = ()

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class SecFilingPayload(PayloadModel):
    form_type: str
    accession_number: str
    filed_at: datetime
    period_of_report: date | None = None
    primary_document: str | None = None
    issuer_cik: str | None = None

    @field_validator("filed_at")
    @classmethod
    def normalize_filed_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class TradingHaltPayload(PayloadModel):
    halt_status: str
    halt_reason: str | None = None
    halt_time: datetime | None = None
    resume_time: datetime | None = None

    @field_validator("halt_time", "resume_time")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class CorporateActionPayload(PayloadModel):
    action_type: str
    effective_date: date | None = None
    description: str | None = None


class DerivedIndicatorPayload(PayloadModel):
    calculation_name: str
    calculation_version: str
    input_observation_ids: tuple[str, ...]
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: Decimal | str | bool | None


class SourceStatusPayload(PayloadModel):
    status: str
    latency_ms: int | None = Field(default=None, ge=0)
    last_successful_event_at: datetime | None = None
    error_code: str | None = None
    message: str | None = None

    @field_validator("last_successful_event_at")
    @classmethod
    def normalize_last_success(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class MarketSnapshotPayload(PayloadModel):
    last_price: Decimal | None = Field(default=None, ge=0)
    previous_close: Decimal | None = Field(default=None, ge=0)
    change_percent: Decimal | None = None
    volume: int | None = Field(default=None, ge=0)
    average_volume: int | None = Field(default=None, ge=0)
    relative_volume: Decimal | None = Field(default=None, ge=0)
    float_shares: int | None = Field(default=None, ge=0)
    shares_outstanding: int | None = Field(default=None, ge=0)
    short_float_percent: Decimal | None = Field(default=None, ge=0)
    short_ratio_days: Decimal | None = Field(default=None, ge=0)
    market_cap: int | None = Field(default=None, ge=0)
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None
    earnings_date: date | None = None
    earnings_session: EarningsSession | None = None
    snapshot_scope: str | None = None


Payload = (
    TradePayload
    | QuotePayload
    | BarPayload
    | PublishedShortInterestPayload
    | BorrowAvailabilityPayload
    | BorrowFeePayload
    | NewsItemPayload
    | SecFilingPayload
    | TradingHaltPayload
    | CorporateActionPayload
    | DerivedIndicatorPayload
    | SourceStatusPayload
    | MarketSnapshotPayload
)
