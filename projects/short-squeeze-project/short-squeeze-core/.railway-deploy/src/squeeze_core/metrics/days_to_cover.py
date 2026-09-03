from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Completeness, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import (
    BarBoundaryRef,
    MetricName,
    MetricResult,
    MetricUnit,
    ProviderScopeMode,
    SampleCounts,
    TrailingWindow,
)
from .pressure_models import DaysToCoverComponents, PressureMetricResult
from .pressure_selection import PressureSelectionRequest, resolve_short_interest_at_period
from .selection import MetricSelectionRequest, bar_end, bar_start, resolve_trailing_window
from .source_age import build_source_age
from .volume_baselines import compute_mean_volume

COMPONENT_VERSION = "1.0.0"
METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = (
    "published_short_interest_divided_by_trailing_mean_completed_daily_share_volume.v1"
)
VOLUME_BASELINE_POLICY_VERSION = "trailing_mean_exclude_current.v1"

_ERROR = "ERROR"
_WARNING = "WARNING"


@dataclass(frozen=True)
class DaysToCoverRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    short_interest_provider: str
    short_interest_reporting_period: date
    volume_provider: str
    volume_interval: BarInterval
    volume_window: TrailingWindow
    volume_session_scope: tuple[BarSession, ...] = ()


def _build_volume_baseline(
    observations: tuple[Observation, ...], request: DaysToCoverRequest
) -> tuple[MetricResult | None, tuple[MetricDiagnostic, ...]]:
    """Reuses Phase 2A's resolve_trailing_window + compute_mean_volume directly, walking
    backward from target_start=as_of (there is no single "target bar" for days to cover to
    exclude via resolve_bar_at_boundary -- see docs/phase-2c-design.md Section 8.3). The
    resulting mean is wrapped in a real Phase 2A MetricResult (identical construction to
    volume_baselines.build_volume_baseline_result's own MEAN_VOLUME_BASELINE output) purely so
    a genuine, independently verifiable Phase 2A metric ID is available to reference."""

    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.volume_interval,
        session_scope=request.volume_session_scope,
        provider=request.volume_provider,
    )
    window_resolution = resolve_trailing_window(
        observations,
        selection_request,
        target_start=request.as_of,
        window=request.volume_window,
        target_volume_unit=None,
    )
    diagnostics: list[MetricDiagnostic] = list(window_resolution.diagnostics)

    if window_resolution.used == 0 or window_resolution.used < request.volume_window.minimum_samples:
        return None, tuple(diagnostics)

    volumes = [Decimal(obs.payload.volume) for obs in window_resolution.samples]
    mean_volume = compute_mean_volume(volumes)
    input_ids = tuple(sorted(obs.observation_id for obs in window_resolution.samples))
    boundaries = tuple(
        sorted(
            (
                BarBoundaryRef(bar_start=bar_start(obs), bar_end=bar_end(obs), observation_id=obs.observation_id)
                for obs in window_resolution.samples
            ),
            key=lambda item: item.bar_start,
        )
    )
    sample_counts = SampleCounts(
        requested=window_resolution.requested,
        eligible=window_resolution.eligible,
        used=window_resolution.used,
        missing=window_resolution.missing,
    )
    completeness = (
        Completeness.COMPLETE if window_resolution.used >= window_resolution.requested else Completeness.PARTIAL
    )
    volume_result = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version=METRIC_VERSION,
        calculation_policy_version=VOLUME_BASELINE_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.volume_interval,
        session_scope=request.volume_session_scope,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.volume_provider,
        window=request.volume_window,
        value=mean_volume,
        unit=MetricUnit.SHARES,
        input_observation_ids=input_ids,
        input_bar_boundaries=boundaries,
        sample_counts=sample_counts,
        quality=Quality(state=QualityState.KNOWN_VALUE, completeness=completeness),
        diagnostics=(),
    )
    return volume_result, tuple(diagnostics)


def build_days_to_cover_components(
    observations: Iterable[Observation], request: DaysToCoverRequest
) -> DaysToCoverComponents:
    observations = tuple(observations)
    diagnostics: list[MetricDiagnostic] = []

    if request.volume_interval is not BarInterval.ONE_DAY:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL,
                severity=_ERROR,
                message="Days to cover requires the daily bar interval under this policy; no other interval is supported.",
            )
        )
        return _components_result(
            request, diagnostics=diagnostics, short_interest=None, volume_result=None
        )

    short_interest_request = PressureSelectionRequest(
        symbol=request.symbol, as_of=request.as_of, provider=request.short_interest_provider
    )
    short_interest_resolution = resolve_short_interest_at_period(
        observations,
        short_interest_request,
        reporting_period=request.short_interest_reporting_period,
        not_found_code=MetricDiagnosticCode.DAYS_TO_COVER_SHORT_INTEREST_NOT_FOUND,
    )
    diagnostics.extend(short_interest_resolution.diagnostics)
    short_interest = short_interest_resolution.observation

    volume_result, volume_diagnostics = _build_volume_baseline(observations, request)
    diagnostics.extend(volume_diagnostics)

    if volume_result is None:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.DAYS_TO_COVER_VOLUME_BASELINE_UNAVAILABLE,
                severity=_WARNING,
                message="No usable trailing daily volume baseline could be computed for the requested window.",
            )
        )
    elif volume_result.value == 0:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.DAYS_TO_COVER_ZERO_VOLUME_BASELINE,
                severity=_ERROR,
                message="Trailing mean daily volume is zero; days to cover cannot be computed.",
                observation_ids=tuple(volume_result.input_observation_ids),
            )
        )

    return _components_result(
        request, diagnostics=diagnostics, short_interest=short_interest, volume_result=volume_result
    )


