from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .semantics import DelayStatus, PercentageUnit


FixtureOrigin = Literal["SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"]


class FinvizSnapshotRecord(BaseModel):
    """Validated local shape for a representative Finviz screener snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["FINVIZ_SCREENER_V1"]
    record_type: Literal["CANDIDATE_SNAPSHOT"]
    fixture_origin: FixtureOrigin
    symbol: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("symbol", "ticker", "Ticker"),
    )
    price: Any = Field(default=None, validation_alias=AliasChoices("price", "Price"))
    previous_close: Any = Field(
        default=None,
        validation_alias=AliasChoices("previous_close", "prev_close", "Prev Close"),
    )
    change_percent: Any = Field(
        default=None, validation_alias=AliasChoices("change_percent", "change", "Change")
    )
    change_percent_unit: PercentageUnit | None = None
    volume: Any = Field(default=None, validation_alias=AliasChoices("volume", "Volume"))
    average_volume: Any = Field(
        default=None,
        validation_alias=AliasChoices("average_volume", "avg_volume", "Avg Volume"),
    )
    relative_volume: Any = Field(
        default=None,
        validation_alias=AliasChoices("relative_volume", "Relative Volume"),
    )
    float_shares: Any = Field(
        default=None,
        validation_alias=AliasChoices("float_shares", "float", "Shares Float"),
    )
    shares_outstanding: Any = Field(
        default=None,
        validation_alias=AliasChoices("shares_outstanding", "Shares Outstanding"),
    )
    short_float_percent: Any = Field(
        default=None,
        validation_alias=AliasChoices("short_float_percent", "short_float", "Short Float"),
    )
    short_float_percent_unit: PercentageUnit | None = None
    short_ratio_days: Any = Field(
        default=None,
        validation_alias=AliasChoices("short_ratio_days", "short_ratio", "Short Ratio"),
    )
    market_cap: Any = Field(
        default=None, validation_alias=AliasChoices("market_cap", "Market Cap")
    )
    sector: str | None = Field(default=None, validation_alias=AliasChoices("sector", "Sector"))
    industry: str | None = Field(
        default=None, validation_alias=AliasChoices("industry", "Industry")
    )
    country: str | None = Field(
        default=None, validation_alias=AliasChoices("country", "Country")
    )
    exchange: str | None = Field(
        default=None, validation_alias=AliasChoices("exchange", "Exchange")
    )
    earnings: Any = Field(default=None, validation_alias=AliasChoices("earnings", "Earnings"))
    provider_timestamp: str | None = None
    provider_timezone: str | None = None
    capture_timestamp: str | None = None
    capture_timezone: str | None = None
    delay_status: DelayStatus = DelayStatus.UNKNOWN
    screener_name: str | None = None
    applied_filters: tuple[str, ...] = ()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized
