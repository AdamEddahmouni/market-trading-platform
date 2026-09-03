import re
from datetime import date
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import AssetClass

from .semantics import (
    BarCompletionStatus,
    BarInterval,
    BarSession,
    BarTimestampMeaning,
    BarVolumeUnit,
)


FixtureOrigin = Literal[
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
]


class MarketBarRecord(BaseModel):
    """Strict local-only provider-neutral market-bar record."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["MARKET_BAR_V1"]
    record_type: Literal["MARKET_BAR"]
    fixture_origin: FixtureOrigin
    provider: str = Field(min_length=1)
    provider_record_id: str | None = None
    symbol: str = Field(min_length=1, max_length=32, validation_alias=AliasChoices("symbol", "ticker"))
    asset_class: AssetClass = AssetClass.EQUITY
    exchange: str | None = Field(default=None, validation_alias=AliasChoices("exchange", "venue"))
    interval: BarInterval
    provider_timestamp: str | None = Field(
        default=None, validation_alias=AliasChoices("provider_timestamp", "timestamp", "datetime", "date")
    )
    timestamp_meaning: BarTimestampMeaning = BarTimestampMeaning.UNKNOWN
    bar_start: str | None = None
    bar_end: str | None = None
    open: str | int | float | None = Field(default=None, validation_alias=AliasChoices("open", "Open"))
    high: str | int | float | None = Field(default=None, validation_alias=AliasChoices("high", "High"))
    low: str | int | float | None = Field(default=None, validation_alias=AliasChoices("low", "Low"))
    close: str | int | float | None = Field(default=None, validation_alias=AliasChoices("close", "Close"))
    volume: str | int | float | None = Field(default=None, validation_alias=AliasChoices("volume", "Volume"))
    trade_count: str | int | float | None = Field(
        default=None, validation_alias=AliasChoices("trade_count", "barCount", "tradeCount")
    )
    vwap: str | int | float | None = Field(default=None, validation_alias=AliasChoices("vwap", "average", "VWAP"))
    volume_unit: BarVolumeUnit = BarVolumeUnit.UNKNOWN
    session: BarSession = BarSession.UNKNOWN
    session_date: date | None = None
    timezone: str | None = None
    status: BarCompletionStatus = BarCompletionStatus.UNKNOWN
    publication_timestamp: str | None = Field(
        default=None, validation_alias=AliasChoices("publication_timestamp", "published_at", "provider_available_at")
    )
    capture_timestamp: str | None = None
    revision_number: int | None = Field(default=None, ge=0)
    supersedes_provider_record_id: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,32}", normalized):
            raise ValueError("symbol has an unsupported format")
        return normalized

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().upper()

