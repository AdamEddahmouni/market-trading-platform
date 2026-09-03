from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.contracts.validation import require_aware_utc

from .diagnostics import MetricDiagnostic
from .models import (
    BarBoundaryRef,
    MetricName,
    MetricUnit,
    PriceField,
    ProviderScopeMode,
    SampleCounts,
    TrailingWindow,
    WindowType,
)


class StandardDeviationPolicy(StrEnum):
    """Only one policy is implemented in Phase 2B -- population, not sample. See
    docs/adr/0033-decimal-population-standard-deviation.md."""

    POPULATION_DECIMAL_V1 = "population_standard_deviation_decimal.v1"


class BaselineKind(StrEnum):
    VOLUME = "VOLUME"
    PERCENTAGE_RETURN = "PERCENTAGE_RETURN"


class ReturnCountWindow(BaseModel):
    """A trailing window sized in RETURNS, not bars -- a return count of N requires N+1 eligible
    bars (docs/phase-2b-design.md Section 6). Deliberately a separate model from TrailingWindow so
    TrailingWindow's Phase 2A "only BAR_COUNT is implemented" guarantee stays literally true."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_type: Literal[WindowType.RETURN_COUNT] = WindowType.RETURN_COUNT
    requested_count: int = Field(gt=0)
    exclude_current_bar: bool = True
    minimum_samples: int = Field(gt=0)

    @model_validator(mode="after")
    def minimum_not_above_requested(self) -> "ReturnCountWindow":
        if self.minimum_samples > self.requested_count:
            raise ValueError("minimum_samples cannot exceed requested_count")
        if not self.exclude_current_bar:
            raise NotImplementedError(
                "exclude_current_bar=False is not implemented for ReturnCountWindow in Phase 2B"
            )
        return self


class BaselineStatistics(BaseModel):
    """Mean/variance/standard-deviation over an explicit trailing distribution of volume samples
    or percentage-return samples. Never a MetricResult -- see docs/phase-2b-design.md Section 4
    for why this is a standalone model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_kind: BaselineKind
    baseline_version: str
    calculation_policy_version: str
    standard_deviation_policy: StandardDeviationPolicy
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode
    provider: str | None = None
    price_field: PriceField | None = None
    window: TrailingWindow | ReturnCountWindow
    sample_counts: SampleCounts
    mean: Decimal | None
    variance: Decimal | None
    standard_deviation: Decimal | None
    unit: MetricUnit
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    input_bar_boundaries: tuple[BarBoundaryRef, ...] = ()
    quality: Quality
    diagnostics: tuple[MetricDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("input_observation_ids", "input_metric_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("input_bar_boundaries")
    @classmethod
    def sort_boundaries(cls, value: tuple[BarBoundaryRef, ...]) -> tuple[BarBoundaryRef, ...]:
        return tuple(
            sorted(value, key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        )

    @model_validator(mode="after")
    def numeric_fields_match_quality(self) -> "BaselineStatistics":
        known = self.quality.state is QualityState.KNOWN_VALUE
        if known and (self.mean is None or self.variance is None or self.standard_deviation is None):
            raise ValueError("a KNOWN_VALUE baseline must carry mean, variance, and standard_deviation")
        if not known and (self.mean is not None or self.variance is not None or self.standard_deviation is not None):
            raise ValueError("a non-KNOWN_VALUE baseline must not carry mean, variance, or standard_deviation")
        return self

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "BaselineStatistics":
        if self.deterministic_id is None:
            from .normalized_identifiers import baseline_identity, deterministic_baseline_id

            object.__setattr__(self, "deterministic_id", deterministic_baseline_id(baseline_identity(self)))
        return self


class NormalizedMetricResult(BaseModel):
    """Result type for the six Phase 2B metrics. Deliberately not MetricResult -- see
    docs/phase-2b-design.md Section 2 (canonical_json.canonicalize() serializes every field of a
    BaseModel regardless of default, so extending MetricResult in place would change every
    already-anchored Phase 2A result's bytes)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: MetricName
    metric_version: str
    calculation_policy_version: str
    standard_deviation_policy: StandardDeviationPolicy | None = None
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode
    provider: str | None = None
    price_field: PriceField | None = None
    window: TrailingWindow | ReturnCountWindow | None = None
    target_boundary: BarBoundaryRef | None = None
    baseline_metric_id: str | None = None
    value: Decimal | None
    unit: MetricUnit
    input_observation_ids: tuple[str, ...] = ()
    input_bar_boundaries: tuple[BarBoundaryRef, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
    sample_counts: SampleCounts | None = None
    quality: Quality
    diagnostics: tuple[MetricDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("input_observation_ids", "input_metric_ids")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("input_bar_boundaries")
    @classmethod
    def sort_boundaries(cls, value: tuple[BarBoundaryRef, ...]) -> tuple[BarBoundaryRef, ...]:
        return tuple(
            sorted(value, key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        )

    @model_validator(mode="after")
    def value_matches_quality(self) -> "NormalizedMetricResult":
        if self.quality.state is QualityState.KNOWN_VALUE and self.value is None:
            raise ValueError("a KNOWN_VALUE result must carry a value")
        if self.quality.state is not QualityState.KNOWN_VALUE and self.value is not None:
            raise ValueError("a non-KNOWN_VALUE result must not carry a value")
        return self

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "NormalizedMetricResult":
        if self.deterministic_id is None:
            from .normalized_identifiers import deterministic_normalized_metric_id, normalized_metric_identity

            object.__setattr__(
                self, "deterministic_id", deterministic_normalized_metric_id(normalized_metric_identity(self))
            )
        return self
