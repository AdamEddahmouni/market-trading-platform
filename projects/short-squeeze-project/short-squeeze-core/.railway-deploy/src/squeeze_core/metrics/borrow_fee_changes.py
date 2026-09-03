from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from squeeze_core.contracts import AssetClass, EventType, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import MetricName, MetricUnit, ProviderScopeMode
from .pressure_models import PressureMetricResult
from .pressure_selection import PressureSelectionRequest, resolve_borrow_observation_at
from .source_age import build_source_age

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "explicit_observation_pair.v1"

_ERROR = "ERROR"


@dataclass(frozen=True)
class BorrowComparisonRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    provider: str
    starting_effective_timestamp: datetime
    ending_effective_timestamp: datetime


def _quality_state_for(diagnostics: tuple[MetricDiagnostic, ...]) -> QualityState:
    codes = {item.code for item in diagnostics}
    if MetricDiagnosticCode.PRESSURE_METRIC_CONFLICTED_INPUT in codes:
        return QualityState.CONFLICTED
    if codes & {
        MetricDiagnosticCode.BORROW_FEE_ZERO_START_DENOMINATOR,
        MetricDiagnosticCode.PRESSURE_METRIC_IDENTICAL_INPUT,
        MetricDiagnosticCode.PRESSURE_METRIC_START_AFTER_END,
    }:
        return QualityState.INVALID
    return QualityState.UNAVAILABLE


def _unavailable_result(
    *,
    metric_name: MetricName,
    request: BorrowComparisonRequest,
    unit: MetricUnit,
    diagnostics: tuple[MetricDiagnostic, ...],
    starting: Observation | None,
    ending: Observation | None,
) -> PressureMetricResult:
    diagnostics = sort_diagnostics(diagnostics)
    input_ids = tuple(sorted({obs.observation_id for obs in (starting, ending) if obs is not None}))
    return PressureMetricResult(
        metric_name=metric_name,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.provider,
        starting_observation_id=None if starting is None else starting.observation_id,
        ending_observation_id=None if ending is None else ending.observation_id,
        starting_source_age=None if starting is None else build_source_age(starting, request.as_of),
        ending_source_age=None if ending is None else build_source_age(ending, request.as_of),
        value=None,
        unit=unit,
        input_observation_ids=input_ids,
        quality=Quality(
            state=_quality_state_for(diagnostics),
            reasons=tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=diagnostics,
    )


def build_borrow_fee_change_result(
    observations: Iterable[Observation],
    request: BorrowComparisonRequest,
    metric_name: MetricName,
) -> PressureMetricResult:
    observations = tuple(observations)
    unit = (
        MetricUnit.PERCENTAGE_POINTS
        if metric_name is MetricName.BORROW_FEE_ABSOLUTE_CHANGE
        else MetricUnit.PERCENT
    )

    if request.starting_effective_timestamp >= request.ending_effective_timestamp:
        code = (
            MetricDiagnosticCode.PRESSURE_METRIC_IDENTICAL_INPUT
            if request.starting_effective_timestamp == request.ending_effective_timestamp
            else MetricDiagnosticCode.PRESSURE_METRIC_START_AFTER_END
        )
        return _unavailable_result(
            metric_name=metric_name,
            request=request,
            unit=unit,
            diagnostics=(
                MetricDiagnostic(
                    code=code,
                    severity=_ERROR,
                    message="Starting boundary must be strictly before the ending boundary.",
                ),
            ),
            starting=None,
            ending=None,
        )

    selection_request = PressureSelectionRequest(symbol=request.symbol, as_of=request.as_of, provider=request.provider)
    starting_resolution = resolve_borrow_observation_at(
        observations,
        selection_request,
        event_type=EventType.BORROW_FEE,
        effective_timestamp=request.starting_effective_timestamp,
        not_found_code=MetricDiagnosticCode.BORROW_FEE_START_NOT_FOUND,
    )
    ending_resolution = resolve_borrow_observation_at(
        observations,
        selection_request,
        event_type=EventType.BORROW_FEE,
        effective_timestamp=request.ending_effective_timestamp,
        not_found_code=MetricDiagnosticCode.BORROW_FEE_END_NOT_FOUND,
    )

    starting = starting_resolution.observation
    ending = ending_resolution.observation
    diagnostics: list[MetricDiagnostic] = list(starting_resolution.diagnostics) + list(ending_resolution.diagnostics)

    if starting is not None and starting.payload.annualized_fee_percent is None:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.BORROW_FEE_MISSING_VALUE,
                severity=_ERROR,
                message="Starting borrow-fee observation has no reported fee value.",
                observation_ids=(starting.observation_id,),
            )
        )
        starting = None
    if ending is not None and ending.payload.annualized_fee_percent is None:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.BORROW_FEE_MISSING_VALUE,
                severity=_ERROR,
                message="Ending borrow-fee observation has no reported fee value.",
                observation_ids=(ending.observation_id,),
            )
        )
        ending = None

    if starting is None or ending is None:
        return _unavailable_result(
            metric_name=metric_name, request=request, unit=unit, diagnostics=tuple(diagnostics),
            starting=starting, ending=ending,
        )

    starting_fee = starting.payload.annualized_fee_percent
    ending_fee = ending.payload.annualized_fee_percent

    value: Decimal | None
    with localcontext() as ctx:
        ctx.prec = 28
        if metric_name is MetricName.BORROW_FEE_ABSOLUTE_CHANGE:
            value = ending_fee - starting_fee
        else:
            if starting_fee == 0:
                diagnostics.append(
                    MetricDiagnostic(
                        code=MetricDiagnosticCode.BORROW_FEE_ZERO_START_DENOMINATOR,
                        severity=_ERROR,
                        message="Starting borrow fee is zero; a relative percentage change cannot be computed.",
                        observation_ids=(starting.observation_id,),
                    )
                )
                value = None
            else:
                value = (ending_fee - starting_fee) / starting_fee * Decimal(100)

    if value is None:
        return _unavailable_result(
            metric_name=metric_name, request=request, unit=unit, diagnostics=tuple(diagnostics),
            starting=starting, ending=ending,
        )

    return PressureMetricResult(
        metric_name=metric_name,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CALCULATION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.provider,
        starting_observation_id=starting.observation_id,
        ending_observation_id=ending.observation_id,
        starting_source_age=build_source_age(starting, request.as_of),
        ending_source_age=build_source_age(ending, request.as_of),
        value=value,
        unit=unit,
        input_observation_ids=(starting.observation_id, ending.observation_id),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=(),
    )
