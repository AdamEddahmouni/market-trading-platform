from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.contracts.validation import require_aware_utc

from .diagnostics import MetricDiagnostic
from .models import MetricName, MetricUnit, ProviderScopeMode, SampleCounts, TrailingWindow
from .source_age import SourceAgeMetadata


class PressureMetricResult(BaseModel):
    """Shared result model for every Phase 2C metric except the days-to-cover component
    breakdown (DaysToCoverComponents, below). A wholly separate frozen model from
    MetricResult/NormalizedMetricResult -- see docs/phase-2c-design.md Section 2 for why
    MetricResult.source_interval being required makes it unsuitable for non-bar metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: MetricName
    metric_version: str
    calculation_policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    provider_scope: ProviderScopeMode
    provider: str | None = None
    volume_provider: str | None = None
    starting_observation_id: str | None = None
    ending_observation_id: str | None = None
    starting_reporting_period: date | None = None
    ending_reporting_period: date | None = None
    starting_source_age: SourceAgeMetadata | None = None
    ending_source_age: SourceAgeMetadata | None = None
    days_to_cover_components_id: str | None = None
    value: Decimal | None
    unit: MetricUnit
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
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

    @field_validator("input_metric_ids")
    @classmethod
    def sort_input_metric_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @model_validator(mode="after")
    def value_matches_quality(self) -> "PressureMetricResult":
        if self.quality.state is QualityState.KNOWN_VALUE and self.value is None:
            raise ValueError("a KNOWN_VALUE result must carry a value")
        if self.quality.state is not QualityState.KNOWN_VALUE and self.value is not None:
            raise ValueError("a non-KNOWN_VALUE result must not carry a value")
        return self

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "PressureMetricResult":
        if self.deterministic_id is None:
            from .pressure_identifiers import (
                deterministic_pressure_metric_id,
                pressure_metric_identity,
            )

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_pressure_metric_id(pressure_metric_identity(self)),
            )
        return self


class DaysToCoverComponents(BaseModel):
    """Structured, auditable days-to-cover breakdown with no scalar `value` (handoff Section
    10.4) -- every numerator/denominator assumption is a named field, not folded into one
    number. DAYS_TO_COVER (PressureMetricResult) references this via
    days_to_cover_components_id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_version: str
    calculation_policy_version: str
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    short_interest_provider: str
    short_interest_observation_id: str | None = None
    short_interest_reporting_period: date
    short_interest_value: int | None = None
    short_interest_unit: MetricUnit
    short_interest_source_age: SourceAgeMetadata | None = None
    volume_provider: str
    volume_baseline_metric_id: str | None = None
    volume_baseline_value: Decimal | None = None
    volume_unit: MetricUnit
    volume_interval: BarInterval
    volume_session_scope: tuple[BarSession, ...] = ()
    volume_window: TrailingWindow
    volume_sample_counts: SampleCounts | None = None
    input_observation_ids: tuple[str, ...] = ()
    input_metric_ids: tuple[str, ...] = ()
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

    @field_validator("input_metric_ids")
    @classmethod
    def sort_input_metric_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @model_validator(mode="after")
    def assign_deterministic_id(self) -> "DaysToCoverComponents":
        if self.deterministic_id is None:
            from .pressure_identifiers import (
                days_to_cover_components_identity,
                deterministic_days_to_cover_components_id,
            )

            object.__setattr__(
                self,
                "deterministic_id",
                deterministic_days_to_cover_components_id(days_to_cover_components_identity(self)),
            )
        return self
