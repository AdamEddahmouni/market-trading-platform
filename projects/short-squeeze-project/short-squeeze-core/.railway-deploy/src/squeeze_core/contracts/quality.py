from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import Completeness, QualityState, SourceHealth
from .validation import require_aware_utc


class Quality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: QualityState
    reasons: tuple[str, ...] = ()
    evaluated_at: datetime | None = None
    age_ms: int | None = Field(default=None, ge=0)
    expected_delay_ms: int | None = Field(default=None, ge=0)
    source_health: SourceHealth | None = None
    completeness: Completeness | None = None
    confidence: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @model_validator(mode="after")
    def require_reason_for_non_known_state(self) -> "Quality":
        if self.state is not QualityState.KNOWN_VALUE and not self.reasons:
            raise ValueError("a reason is required for a non-known quality state")
        return self

