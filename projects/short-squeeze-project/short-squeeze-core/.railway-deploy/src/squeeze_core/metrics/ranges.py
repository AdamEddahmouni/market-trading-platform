from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricResult, MetricUnit, ProviderScopeMode
from .selection import MetricSelectionRequest, bar_end, bar_start, resolve_bar_at_boundary

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "low_denominator_range.v1"

_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class RangeRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    target_bar_start: datetime
    target_bar_end: datetime
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None


def compute_absolute_range(high: Decimal, low: Decimal) -> Decimal:
    return high - low


def compute_percentage_range(
    high: Decimal, low: Decimal
) -> tuple[Decimal | None, MetricDiagnosticCode | None]:
    if low == 0:
        return None, MetricDiagnosticCode.RANGE_ZERO_DENOMINATOR
    with localcontext() as ctx:
        ctx.prec = 28
        return ((high - low) / low) * Decimal(100), None


def build_range_result(
    observations: Iterable[Observation], request: RangeRequest, metric_name: MetricName
) -> MetricResult:
    if metric_name not in (MetricName.ABSOLUTE_BAR_RANGE, MetricName.PERCENTAGE_BAR_RANGE):
        raise ValueError(f"unsupported range metric_name: {metric_name}")
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    resolution = resolve_bar_at_boundary(
        observations,
        selection_request,
        target_start=request.target_bar_start,
        target_end=request.target_bar_end,
    )
    diagnostics: list[MetricDiagnostic] = list(resolution.diagnostics)
    bar = resolution.observation
    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    input_ids: tuple[str, ...] = ()
    boundaries: tuple[BarBoundaryRef, ...] = ()

    if bar is not None:
        # A partial bar is already excluded upstream by selection._resolve_group; this branch
        # only ever sees a COMPLETED or CORRECTED bar.
        high = bar.payload.high
        low = bar.payload.low
        if metric_name is MetricName.ABSOLUTE_BAR_RANGE:
            value = compute_absolute_range(high, low)
            quality_state = QualityState.KNOWN_VALUE
        else:
            value, code = compute_percentage_range(high, low)
            if code is None:
                quality_state = QualityState.KNOWN_VALUE
            else:
                quality_state = QualityState.INVALID
                diagnostics.append(
                    MetricDiagnostic(
                        code=code,
                        severity=_ERROR,
                        message="The bar's low is zero and cannot be used as a range denominator.",
                        observation_ids=(bar.observation_id,),
                    )
                )
        input_ids = (bar.observation_id,)
        boundaries = (
            BarBoundaryRef(
                bar_start=bar_start(bar), bar_end=bar_end(bar), observation_id=bar.observation_id
            ),
        )
    elif any(d.code is MetricDiagnosticCode.METRIC_PARTIAL_INPUT for d in resolution.diagnostics):
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RANGE_PARTIAL_BAR_UNSUPPORTED,
                severity=_WARNING,
                message="A completed-bar range cannot be computed from a partial bar.",
            )
        )

    return MetricResult(
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
        value=value,
        unit=MetricUnit.PRICE if metric_name is MetricName.ABSOLUTE_BAR_RANGE else MetricUnit.PERCENT,
        input_observation_ids=input_ids,
        input_bar_boundaries=boundaries,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )
