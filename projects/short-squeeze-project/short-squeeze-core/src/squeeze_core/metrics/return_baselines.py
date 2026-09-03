from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Completeness, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricUnit, PriceField, ProviderScopeMode, SampleCounts
from .normalized_models import BaselineKind, BaselineStatistics, NormalizedMetricResult, ReturnCountWindow, StandardDeviationPolicy
from .returns import ReturnRequest, build_return_result
from .selection import (
    MetricSelectionRequest,
    _filter_by_provider,
    _group_by_boundary,
    _resolve_group,
    bar_end,
    bar_provider,
    bar_start,
    eligible_series,
)
from .statistics import DECIMAL_STATISTICS_PRECISION, population_standard_deviation

BASELINE_VERSION = "1.0.0"
DISTRIBUTION_CALCULATION_POLICY_VERSION = "adjacent_close_to_close_return_count.v1"
MEAN_METRIC_VERSION = "1.0.0"
STDDEV_METRIC_VERSION = "1.0.0"

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class ReturnBaselineRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    target_bar_start: datetime
    window: ReturnCountWindow
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None
    price_field: PriceField = PriceField.CLOSE


def _resolve_price_trailing_bars(
    observations: tuple[Observation, ...],
    selection_request: MetricSelectionRequest,
    *,
    target_start: datetime,
    requested_bar_count: int,
) -> tuple[list[Observation], list[MetricDiagnostic]]:
    """A price-only trailing-bar walk mirroring selection.resolve_trailing_window's boundary
    grouping and lifecycle resolution, without that function's volume-specific missing/unit
    filtering (a return baseline only needs CLOSE, never volume). Reuses selection.py's private
    boundary/lifecycle helpers directly rather than duplicating their logic -- the same
    "duplicate a small private helper rather than change the shared module's public surface"
    tradeoff ADR 0030 already accepts for _metadata_time. metrics/selection.py itself is not
    modified."""

    series = eligible_series(observations, selection_request)
    candidates = series.observations
    diagnostics: list[MetricDiagnostic] = []
    if selection_request.provider is None and selection_request.provider_scope is ProviderScopeMode.SINGLE_PROVIDER:
        providers = {bar_provider(item) for item in candidates}
        if len(providers) > 1:
            ids = tuple(sorted(item.observation_id for item in candidates))
            return [], [
                MetricDiagnostic(
                    code=MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER,
                    severity=_ERROR,
                    message="Multiple providers publish candidate bars; an explicit provider is required.",
                    observation_ids=ids,
                )
            ]
    filtered = _filter_by_provider(candidates, selection_request.provider)
    groups = _group_by_boundary(filtered)

    resolved: list[tuple[datetime, Observation | None, MetricDiagnostic | None]] = []
    for (start, _end), group in groups.items():
        if start >= target_start:
            continue
        observation, diagnostic = _resolve_group(group)
        resolved.append((start, observation, diagnostic))
    resolved.sort(key=lambda item: item[0], reverse=True)

    samples: list[Observation] = []
    for start, observation, diagnostic in resolved:
        if len(samples) >= requested_bar_count:
            break
        if observation is None:
            if diagnostic is not None:
                diagnostics.append(diagnostic)
            continue
        samples.append(observation)

    samples.sort(key=lambda item: (bar_start(item), item.observation_id))
    return samples, diagnostics


