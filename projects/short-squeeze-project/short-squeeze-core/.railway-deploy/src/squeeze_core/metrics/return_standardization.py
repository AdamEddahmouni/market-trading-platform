from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricUnit, PriceField, ProviderScopeMode
from .normalized_models import NormalizedMetricResult, ReturnCountWindow, StandardDeviationPolicy
from .return_baselines import ReturnBaselineRequest, build_return_distribution_statistics
from .returns import ReturnRequest, build_return_result
from .statistics import DECIMAL_STATISTICS_PRECISION

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "return_distribution_z_score.v1"

_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class ReturnZScoreRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    target_start_bar_start: datetime
    target_start_bar_end: datetime
    target_end_bar_start: datetime
    target_end_bar_end: datetime
    window: ReturnCountWindow
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None
    price_field: PriceField = PriceField.CLOSE


def compute_percentage_return_z_score(
    target_return: Decimal, mean: Decimal, standard_deviation: Decimal
) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        return (target_return - mean) / standard_deviation


def build_percentage_return_z_score_result(
    observations: Iterable[Observation], request: ReturnZScoreRequest
) -> NormalizedMetricResult:
    observations = tuple(observations)

    target_result = build_return_result(
        observations,
        ReturnRequest(
            symbol=request.symbol,
            asset_class=request.asset_class,
            as_of=request.as_of,
            source_interval=request.source_interval,
            start_bar_start=request.target_start_bar_start,
            start_bar_end=request.target_start_bar_end,
            end_bar_start=request.target_end_bar_start,
            end_bar_end=request.target_end_bar_end,
            session_scope=request.session_scope,
            provider_scope=request.provider_scope,
            provider=request.provider,
            price_field=request.price_field,
        ),
        MetricName.PERCENTAGE_RETURN,
    )

    diagnostics: list[MetricDiagnostic] = list(target_result.diagnostics)
    if target_result.quality.state is not QualityState.KNOWN_VALUE:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_TARGET_NOT_FOUND,
                severity=_WARNING,
                message="The target percentage return could not be computed.",
            )
        )

    baseline_request = ReturnBaselineRequest(
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        source_interval=request.source_interval,
        target_bar_start=request.target_start_bar_start,
        window=request.window,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
        price_field=request.price_field,
    )
    distribution = build_return_distribution_statistics(observations, baseline_request)
    diagnostics.extend(distribution.diagnostics)

    target_boundary = None
    input_ids = set(target_result.input_observation_ids) | set(distribution.input_observation_ids)
    boundaries = list(target_result.input_bar_boundaries) + list(distribution.input_bar_boundaries)
    if target_result.input_bar_boundaries:
        end_ref = max(target_result.input_bar_boundaries, key=lambda item: item.bar_start)
        target_boundary = end_ref

    input_metric_ids: set[str] = set(distribution.input_metric_ids)
    if target_result.quality.state is QualityState.KNOWN_VALUE:
        input_metric_ids.add(target_result.deterministic_id)
    if distribution.deterministic_id is not None:
        input_metric_ids.add(distribution.deterministic_id)

    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    if target_result.quality.state is not QualityState.KNOWN_VALUE:
        pass
    elif distribution.quality.state is not QualityState.KNOWN_VALUE:
        pass
    elif distribution.standard_deviation == 0:
        quality_state = QualityState.INVALID
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.NORMALIZED_METRIC_ZERO_VARIANCE,
                severity=_ERROR,
                message="The historical percentage-return distribution's standard deviation is exactly zero; a z-score is undefined.",
            )
        )
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_DISTRIBUTION_ZERO_VARIANCE,
                severity=_ERROR,
                message="The historical percentage-return distribution's standard deviation is exactly zero; a z-score is undefined.",
            )
        )
    else:
        value = compute_percentage_return_z_score(target_result.value, distribution.mean, distribution.standard_deviation)
        quality_state = QualityState.KNOWN_VALUE

    return NormalizedMetricResult(
        metric_name=MetricName.PERCENTAGE_RETURN_Z_SCORE,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
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
        target_boundary=target_boundary,
        baseline_metric_id=distribution.deterministic_id,
        value=value,
        unit=MetricUnit.STANDARD_DEVIATIONS,
        input_observation_ids=tuple(sorted(input_ids)),
        input_bar_boundaries=tuple(
            sorted(set(boundaries), key=lambda item: (item.bar_start, item.bar_end, item.observation_id))
        ),
        input_metric_ids=tuple(sorted(input_metric_ids)),
        sample_counts=distribution.sample_counts,
        quality=Quality(
            state=quality_state,
            reasons=()
            if quality_state is QualityState.KNOWN_VALUE
            else tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=sort_diagnostics(diagnostics),
    )
