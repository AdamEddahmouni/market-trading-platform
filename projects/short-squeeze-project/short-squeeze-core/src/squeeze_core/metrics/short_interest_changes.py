from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext

from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import MetricName, MetricUnit, ProviderScopeMode
from .pressure_models import PressureMetricResult
from .pressure_selection import (
    PressureSelectionRequest,
    resolve_short_interest_at_period,
    resolve_short_interest_revision,
)
from .source_age import build_source_age

METRIC_VERSION = "1.0.0"
CHANGE_POLICY_VERSION = "explicit_reporting_period_pair.v1"
REVISION_POLICY_VERSION = "explicit_revision_link.v1"

_ERROR = "ERROR"


@dataclass(frozen=True)
class ShortInterestComparisonRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    provider: str
    starting_reporting_period: date
    ending_reporting_period: date


@dataclass(frozen=True)
class ShortInterestRevisionRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    provider: str
    reporting_period: date


def _quality_state_for(diagnostics: tuple[MetricDiagnostic, ...]) -> QualityState:
    codes = {item.code for item in diagnostics}
    if MetricDiagnosticCode.PRESSURE_METRIC_CONFLICTED_INPUT in codes:
        return QualityState.CONFLICTED
    if codes & {
        MetricDiagnosticCode.SHORT_INTEREST_ZERO_START_DENOMINATOR,
        MetricDiagnosticCode.PRESSURE_METRIC_IDENTICAL_INPUT,
        MetricDiagnosticCode.PRESSURE_METRIC_START_AFTER_END,
    }:
        return QualityState.INVALID
    return QualityState.UNAVAILABLE


def _unavailable_result(
    *,
    metric_name: MetricName,
    calculation_policy_version: str,
    request_symbol: str,
    request_asset_class: AssetClass,
    request_as_of: datetime,
    provider: str,
    unit: MetricUnit,
    diagnostics: tuple[MetricDiagnostic, ...],
    starting_reporting_period: date | None = None,
    ending_reporting_period: date | None = None,
    starting: Observation | None = None,
    ending: Observation | None = None,
) -> PressureMetricResult:
    diagnostics = sort_diagnostics(diagnostics)
    input_ids = tuple(
        sorted({obs.observation_id for obs in (starting, ending) if obs is not None})
    )
    return PressureMetricResult(
        metric_name=metric_name,
        metric_version=METRIC_VERSION,
        calculation_policy_version=calculation_policy_version,
        symbol=request_symbol,
        asset_class=request_asset_class,
        as_of=request_as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=provider,
        starting_observation_id=None if starting is None else starting.observation_id,
        ending_observation_id=None if ending is None else ending.observation_id,
        starting_reporting_period=starting_reporting_period,
        ending_reporting_period=ending_reporting_period,
        starting_source_age=None
        if starting is None
        else build_source_age(starting, request_as_of, reporting_period_end=starting.payload.settlement_date),
        ending_source_age=None
        if ending is None
        else build_source_age(ending, request_as_of, reporting_period_end=ending.payload.settlement_date),
        value=None,
        unit=unit,
        input_observation_ids=input_ids,
        quality=Quality(
            state=_quality_state_for(diagnostics),
            reasons=tuple(sorted({d.code.value for d in diagnostics})),
        ),
        diagnostics=diagnostics,
    )


