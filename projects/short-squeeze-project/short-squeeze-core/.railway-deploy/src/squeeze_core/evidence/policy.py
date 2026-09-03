from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import EventType
from squeeze_core.contracts.validation import require_aware_utc


class PointInTimeEvidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: datetime
    maximum_future_skew_ms: int = Field(default=0, ge=0)
    maximum_age_ms_by_event_type: dict[EventType, int] = Field(default_factory=dict)
    allow_stale: bool = False
    allow_delayed: bool = True
    allow_unknown_freshness: bool = True
    conflict_tolerance: dict[str, Decimal] = Field(default_factory=dict)
    source_priority_metadata: dict[str, int] = Field(default_factory=dict)
    maximum_reporting_period_age_days: int | None = Field(default=None, ge=0)
    include_published_short_interest_domain: bool = False
    include_sec_filings_domain: bool = False
    include_trading_halts_domain: bool = False
    include_news_domain: bool = False
    include_market_bars_domain: bool = False
    include_trades_domain: bool = Field(default=False, exclude=True)
    include_quotes_domain: bool = Field(default=False, exclude=True)

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("maximum_age_ms_by_event_type")
    @classmethod
    def nonnegative_ages(cls, value: dict[EventType, int]) -> dict[EventType, int]:
        if any(age < 0 for age in value.values()):
            raise ValueError("maximum ages must be nonnegative")
        return value

    @field_validator("conflict_tolerance")
    @classmethod
    def nonnegative_tolerances(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        if any(item < 0 for item in value.values()):
            raise ValueError("conflict tolerances must be nonnegative")
        return value
