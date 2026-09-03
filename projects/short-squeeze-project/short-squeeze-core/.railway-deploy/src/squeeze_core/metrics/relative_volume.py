from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricUnit, ProviderScopeMode, TrailingWindow
from .normalized_models import NormalizedMetricResult
from .selection import MetricSelectionRequest, bar_end, bar_start, resolve_bar_at_boundary
from .volume_baselines import VolumeBaselineRequest, build_volume_baseline_result

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "trailing_mean_ratio.v1"

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class RelativeVolumeRequest:
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


@dataclass(frozen=True)
class _ResolvedInputs:
    target_volume: Decimal | None
    baseline_mean: Decimal | None
    baseline_metric_id: str | None
    target_boundary: BarBoundaryRef | None
    input_observation_ids: tuple[str, ...]
    input_bar_boundaries: tuple[BarBoundaryRef, ...]
    diagnostics: list[MetricDiagnostic]
    quality_state: QualityState


def _resolve_inputs(observations: tuple[Observation, ...], request: RelativeVolumeRequest) -> _ResolvedInputs:
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    target_resolution = resolve_bar_at_boundary(
        observations, selection_request, target_start=request.target_bar_start, target_end=request.target_bar_end
    )
    diagnostics: list[MetricDiagnostic] = list(target_resolution.diagnostics)

    baseline_result = build_volume_baseline_result(
        observations,
        VolumeBaselineRequest(
            symbol=request.symbol,
            asset_class=request.asset_class,
            as_of=request.as_of,
            source_interval=request.source_interval,
            target_bar_start=request.target_bar_start,
            target_bar_end=request.target_bar_end,
            window=request.window,
            session_scope=request.session_scope,
            provider_scope=request.provider_scope,
            provider=request.provider,
        ),
    )

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

    diagnostics.extend(baseline_result.diagnostics)

    baseline_mean: Decimal | None = None
    baseline_metric_id: str | None = None
    if baseline_result.quality.state is not QualityState.KNOWN_VALUE:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RELATIVE_VOLUME_BASELINE_UNAVAILABLE,
                severity=_WARNING,
                message="The trailing mean-volume baseline is unavailable; no ratio can be computed.",
            )
        )
    else:
        baseline_metric_id = baseline_result.deterministic_id
        input_ids.update(baseline_result.input_observation_ids)
        boundaries.extend(baseline_result.input_bar_boundaries)
        if baseline_result.value == 0:
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.RELATIVE_VOLUME_BASELINE_ZERO,
                    severity=_ERROR,
                    message="The trailing mean-volume baseline is exactly zero; division is undefined.",
                )
            )
        else:
            baseline_mean = baseline_result.value

    quality_state = QualityState.UNAVAILABLE
    if target_volume is not None and baseline_mean is not None:
        quality_state = QualityState.KNOWN_VALUE
    elif baseline_result.quality.state is QualityState.KNOWN_VALUE and baseline_result.value == 0:
        quality_state = QualityState.INVALID

    return _ResolvedInputs(
        target_volume=target_volume,
        baseline_mean=baseline_mean,
        baseline_metric_id=baseline_metric_id,
        target_boundary=target_boundary,
        input_observation_ids=tuple(sorted(input_ids)),
        input_bar_boundaries=tuple(
            sorted(set(boundaries), key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        ),
        diagnostics=diagnostics,
        quality_state=quality_state,
    )


def compute_relative_volume(
    target_volume: Decimal | None, baseline_mean: Decimal | None
) -> Decimal | None:
    if target_volume is None or baseline_mean is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        return target_volume / baseline_mean


def compute_volume_percent_deviation(
    target_volume: Decimal | None, baseline_mean: Decimal | None
) -> Decimal | None:
    if target_volume is None or baseline_mean is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        return ((target_volume - baseline_mean) / baseline_mean) * Decimal(100)


def _build_result(
    observations: Iterable[Observation],
    request: RelativeVolumeRequest,
    metric_name: MetricName,
    unit: MetricUnit,
    formula,
) -> NormalizedMetricResult:
    observations = tuple(observations)
    resolved = _resolve_inputs(observations, request)
    value = formula(resolved.target_volume, resolved.baseline_mean) if resolved.quality_state is QualityState.KNOWN_VALUE else None

    return NormalizedMetricResult(
        metric_name=metric_name,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
        window=request.window,
        target_boundary=resolved.target_boundary,
        baseline_metric_id=resolved.baseline_metric_id,
        value=value,
        unit=unit,
        input_observation_ids=resolved.input_observation_ids,
        input_bar_boundaries=resolved.input_bar_boundaries,
        input_metric_ids=() if resolved.baseline_metric_id is None else (resolved.baseline_metric_id,),
        quality=Quality(
            state=resolved.quality_state,
            reasons=()
            if resolved.quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in resolved.diagnostics})),
        ),
        diagnostics=sort_diagnostics(resolved.diagnostics),
    )


def build_relative_volume_result(
    observations: Iterable[Observation], request: RelativeVolumeRequest
) -> NormalizedMetricResult:
    return _build_result(
        observations, request, MetricName.RELATIVE_VOLUME, MetricUnit.RATIO, compute_relative_volume
    )


def build_volume_percent_deviation_result(
    observations: Iterable[Observation], request: RelativeVolumeRequest
) -> NormalizedMetricResult:
    return _build_result(
        observations,
        request,
        MetricName.VOLUME_PERCENT_DEVIATION,
        MetricUnit.PERCENT,
        compute_volume_percent_deviation,
    )