def build_short_interest_change_result(
    observations: Iterable[Observation],
    request: ShortInterestComparisonRequest,
    metric_name: MetricName,
) -> PressureMetricResult:
    observations = tuple(observations)
    unit = MetricUnit.SHARES if metric_name is MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE else MetricUnit.PERCENT

    if request.starting_reporting_period == request.ending_reporting_period:
        return _unavailable_result(
            metric_name=metric_name,
            calculation_policy_version=CHANGE_POLICY_VERSION,
            request_symbol=request.symbol,
            request_asset_class=request.asset_class,
            request_as_of=request.as_of,
            provider=request.provider,
            unit=unit,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.PRESSURE_METRIC_IDENTICAL_INPUT,
                    severity=_ERROR,
                    message="Starting and ending reporting periods must differ.",
                ),
            ),
            starting_reporting_period=request.starting_reporting_period,
            ending_reporting_period=request.ending_reporting_period,
        )

    if request.starting_reporting_period > request.ending_reporting_period:
        return _unavailable_result(
            metric_name=metric_name,
            calculation_policy_version=CHANGE_POLICY_VERSION,
            request_symbol=request.symbol,
            request_asset_class=request.asset_class,
            request_as_of=request.as_of,
            provider=request.provider,
            unit=unit,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.PRESSURE_METRIC_START_AFTER_END,
                    severity=_ERROR,
                    message="Starting reporting period must be chronologically before the ending reporting period.",
                ),
            ),
            starting_reporting_period=request.starting_reporting_period,
            ending_reporting_period=request.ending_reporting_period,
        )

    selection_request = PressureSelectionRequest(
        symbol=request.symbol, as_of=request.as_of, provider=request.provider
    )
    starting_resolution = resolve_short_interest_at_period(
        observations,
        selection_request,
        reporting_period=request.starting_reporting_period,
        not_found_code=MetricDiagnosticCode.SHORT_INTEREST_START_NOT_FOUND,
    )
    ending_resolution = resolve_short_interest_at_period(
        observations,
        selection_request,
        reporting_period=request.ending_reporting_period,
        not_found_code=MetricDiagnosticCode.SHORT_INTEREST_END_NOT_FOUND,
    )

    if starting_resolution.observation is None or ending_resolution.observation is None:
        return _unavailable_result(
            metric_name=metric_name,
            calculation_policy_version=CHANGE_POLICY_VERSION,
            request_symbol=request.symbol,
            request_asset_class=request.asset_class,
            request_as_of=request.as_of,
            provider=request.provider,
            unit=unit,
            diagnostics=starting_resolution.diagnostics + ending_resolution.diagnostics,
            starting_reporting_period=request.starting_reporting_period,
            ending_reporting_period=request.ending_reporting_period,
            starting=starting_resolution.observation,
            ending=ending_resolution.observation,
        )

    starting = starting_resolution.observation
    ending = ending_resolution.observation
    starting_shares = Decimal(starting.payload.short_shares)
    ending_shares = Decimal(ending.payload.short_shares)

    diagnostics: list[MetricDiagnostic] = []
    value: Decimal | None
    with localcontext() as ctx:
        ctx.prec = 28
        if metric_name is MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE:
            value = ending_shares - starting_shares
        else:
            if starting_shares == 0:
                diagnostics.append(
                    MetricDiagnostic(
                        code=MetricDiagnosticCode.SHORT_INTEREST_ZERO_START_DENOMINATOR,
                        severity=_ERROR,
                        message="Starting published short interest is zero; a percentage change cannot be computed.",
                        observation_ids=(starting.observation_id,),
                    )
                )
                value = None
            else:
                value = (ending_shares - starting_shares) / starting_shares * Decimal(100)

    if value is None:
        return _unavailable_result(
            metric_name=metric_name,
            calculation_policy_version=CHANGE_POLICY_VERSION,
            request_symbol=request.symbol,
            request_asset_class=request.asset_class,
            request_as_of=request.as_of,
            provider=request.provider,
            unit=unit,
            diagnostics=diagnostics,
            starting_reporting_period=request.starting_reporting_period,
            ending_reporting_period=request.ending_reporting_period,
            starting=starting,
            ending=ending,
        )

    return PressureMetricResult(
        metric_name=metric_name,
        metric_version=METRIC_VERSION,
        calculation_policy_version=CHANGE_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.provider,
        starting_observation_id=starting.observation_id,
        ending_observation_id=ending.observation_id,
        starting_reporting_period=request.starting_reporting_period,
        ending_reporting_period=request.ending_reporting_period,
        starting_source_age=build_source_age(starting, request.as_of, reporting_period_end=starting.payload.settlement_date),
        ending_source_age=build_source_age(ending, request.as_of, reporting_period_end=ending.payload.settlement_date),
        value=value,
        unit=unit,
        input_observation_ids=(starting.observation_id, ending.observation_id),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=(),
    )


def build_short_interest_revision_delta_result(
    observations: Iterable[Observation],
    request: ShortInterestRevisionRequest,
) -> PressureMetricResult:
    observations = tuple(observations)
    selection_request = PressureSelectionRequest(
        symbol=request.symbol, as_of=request.as_of, provider=request.provider
    )
    starting_resolution, ending_resolution = resolve_short_interest_revision(
        observations, selection_request, reporting_period=request.reporting_period
    )

    if starting_resolution.observation is None or ending_resolution.observation is None:
        return _unavailable_result(
            metric_name=MetricName.PUBLISHED_SHORT_INTEREST_REVISION_DELTA,
            calculation_policy_version=REVISION_POLICY_VERSION,
            request_symbol=request.symbol,
            request_asset_class=request.asset_class,
            request_as_of=request.as_of,
            provider=request.provider,
            unit=MetricUnit.SHARES,
            diagnostics=starting_resolution.diagnostics + ending_resolution.diagnostics,
            starting_reporting_period=request.reporting_period,
            ending_reporting_period=request.reporting_period,
            starting=starting_resolution.observation,
            ending=ending_resolution.observation,
        )

    starting = starting_resolution.observation
    ending = ending_resolution.observation
    with localcontext() as ctx:
        ctx.prec = 28
        value = Decimal(ending.payload.short_shares) - Decimal(starting.payload.short_shares)

    return PressureMetricResult(
        metric_name=MetricName.PUBLISHED_SHORT_INTEREST_REVISION_DELTA,
        metric_version=METRIC_VERSION,
        calculation_policy_version=REVISION_POLICY_VERSION,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=request.provider,
        starting_observation_id=starting.observation_id,
        ending_observation_id=ending.observation_id,
        starting_reporting_period=request.reporting_period,
        ending_reporting_period=request.reporting_period,
        starting_source_age=build_source_age(starting, request.as_of, reporting_period_end=starting.payload.settlement_date),
        ending_source_age=build_source_age(ending, request.as_of, reporting_period_end=ending.payload.settlement_date),
        value=value,
        unit=MetricUnit.SHARES,
        input_observation_ids=(starting.observation_id, ending.observation_id),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=(),
    )
