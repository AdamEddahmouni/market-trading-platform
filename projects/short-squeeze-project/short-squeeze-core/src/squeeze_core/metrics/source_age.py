from datetime import UTC, date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import Observation
from squeeze_core.contracts.validation import require_aware_utc


class SourceAgeMetadata(BaseModel):
    """Two distinct age concepts, kept separate (docs/phase-2c-design.md Section 4):
    `availability_age_seconds` (evidence freshness -- how long ago this became usable) and
    `reporting_period_age_days` (report staleness -- how old the underlying fact is,
    independent of when it was received). Age is metadata, never a gate or a score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_publication_time: datetime
    local_receipt_time: datetime
    effective_time: datetime
    availability_age_seconds: int = Field(ge=0)
    reporting_period_end: date | None = None
    reporting_period_age_days: int | None = Field(default=None, ge=0)
    publication_lag_seconds: int | None = Field(default=None, ge=0)

    @field_validator("provider_publication_time", "local_receipt_time", "effective_time")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


def build_source_age(
    observation: Observation,
    as_of: datetime,
    *,
    reporting_period_end: date | None = None,
) -> SourceAgeMetadata:
    """Builds age metadata for one resolved observation. `reporting_period_end` is the
    published short-interest settlement date; omitted for borrow observations, which have no
    reporting-period concept (docs/phase-2c-design.md Section 3)."""

    effective_time = observation.effective_timestamp
    availability_age_seconds = int((as_of - effective_time).total_seconds())

    reporting_period_age_days: int | None = None
    publication_lag_seconds: int | None = None
    if reporting_period_end is not None:
        reporting_period_age_days = (as_of.date() - reporting_period_end).days
        reporting_period_midnight = datetime.combine(reporting_period_end, time.min, tzinfo=UTC)
        publication_lag_seconds = int(
            (observation.source_timestamp - reporting_period_midnight).total_seconds()
        )

    return SourceAgeMetadata(
        provider_publication_time=observation.source_timestamp,
        local_receipt_time=observation.received_timestamp,
        effective_time=effective_time,
        availability_age_seconds=availability_age_seconds,
        reporting_period_end=reporting_period_end,
        reporting_period_age_days=reporting_period_age_days,
        publication_lag_seconds=publication_lag_seconds,
    )
