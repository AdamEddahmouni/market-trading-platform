from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation, Quality, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode, sort_diagnostics
from .models import BarBoundaryRef, MetricName, MetricResult, MetricUnit, ProviderScopeMode
from .selection import (
    MetricSelectionRequest,
    bar_end,
    bar_session_date,
    bar_start,
    resolve_bar_at_boundary,
)

METRIC_VERSION = "1.0.0"
CALCULATION_POLICY_VERSION = "explicit_prior_close_to_current_open.v1"

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class GapRequest:
    symbol: str
    asset_class: AssetClass
    as_of: datetime
    source_interval: BarInterval
    prior_bar_start: datetime
    prior_bar_end: datetime
    current_bar_start: datetime
    current_bar_end: datetime
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None


def compute_absolute_gap(
    prior_close: Decimal | None, current_open: Decimal | None
) -> tuple[Decimal | None, MetricDiagnosticCode | None]:
    if prior_close is None:
        return None, MetricDiagnosticCode.GAP_PRIOR_CLOSE_UNAVAILABLE
    if current_open is None:
        return None, MetricDiagnosticCode.GAP_CURRENT_OPEN_UNAVAILABLE
    return current_open - prior_close, None


def compute_percentage_gap(
    prior_close: Decimal | None, current_open: Decimal | None
) -> tuple[Decimal | None, MetricDiagnosticCode | None]:
    if prior_close is None:
        return None, MetricDiagnosticCode.GAP_PRIOR_CLOSE_UNAVAILABLE
    if current_open is None:
        return None, MetricDiagnosticCode.GAP_CURRENT_OPEN_UNAVAILABLE
    if prior_close == 0:
        return None, MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR
    with localcontext() as ctx:
        ctx.prec = 28
        return ((current_open - prior_close) / prior_close) * Decimal(100), None


def _session_date_gap_days(prior_session_date: str | None, current_session_date: str | None) -> int | None:
    if prior_session_date is None or current_session_date is None:
        return None
    try:
        prior = date.fromisoformat(prior_session_date)
        current = date.fromisoformat(current_session_date)
    except ValueError:
        return None
    return (current - prior).days


def build_gap_result(
    observations: Iterable[Observation], request: GapRequest, metric_name: MetricName
) -> MetricResult:
    if metric_name not in (MetricName.ABSOLUTE_SESSION_GAP, MetricName.PERCENTAGE_SESSION_GAP):
        raise ValueError(f"unsupported gap metric_name: {metric_name}")
    observations = tuple(observations)
    selection_request = MetricSelectionRequest(
        symbol=request.symbol,
        as_of=request.as_of,
        source_interval=request.source_interval,
        session_scope=request.session_scope,
        provider_scope=request.provider_scope,
        provider=request.provider,
    )
    prior_resolution = resolve_bar_at_boundary(
        observations, selection_request, target_start=request.prior_bar_start, target_end=request.prior_bar_end
    )
    current_resolution = resolve_bar_at_boundary(
        observations, selection_request, target_start=request.current_bar_start, target_end=request.current_bar_end
    )
    diagnostics: list[MetricDiagnostic] = list(prior_resolution.diagnostics) + list(current_resolution.diagnostics)
    if prior_resolution.observation is None and any(
        d.code is MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS for d in prior_resolution.diagnostics
    ):
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.GAP_PRIOR_SESSION_NOT_FOUND,
                severity=_WARNING,
                message="No eligible bar exists at the requested prior-session boundary.",
            )
        )
    if current_resolution.observation is None and any(
        d.code is MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS for d in current_resolution.diagnostics
    ):
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.GAP_CURRENT_SESSION_NOT_FOUND,
                severity=_WARNING,
                message="No eligible bar exists at the requested current-session boundary.",
            )
        )

    prior_bar = prior_resolution.observation
    current_bar = current_resolution.observation
    value: Decimal | None = None
    quality_state = QualityState.UNAVAILABLE
    input_ids: tuple[str, ...] = ()
    boundaries: tuple[BarBoundaryRef, ...] = ()

    if prior_bar is not None and current_bar is not None:
        prior_session_date = bar_session_date(prior_bar)
        current_session_date = bar_session_date(current_bar)
        gap_days = _session_date_gap_days(prior_session_date, current_session_date)
        if gap_days is not None and gap_days <= 0:
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.GAP_SESSION_DATE_MISMATCH,
                    severity=_ERROR,
                    message="The prior and current boundaries do not represent two distinct, ordered session dates.",
                    observation_ids=(prior_bar.observation_id, current_bar.observation_id),
                )
            )
            quality_state = QualityState.INVALID
        else:
            if gap_days is not None and gap_days > 1:
                diagnostics.append(
                    MetricDiagnostic(
                        code=MetricDiagnosticCode.GAP_NONADJACENT_SESSION_POLICY,
                        severity=_INFO,
                        message="The prior and current session dates are more than one calendar day apart; no exchange calendar is consulted.",
                        observation_ids=(prior_bar.observation_id, current_bar.observation_id),
                    )
                )
            prior_close = prior_bar.payload.close
            current_open = current_bar.payload.open
            if metric_name is MetricName.ABSOLUTE_SESSION_GAP:
                gap_value, code = compute_absolute_gap(prior_close, current_open)
            else:
                gap_value, code = compute_percentage_gap(prior_close, current_open)
            if code is None:
                value = gap_value
                quality_state = QualityState.KNOWN_VALUE
            else:
                quality_state = (
                    QualityState.INVALID if code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR else QualityState.UNAVAILABLE
                )
                diagnostics.append(
                    MetricDiagnostic(
                        code=code,
                        severity=_ERROR if code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR else _WARNING,
                        message="The prior close or current open could not be used to compute a gap.",
                        observation_ids=(prior_bar.observation_id, current_bar.observation_id),
                    )
                )
        input_ids = tuple(sorted({prior_bar.observation_id, current_bar.observation_id}))
        boundaries = tuple(
            sorted(
                (
                    BarBoundaryRef(bar_start=bar_start(obs), bar_end=bar_end(obs), observation_id=obs.observation_id)
                    for obs in (prior_bar, current_bar)
                ),
                key=lambda item: item.bar_start,
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
        unit=MetricUnit.PRICE if metric_name is MetricName.ABSOLUTE_SESSION_GAP else MetricUnit.PERCENT,
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