def _components_result(
    request: DaysToCoverRequest,
    *,
    diagnostics: list[MetricDiagnostic],
    short_interest: Observation | None,
    volume_result: MetricResult | None,
) -> DaysToCoverComponents:
    sorted_diagnostics = sort_diagnostics(diagnostics)
    codes = {item.code for item in sorted_diagnostics}

    observation_ids: set[str] = set()
    if short_interest is not None:
        observation_ids.add(short_interest.observation_id)
    if volume_result is not None:
        observation_ids.update(volume_result.input_observation_ids)

    metric_ids: set[str] = set()
    if volume_result is not None and volume_result.deterministic_id is not None:
        metric_ids.add(volume_result.deterministic_id)

    usable = (
        short_interest is not None
        and volume_result is not None
        and volume_result.value is not None
        and volume_result.value != 0
    )
    if usable:
        state = QualityState.KNOWN_VALUE
    elif codes & {
        MetricDiagnosticCode.DAYS_TO_COVER_ZERO_VOLUME_BASELINE,
        MetricDiagnosticCode.DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL,
    }:
        state = QualityState.INVALID
    elif codes & {MetricDiagnosticCode.PRESSURE_METRIC_CONFLICTED_INPUT}:
        state = QualityState.CONFLICTED
    else:
        state = QualityState.UNAVAILABLE

    return DaysToCoverComponents(
        component_version=COMPONENT_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        short_interest_provider=request.short_interest_provider,
        short_interest_observation_id=None if short_interest is None else short_interest.observation_id,
        short_interest_reporting_period=request.short_interest_reporting_period,
        short_interest_value=None if short_interest is None else short_interest.payload.short_shares,
        short_interest_unit=MetricUnit.SHARES,
        short_interest_source_age=None
        if short_interest is None
        else build_source_age(
            short_interest, request.as_of, reporting_period_end=short_interest.payload.settlement_date
        ),
        volume_provider=request.volume_provider,
        volume_baseline_metric_id=None if volume_result is None else volume_result.deterministic_id,
        volume_baseline_value=None if volume_result is None else volume_result.value,
        volume_unit=MetricUnit.SHARES,
        volume_interval=request.volume_interval,
        volume_session_scope=request.volume_session_scope,
        volume_window=request.volume_window,
        volume_sample_counts=None if volume_result is None else volume_result.sample_counts,
        input_observation_ids=tuple(sorted(observation_ids)),
        input_metric_ids=tuple(sorted(metric_ids)),
        quality=Quality(
            state=state,
            reasons=() if state is QualityState.KNOWN_VALUE else tuple(sorted({c.value for c in codes})),
        ),
        diagnostics=sorted_diagnostics,
    )


def build_days_to_cover_result(
    observations: Iterable[Observation], request: DaysToCoverRequest
) -> PressureMetricResult:
    components = build_days_to_cover_components(observations, request)

    value: Decimal | None = None
    if components.quality.state is QualityState.KNOWN_VALUE:
        with localcontext() as ctx:
            ctx.prec = 28
            value = Decimal(components.short_interest_value) / components.volume_baseline_value

    input_ids = set(components.input_observation_ids)
    metric_ids = set(components.input_metric_ids)
    metric_ids.add(components.deterministic_id)

    return PressureMetricResult(
        metric_name=MetricName.DAYS_TO_COVER,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.short_interest_provider,
        volume_provider=request.volume_provider,
        starting_observation_id=components.short_interest_observation_id,
        ending_observation_id=None,
        starting_reporting_period=components.short_interest_reporting_period,
        ending_reporting_period=None,
        starting_source_age=components.short_interest_source_age,
        ending_source_age=None,
        days_to_cover_components_id=components.deterministic_id,
        value=value,
        unit=MetricUnit.DAYS,
        input_observation_ids=tuple(sorted(input_ids)),
        input_metric_ids=tuple(sorted(metric_ids)),
        quality=components.quality,
        diagnostics=components.diagnostics,
    )
