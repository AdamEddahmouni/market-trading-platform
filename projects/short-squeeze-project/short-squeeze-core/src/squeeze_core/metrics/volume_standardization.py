from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Completeness, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import (
    BarBoundaryRef,
    MetricName,
    MetricUnit,
    ProviderScopeMode,
    SampleCounts,
    TrailingWindow,
)
from .normalized_models import BaselineKind, BaselineStatistics, NormalizedMetricResult, StandardDeviationPolicy
from .selection import (
    MetricSelectionRequest,
    bar_end,
    bar_start,
    bar_volume_unit,
    resolve_bar_at_boundary,
    resolve_trailing_window,
)
from .statistics import DECIMAL_STATISTICS_PRECISION, population_standard_deviation
from .volume_baselines import compute_mean_volume

BASELINE_VERSION = "1.0.0"
DISTRIBUTION_CALCULATION_POLICY_VERSION = "trailing_bar_count_exclude_current.v1"
METRIC_VERSION = "1.0.0"
METRIC_CALCULATION_POLICY_VERSION = "volume_distribution_z_score.v1"

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class VolumeZScoreRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    target_bar_start: datetime
    target_bar_end: datetime
    window: TrailingWindow
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None


def build_volume_distribution_statistics(
    observations: Iterable[Observation], request: VolumeZScoreRequest
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
    target_resolution = resolve_bar_at_boundary(
        observations,
        selection_request,
        target_start=request.target_bar_start,
        target_end=request.target_bar_end,
    )
    target_volume_unit = (
        None if target_resolution.observation is None else bar_volume_unit(target_resolution.observation)
    )

    window_resolution = resolve_trailing_window(
        observations,
        selection_request,
        target_start=request.target_bar_start,
        window=request.window,
        target_volume_unit=target_volume_unit,
    )
    diagnostics: list[MetricDiagnostic] = list(window_resolution.diagnostics)
    if request.window.exclude_current_bar and target_resolution.observation is not None:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_BASELINE_CURRENT_BAR_EXCLUDED,
                severity=_INFO,
                message="The current/target bar exists but is excluded from its own volume distribution.",
                observation_ids=(target_resolution.observation.observation_id,),
            )
        )

    mean: Decimal | None = None
    variance: Decimal | None = None
    standard_deviation: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    completeness: Completeness | None = None

    if not window_resolution.samples:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_DISTRIBUTION_WINDOW_EMPTY,
                severity=_ERROR,
                message="No usable bar exists within the requested volume-distribution window.",
            )
        )
    elif window_resolution.used < request.window.minimum_samples:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_DISTRIBUTION_INSUFFICIENT_SAMPLES,
                severity=_ERROR,
                message="Fewer usable volume samples were found than the required minimum.",
                observation_ids=tuple(sorted(obs.observation_id for obs in window_resolution.samples)),
            )
        )
    else:
        volumes = [Decimal(obs.payload.volume) for obs in window_resolution.samples]
        mean = compute_mean_volume(volumes)
        with localcontext() as ctx:
            ctx.prec = DECIMAL_STATISTICS_PRECISION
            _, variance, standard_deviation = population_standard_deviation(volumes)
        quality_state = QualityState.KNOWN_VALUE
        completeness = (
            Completeness.COMPLETE
            if window_resolution.used >= window_resolution.requested
            else Completeness.PARTIAL
        )

    input_ids = tuple(sorted(obs.observation_id for obs in window_resolution.samples))
    boundaries = tuple(
        sorted(
            (
                BarBoundaryRef(
                    bar_start=bar_start(obs), bar_end=bar_end(obs), observation_id=obs.observation_id
                )
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

    return BaselineStatistics(
        baseline_kind=BaselineKind.VOLUME,
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
        window=request.window,
        sample_counts=sample_counts,
        mean=mean,
        variance=variance,
        standard_deviation=standard_deviation,
        unit=MetricUnit.SHARES,
        input_observation_ids=input_ids,
        input_bar_boundaries=boundaries,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
            completeness=completeness,
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )


def compute_volume_z_score(target_volume: Decimal, mean: Decimal, standard_deviation: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        return (target_volume - mean) / standard_deviation


def build_volume_z_score_result(
    observations: Iterable[Observation], request: VolumeZScoreRequest
) -> NormalizedMetricResult:
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    target_resolution = resolve_bar_at_boundary(
        observations,
        selection_request,
        target_start=request.target_bar_start,
        target_end=request.target_bar_end,
    )
    diagnostics: list[MetricDiagnostic] = list(target_resolution.diagnostics)

    target_obs = target_resolution.observation
    target_boundary: BarBoundaryRef | None = None
    target_volume: Decimal | None = None
    input_ids: set[str] = set()
    boundaries: list[BarBoundaryRef] = []

    if target_obs is None:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RELATIVE_VOLUME_TARGET_NOT_FOUND,
                severity=_WARNING,
                message="No eligible bar exists at the requested target boundary.",
            )
        )
    else:
        target_boundary = BarBoundaryRef(
            bar_start=bar_start(target_obs), bar_end=bar_end(target_obs), observation_id=target_obs.observation_id
        )
        input_ids.add(target_obs.observation_id)
        boundaries.append(target_boundary)
        if target_obs.payload.volume is None:
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.RELATIVE_VOLUME_TARGET_MISSING_VOLUME,
                    severity=_WARNING,
                    message="The target bar has no recorded volume; it is missing, not zero.",
                    observation_ids=(target_obs.observation_id,),
                )
            )
        else:
            target_volume = Decimal(target_obs.payload.volume)

    distribution = build_volume_distribution_statistics(observations, request)
    diagnostics.extend(distribution.diagnostics)
    input_ids.update(distribution.input_observation_ids)
    boundaries.extend(distribution.input_bar_boundaries)

    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    if target_volume is None:
        pass
    elif distribution.quality.state is not QualityState.KNOWN_VALUE:
        pass
    elif distribution.standard_deviation == 0:
        quality_state = QualityState.INVALID
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.NORMALIZED_METRIC_ZERO_VARIANCE,
                severity=_ERROR,
                message="The volume distribution's standard deviation is exactly zero; a z-score is undefined.",
            )
        )
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_DISTRIBUTION_ZERO_VARIANCE,
                severity=_ERROR,
                message="The volume distribution's standard deviation is exactly zero; a z-score is undefined.",
            )
        )
    else:
        value = compute_volume_z_score(target_volume, distribution.mean, distribution.standard_deviation)
        quality_state = QualityState.KNOWN_VALUE

    input_metric_ids = () if distribution.deterministic_id is None else (distribution.deterministic_id,)

    return NormalizedMetricResult(
        metric_name=MetricName.VOLUME_Z_SCORE,
        metric_version=METRIC_VERSION,
        calculation_policy_version=METRIC_CALCULATION_POLICY_VERSION,
        standard_deviation_policy=StandardDeviationPolicy.POPULATION_DECIMAL_V1,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
        window=request.window,
        target_boundary=target_boundary,
        baseline_metric_id=distribution.deterministic_id,
        value=value,
        unit=MetricUnit.STANDARD_DEVIATIONS,
        input_observation_ids=tuple(sorted(input_ids)),
        input_bar_boundaries=tuple(
            sorted(set(boundaries), key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        ),
        input_metric_ids=input_metric_ids,
        sample_counts=distribution.sample_counts,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )
