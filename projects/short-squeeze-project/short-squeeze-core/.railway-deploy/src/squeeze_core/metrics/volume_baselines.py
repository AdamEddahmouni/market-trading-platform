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
    MetricResult,
    MetricUnit,
    ProviderScopeMode,
    SampleCounts,
    TrailingWindow,
)
from .selection import (
    MetricSelectionRequest,
    bar_end,
    bar_start,
    bar_volume_unit,
    resolve_bar_at_boundary,
    resolve_trailing_window,
)

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "trailing_mean_exclude_current.v1"

_INFO = "INFO"


@dataclass(frozen=True)
class VolumeBaselineRequest:
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


def compute_mean_volume(volumes: list[Decimal]) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        total = sum(volumes, Decimal(0))
        return total / Decimal(len(volumes))


def build_volume_baseline_result(
    observations: Iterable[Observation], request: VolumeBaselineRequest
) -> MetricResult:
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    # The target bar is resolved only to learn its volume unit (for cross-unit comparison) and
    # to record that it was deliberately excluded; it is never itself part of the window mean
    # when window.exclude_current_bar is set (the Phase 2A default).
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
                message="The current/target bar exists but is excluded from its own trailing baseline.",
                observation_ids=(target_resolution.observation.observation_id,),
            )
        )

    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    completeness: Completeness | None = None

    if window_resolution.used > 0 and window_resolution.used >= request.window.minimum_samples:
        volumes = [Decimal(obs.payload.volume) for obs in window_resolution.samples]
        value = compute_mean_volume(volumes)
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

    return MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
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
        value=value,
        unit=MetricUnit.SHARES,
        input_observation_ids=input_ids,
        input_bar_boundaries=boundaries,
        sample_counts=sample_counts,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
            completeness=completeness,
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )
