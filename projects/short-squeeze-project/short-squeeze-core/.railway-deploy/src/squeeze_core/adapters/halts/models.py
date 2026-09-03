import re
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .semantics import HaltLifecycleStatus, HaltRevisionStatus


FixtureOrigin = Literal[
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
]


class TradingHaltRecord(BaseModel):
    """Strict local-only shape for representative halt lifecycle metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["TRADING_HALT_V1"]
    record_type: Literal["TRADING_HALT"]
    fixture_origin: FixtureOrigin
    symbol: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("symbol", "ticker"),
    )
    exchange: str | None = Field(
        default=None,
        validation_alias=AliasChoices("exchange", "market"),
    )
    provider_halt_id: str | None = None
    provider_record_id: str | None = None
    halt_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("halt_code", "reason_code"),
    )
    reason_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices("reason_text", "reason"),
    )
    announcement_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("announcement_at", "announcement_datetime"),
    )
    halt_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("halt_at", "halt_datetime"),
    )
    quote_resumption_scheduled_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "quote_resumption_scheduled_at", "quote_resume_scheduled_at"
        ),
    )
    quote_resumed_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("quote_resumed_at", "quote_resume_at"),
    )
    trade_resumption_scheduled_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "trade_resumption_scheduled_at", "trade_resume_scheduled_at"
        ),
    )
    trading_resumed_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("trading_resumed_at", "trade_resume_at"),
    )
    publication_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("publication_at", "published_at"),
    )
    session_date: str | None = None
    timezone: str | None = None
    status: HaltLifecycleStatus = Field(
        validation_alias=AliasChoices("status", "record_status")
    )
    revision_status: HaltRevisionStatus = HaltRevisionStatus.ORIGINAL
    revision_number: int | None = Field(default=None, ge=0)
    supersedes_source_record_id: str | None = None
    capture_timestamp: str | None = None
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
