from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricResult, MetricUnit, PriceField, ProviderScopeMode
from .selection import MetricSelectionRequest, resolve_bar_at_boundary

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "close_to_close_completed.v1"

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class ReturnRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    start_bar_start: datetime
    start_bar_end: datetime
    end_bar_start: datetime
    end_bar_end: datetime
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None
    price_field: PriceField = PriceField.CLOSE


def compute_absolute_return(
    start_price: Decimal | None, end_price: Decimal | None
) -> tuple[Decimal | None, MetricDiagnosticCode | None]:
    if start_price is None:
        return None, MetricDiagnosticCode.METRIC_MISSING_START_PRICE
    if end_price is None:
        return None, MetricDiagnosticCode.METRIC_MISSING_END_PRICE
    return end_price - start_price, None


def compute_percentage_return(
    start_price: Decimal | None, end_price: Decimal | None
) -> tuple[Decimal | None, MetricDiagnosticCode | None]:
    if start_price is None:
        return None, MetricDiagnosticCode.METRIC_MISSING_START_PRICE
    if end_price is None:
        return None, MetricDiagnosticCode.METRIC_MISSING_END_PRICE
    if start_price == 0:
        return None, MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR
    with localcontext() as ctx:
        ctx.prec = 28
        return ((end_price - start_price) / start_price) * Decimal(100), None


def _price(observation: Observation, field: PriceField) -> Decimal | None:
    return getattr(observation.payload, field.value.lower(), None)


def _boundary_ref(observation: Observation) -> BarBoundaryRef:
    from .selection import bar_end, bar_start

    return BarBoundaryRef(
        bar_start=bar_start(observation), bar_end=bar_end(observation), observation_id=observation.observation_id
    )


def build_return_result(
    observations: Iterable[Observation], request: ReturnRequest, metric_name: MetricName
) -> MetricResult:
    if metric_name not in (MetricName.ABSOLUTE_RETURN, MetricName.PERCENTAGE_RETURN):
        raise ValueError(f"unsupported return metric_name: {metric_name}")
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    start_resolution = resolve_bar_at_boundary(
        observations, selection_request, target_start=request.start_bar_start, target_end=request.start_bar_end
    )
    end_resolution = resolve_bar_at_boundary(
        observations, selection_request, target_start=request.end_bar_start, target_end=request.end_bar_end
    )

    diagnostics: list[MetricDiagnostic] = list(start_resolution.diagnostics) + list(end_resolution.diagnostics)
    if start_resolution.observation is None and any(
        d.code is MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS for d in start_resolution.diagnostics
    ):
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_START_BAR_NOT_FOUND,
                severity=_WARNING,
                message="No eligible bar exists at the requested starting boundary.",
            )
        )
    if end_resolution.observation is None and any(
        d.code is MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS for d in end_resolution.diagnostics
    ):
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_END_BAR_NOT_FOUND,
                severity=_WARNING,
                message="No eligible bar exists at the requested ending boundary.",
            )
        )

    start_obs = start_resolution.observation
    end_obs = end_resolution.observation
    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE

    if start_obs is not None and end_obs is not None:
        if start_obs.observation_id == end_obs.observation_id:
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.RETURN_IDENTICAL_INPUT_BAR,
                    severity=_INFO,
                    message="The same bar was used as both the starting and ending observation.",
                    observation_ids=(start_obs.observation_id,),
                )
            )
        start_price = _price(start_obs, request.price_field)
        end_price = _price(end_obs, request.price_field)
        if metric_name is MetricName.ABSOLUTE_RETURN:
            value, code = compute_absolute_return(start_price, end_price)
        else:
            value, code = compute_percentage_return(start_price, end_price)
        if code is None:
            quality_state = QualityState.KNOWN_VALUE
        else:
            quality_state = (
                QualityState.INVALID
                if code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR
                else QualityState.UNAVAILABLE
            )
            severity = _ERROR if code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR else _WARNING
            diagnostics.append(
                MetricDiagnostic(
                    code=code,
                    severity=severity,
                    message="The requested price field could not be used to compute a return.",
                    observation_ids=tuple(sorted({start_obs.observation_id, end_obs.observation_id})),
                )
            )

    input_ids = tuple(sorted({obs.observation_id for obs in (start_obs, end_obs) if obs is not None}))
    boundaries = tuple(_boundary_ref(obs) for obs in (start_obs, end_obs) if obs is not None)

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
        price_field=request.price_field,
        value=value,
        unit=MetricUnit.PRICE if metric_name is MetricName.ABSOLUTE_RETURN else MetricUnit.PERCENT,
        input_observation_ids=input_ids,
        input_bar_boundaries=boundaries,
        quality=Quality(
            state=quality_state,
            reasons=() if quality_state is QualityState.KNOWN_VALUE else tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )
