from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .semantics import DateOnlyPublicationPolicy, PercentageUnit, RevisionStatus


FixtureOrigin = Literal[
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
]


class FinraShortInterestRecord(BaseModel):
    """Strict local shape for representative published short-interest data."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["FINRA_SHORT_INTEREST_V1"]
    record_type: Literal["PUBLISHED_SHORT_INTEREST"]
    fixture_origin: FixtureOrigin
    symbol: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("symbol", "Symbol", "security_symbol"),
    )
    short_shares: Any = Field(
        default=None,
        validation_alias=AliasChoices("short_shares", "Short Shares", "shares_short"),
    )
    settlement_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "settlement_date", "Settlement Date", "reporting_date", "observation_date"
        ),
    )
    publication_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "publication_date", "Publication Date", "publication_timestamp"
        ),
    )
    publication_timezone: str | None = None
    date_only_publication_policy: DateOnlyPublicationPolicy = (
        DateOnlyPublicationPolicy.STRICT_REJECT
    )
    previous_short_shares: Any = None
    average_daily_volume: Any = None
    average_daily_volume_reference: str | None = None
    days_to_cover: Any = None
    float_shares: Any = None
    short_float_percent: Any = None
    short_float_percent_unit: PercentageUnit | None = None
    market: str | None = None
    exchange: str | None = None
    revision_status: RevisionStatus = Field(
        default=RevisionStatus.UNKNOWN,
        validation_alias=AliasChoices("revision_status", "record_status"),
    )
    revision_number: int | None = Field(default=None, ge=0)
    supersedes_source_record_id: str | None = None
    provider_record_id: str | None = None
    provider_timestamp: str | None = None
    provider_timezone: str | None = None
    provider_timestamp_is_publication: bool = False
    capture_timestamp: str | None = None
    capture_timezone: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized
