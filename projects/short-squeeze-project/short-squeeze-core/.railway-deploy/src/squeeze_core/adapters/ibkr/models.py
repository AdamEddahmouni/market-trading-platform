from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IbkrBorrowRecord(BaseModel):
    """Validated shape of a sanitized IBKR short-stock-file-style row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_record_id: str
    symbol: str = Field(min_length=1, max_length=32)
    fee_rate: Any = None
    fee_rate_unit: str | None = None
    available_shares: Any = None
    lender_count: Any = None
    hard_to_borrow: bool | None = None
    provider_timestamp: str | None = None
    provider_timezone: str | None = None
    delay_status: str = "UNKNOWN"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized
