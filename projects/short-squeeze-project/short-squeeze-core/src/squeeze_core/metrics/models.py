from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.contracts.validation import require_aware_utc

from .diagnostics import MetricDiagnostic


class MetricName(StrEnum):
    ABSOLUTE_RETURN = "ABSOLUTE_RETURN"
    PERCENTAGE_RETURN = "PERCENTAGE_RETURN"
    ABSOLUTE_SESSION_GAP = "ABSOLUTE_SESSION_GAP"
    PERCENTAGE_SESSION_GAP = "PERCENTAGE_SESSION_GAP"
    ABSOLUTE_BAR_RANGE = "ABSOLUTE_BAR_RANGE"
    PERCENTAGE_BAR_RANGE = "PERCENTAGE_BAR_RANGE"
    MEAN_VOLUME_BASELINE = "MEAN_VOLUME_BASELINE"
    # Phase 2B: normalized market-activity metrics (docs/phase-2b-design.md). Additive only --
    # every member above is unchanged in value and meaning.
    RELATIVE_VOLUME = "RELATIVE_VOLUME"
    VOLUME_PERCENT_DEVIATION = "VOLUME_PERCENT_DEVIATION"
    VOLUME_Z_SCORE = "VOLUME_Z_SCORE"
    MEAN_PERCENTAGE_RETURN_BASELINE = "MEAN_PERCENTAGE_RETURN_BASELINE"
    PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE = "PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE"
    PERCENTAGE_RETURN_Z_SCORE = "PERCENTAGE_RETURN_Z_SCORE"
    # Phase 2C: short-interest and borrow-pressure metrics (docs/phase-2c-design.md).
    # Additive only -- every member above is unchanged in value and meaning.
    PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE = "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE = "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE"
    PUBLISHED_SHORT_INTEREST_REVISION_DELTA = "PUBLISHED_SHORT_INTEREST_REVISION_DELTA"
    DAYS_TO_COVER_COMPONENTS = "DAYS_TO_COVER_COMPONENTS"
    DAYS_TO_COVER = "DAYS_TO_COVER"
    BORROW_FEE_ABSOLUTE_CHANGE = "BORROW_FEE_ABSOLUTE_CHANGE"
    BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE = "BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE"
    BORROW_AVAILABILITY_ABSOLUTE_CHANGE = "BORROW_AVAILABILITY_ABSOLUTE_CHANGE"
    BORROW_AVAILABILITY_PERCENTAGE_CHANGE = "BORROW_AVAILABILITY_PERCENTAGE_CHANGE"


class MetricUnit(StrEnum):
    PRICE = "PRICE"
    PERCENT = "PERCENT"
    SHARES = "SHARES"
    UNKNOWN = "UNKNOWN"
    # Phase 2B additions -- additive only.
    RATIO = "RATIO"
    STANDARD_DEVIATIONS = "STANDARD_DEVIATIONS"
    # Phase 2C additions -- additive only.
    PERCENTAGE_POINTS = "PERCENTAGE_POINTS"
    DAYS = "DAYS"


class PriceField(StrEnum):
    OPEN = "OPEN"
    HIGH = "HIGH"
    LOW = "LOW"
    CLOSE = "CLOSE"


class ProviderScopeMode(StrEnum):
    SINGLE_PROVIDER = "SINGLE_PROVIDER"
    EXPLICIT_PROVIDER_SET_PRESERVED_SEPARATELY = "EXPLICIT_PROVIDER_SET_PRESERVED_SEPARATELY"


class WindowType(StrEnum):
    BAR_COUNT = "BAR_COUNT"
    TIME_RANGE = "TIME_RANGE"
    SESSION_COUNT = "SESSION_COUNT"
    # Phase 2B: used only by metrics.normalized_models.ReturnCountWindow, never by TrailingWindow
    # (whose validator below still only implements BAR_COUNT). Additive only.
    RETURN_COUNT = "RETURN_COUNT"


class BarBoundaryRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bar_start: datetime
    bar_end: datetime
    observation_id: str

    @field_validator("bar_start", "bar_end")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class TrailingWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_type: WindowType = WindowType.BAR_COUNT
    requested_count: int = Field(gt=0)
    exclude_current_bar: bool = True
    minimum_samples: int = Field(gt=0)

    @model_validator(mode="after")
    def minimum_not_above_requested(self) -> "TrailingWindow":
        if self.minimum_samples > self.requested_count:
            raise ValueError("minimum_samples cannot exceed requested_count")
        if self.window_type is not WindowType.BAR_COUNT:
            raise NotImplementedError(
                f"window_type {self.window_type.value} is not implemented in Phase 2A"
            )
        return self


class SampleCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requested: int = Field(ge=0)
    eligible: int = Field(ge=0)
    used: int = Field(ge=0)
    missing: int = Field(ge=0)

    @model_validator(mode="after")
    def used_plus_missing_equals_eligible(self) -> "SampleCounts":
        if self.used + self.missing != self.eligible:
            raise ValueError("used + missing must equal eligible")
        if self.used > self.requested:
            raise ValueError("used cannot exceed requested")
        return self


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: MetricName
    metric_version: str
    calculation_policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode
    provider: str | None = None
    price_field: PriceField | None = None
    window: TrailingWindow | None = None
    value: Decimal | None
    unit: MetricUnit
    input_observation_ids: tuple[str, ...] = ()
    input_bar_boundaries: tuple[BarBoundaryRef, ...] = ()
    sample_counts: SampleCounts | None = None
    quality: Quality
    diagnostics: tuple[MetricDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("input_observation_ids")
    @classmethod
    def sort_input_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("input_bar_boundaries")
    @classmethod
    def sort_boundaries(cls, value: tuple[BarBoundaryRef, ...]) -> tuple[BarBoundaryRef, ...]:
        return tuple(
            sorted(value, key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        )

    @model_validator(mode="after")
    def value_matches_quality(self) -> "MetricResult":
        if self.quality.state is QualityState.KNOWN_VALUE and self.value is None:
            raise ValueError("a KNOWN_VALUE result must carry a value")
        if self.quality.state is not QualityState.KNOWN_VALUE and self.value is not None:
            raise ValueError("a non-KNOWN_VALUE result must not carry a value")
        return self

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "MetricResult":
        if self.deterministic_id is None:
            from .identifiers import deterministic_metric_id, metric_identity

            object.__setattr__(self, "deterministic_id", deterministic_metric_id(metric_identity(self)))
        return self