def build_return_distribution_statistics(
    observations: Iterable[Observation], request: ReturnBaselineRequest
) -> BaselineStatistics:
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    required_bars = request.window.requested_count + 1
    samples, diagnostics = _resolve_price_trailing_bars(
        observations, selection_request, target_start=request.target_bar_start, requested_bar_count=required_bars
    )

    returns: list[Decimal] = []
    return_metric_ids: set[str] = set()
    input_observation_ids: set[str] = set()
    input_boundaries: list[BarBoundaryRef] = []

    for start_obs, end_obs in zip(samples, samples[1:]):
        s0, s1 = bar_start(start_obs), bar_end(start_obs)
        e0, e1 = bar_start(end_obs), bar_end(end_obs)
        pair_result = build_return_result(
            observations,
            ReturnRequest(
                symbol=request.symbol,
                asset_class=request.asset_class,
                as_of=request.as_of,
                source_interval=request.source_interval,
                start_bar_start=s0,
                start_bar_end=s1,
                end_bar_start=e0,
                end_bar_end=e1,
                session_scope=request.session_scope,
                provider_scope=request.provider_scope,
                provider=request.provider,
                price_field=request.price_field,
            ),
            MetricName.PERCENTAGE_RETURN,
        )
        if pair_result.quality.state is not QualityState.KNOWN_VALUE:
            # Reuse Phase 2A's own diagnostics verbatim (METRIC_ZERO_DENOMINATOR,
            # METRIC_MISSING_START_PRICE/END_PRICE, RETURN_START/END_BAR_NOT_FOUND) rather than
            # synthesizing a new code that would duplicate the exact reason already computed by
            # build_return_result.
            diagnostics.extend(pair_result.diagnostics)
            continue
        returns.append(pair_result.value)
        return_metric_ids.add(pair_result.deterministic_id)
        input_observation_ids.update({start_obs.observation_id, end_obs.observation_id})
        input_boundaries.append(
            BarBoundaryRef(bar_start=s0, bar_end=s1, observation_id=start_obs.observation_id)
        )
        input_boundaries.append(
            BarBoundaryRef(bar_start=e0, bar_end=e1, observation_id=end_obs.observation_id)
        )

    mean: Decimal | None = None
    variance: Decimal | None = None
    standard_deviation: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    completeness: Completeness | None = None

    if len(samples) == 0:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_DISTRIBUTION_WINDOW_EMPTY,
                severity=_ERROR,
                message="No usable historical bar exists within the requested return-distribution window.",
            )
        )
    elif len(samples) < 2:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_DISTRIBUTION_INSUFFICIENT_BARS,
                severity=_ERROR,
                message="Fewer than two eligible bars were found; no historical return can be formed.",
                observation_ids=tuple(sorted(obs.observation_id for obs in samples)),
            )
        )
    elif len(returns) < request.window.minimum_samples:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_DISTRIBUTION_INSUFFICIENT_RETURNS,
                severity=_ERROR,
                message="Fewer usable historical returns were found than the required minimum.",
                observation_ids=tuple(sorted(input_observation_ids)),
            )
        )
    else:
        with localcontext() as ctx:
            ctx.prec = DECIMAL_STATISTICS_PRECISION
            mean, variance, standard_deviation = population_standard_deviation(returns)
        quality_state = QualityState.KNOWN_VALUE
        completeness = (
            Completeness.COMPLETE if len(returns) >= request.window.requested_count else Completeness.PARTIAL
        )

    sample_counts = SampleCounts(
        requested=request.window.requested_count,
        eligible=max(0, len(samples) - 1),
        used=len(returns),
        missing=max(0, len(samples) - 1) - len(returns),
    )

    return BaselineStatistics(
        baseline_kind=BaselineKind.PERCENTAGE_RETURN,
        baseline_version=BASELINE_VERSION,
        calculation_policy_version=DISTRIBUTION_CALCULATION_POLICY_VERSION,
        standard_deviation_policy=StandardDeviationPolicy.POPULATION_DECIMAL_V1,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
        price_field=request.price_field,
        window=request.window,
        sample_counts=sample_counts,
        mean=mean,
        variance=variance,
        standard_deviation=standard_deviation,
        unit=MetricUnit.PERCENT,
        input_observation_ids=tuple(sorted(input_observation_ids)),
        input_metric_ids=tuple(sorted(return_metric_ids)),
        input_bar_boundaries=tuple(
            sorted(set(input_boundaries), key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        ),
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
            completeness=completeness,
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )


def _wrap_baseline_component(
    distribution: BaselineStatistics, request: ReturnBaselineRequest, metric_name: MetricName, value: Decimal | None
) -> NormalizedMetricResult:
    quality_state = distribution.quality.state if value is not None else QualityState.UNAVAILABLE
    diagnostics = list(distribution.diagnostics)
    return NormalizedMetricResult(
        metric_name=metric_name,
        metric_version=MEAN_METRIC_VERSION if metric_name is MetricName.MEAN_PERCENTAGE_RETURN_BASELINE else STDDEV_METRIC_VERSION,
        calculation_policy_version=DISTRIBUTION_CALCULATION_POLICY_VERSION,
        standard_deviation_policy=None
        if metric_name is MetricName.MEAN_PERCENTAGE_RETURN_BASELINE
        else StandardDeviationPolicy.POPULATION_DECIMAL_V1,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
        price_field=request.price_field,
        window=request.window,
        baseline_metric_id=distribution.deterministic_id,
        value=value,
        unit=MetricUnit.PERCENT,
        input_observation_ids=distribution.input_observation_ids,
        input_bar_boundaries=distribution.input_bar_boundaries,
        input_metric_ids=distribution.input_metric_ids,
        sample_counts=distribution.sample_counts,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )


def build_mean_percentage_return_baseline_result(
    observations: Iterable[Observation], request: ReturnBaselineRequest
) -> NormalizedMetricResult:
    distribution = build_return_distribution_statistics(observations, request)
    return _wrap_baseline_component(
        distribution, request, MetricName.MEAN_PERCENTAGE_RETURN_BASELINE, distribution.mean
    )


def build_percentage_return_standard_deviation_baseline_result(
    observations: Iterable[Observation], request: ReturnBaselineRequest
) -> NormalizedMetricResult:
    distribution = build_return_distribution_statistics(observations, request)
    return _wrap_baseline_component(
        distribution,
        request,
        MetricName.PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE,
        distribution.standard_deviation,
    )
