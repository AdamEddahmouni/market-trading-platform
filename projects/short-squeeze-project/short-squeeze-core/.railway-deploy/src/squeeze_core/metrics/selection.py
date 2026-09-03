from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarCompletionStatus, BarInterval, BarSession
from squeeze_core.contracts import Observation, QualityState
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.evidence import BarSeries, BarSeriesPolicy, build_bar_series

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode
from .models import ProviderScopeMode, TrailingWindow

_INFO = "INFO"
_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class MetricSelectionRequest:
    symbol: str
    as_of: datetime
    source_interval: BarInterval
    session_scope: tuple[BarSession, ...] = ()
    provider_scope: ProviderScopeMode = ProviderScopeMode.SINGLE_PROVIDER
    provider: str | None = None


@dataclass(frozen=True)
class BoundaryResolution:
    observation: Observation | None
    diagnostics: tuple[MetricDiagnostic, ...]


@dataclass(frozen=True)
class WindowResolution:
    samples: tuple[Observation, ...]
    requested: int
    eligible: int
    used: int
    missing: int
    diagnostics: tuple[MetricDiagnostic, ...]


def _metadata_time(observation: Observation, key: str) -> datetime:
    value = observation.provenance.provider_metadata.get(key)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError(f"BAR observation is missing structured {key}")
    return require_aware_utc(value)


def bar_start(observation: Observation) -> datetime:
    return _metadata_time(observation, "bar_start")


def bar_end(observation: Observation) -> datetime:
    return _metadata_time(observation, "bar_end")


def bar_status(observation: Observation) -> BarCompletionStatus:
    return BarCompletionStatus(observation.provenance.provider_metadata["status"])


def bar_provider(observation: Observation) -> str:
    return str(observation.provenance.provider_metadata["provider"])


def bar_revision_number(observation: Observation) -> int:
    value = observation.provenance.provider_metadata.get("revision_number")
    return 0 if value is None else int(value)


def bar_volume_unit(observation: Observation) -> str:
    return str(observation.provenance.provider_metadata.get("volume_unit", "UNKNOWN"))


def bar_session_date(observation: Observation) -> str | None:
    value = observation.provenance.provider_metadata.get("session_date")
    return None if value is None else str(value)


def bar_session(observation: Observation) -> str:
    value = observation.provenance.provider_metadata.get("session", "UNKNOWN")
    return value.value if hasattr(value, "value") else str(value)


def eligible_series(
    observations: Iterable[Observation], request: MetricSelectionRequest
) -> BarSeries:
    return build_bar_series(
        observations,
        BarSeriesPolicy(
            symbol=request.symbol,
            as_of=request.as_of,
            interval=request.source_interval,
            sessions=request.session_scope,
        ),
    )


def _filter_by_provider(
    observations: tuple[Observation, ...], provider: str | None
) -> tuple[Observation, ...]:
    if provider is None:
        return observations
    return tuple(item for item in observations if bar_provider(item) == provider)


def _group_by_boundary(
    observations: Iterable[Observation],
) -> dict[tuple[datetime, datetime], list[Observation]]:
    groups: dict[tuple[datetime, datetime], list[Observation]] = {}
    for observation in observations:
        groups.setdefault((bar_start(observation), bar_end(observation)), []).append(observation)
    return groups


def _resolve_group(
    group: list[Observation],
) -> tuple[Observation | None, MetricDiagnostic | None]:
    conflicted = [item for item in group if item.quality.state is QualityState.CONFLICTED]
    if conflicted:
        ids = tuple(sorted(item.observation_id for item in conflicted))
        return None, MetricDiagnostic(
            code=MetricDiagnosticCode.METRIC_CONFLICTED_INPUT,
            severity=_ERROR,
            message="Same-boundary market-bar records conflict; no winner is selected.",
            observation_ids=ids,
        )
    chosen = max(
        group,
        key=lambda item: (bar_revision_number(item), item.effective_timestamp, item.observation_id),
    )
    status = bar_status(chosen)
    if status is BarCompletionStatus.CANCELLED:
        return None, MetricDiagnostic(
            code=MetricDiagnosticCode.METRIC_CANCELLED_INPUT,
            severity=_WARNING,
            message="The latest eligible revision of this boundary is cancelled.",
            observation_ids=(chosen.observation_id,),
        )
    if status is BarCompletionStatus.PARTIAL:
        return None, MetricDiagnostic(
            code=MetricDiagnosticCode.METRIC_PARTIAL_INPUT,
            severity=_WARNING,
            message="The latest eligible revision of this boundary is still partial.",
            observation_ids=(chosen.observation_id,),
        )
    if status is BarCompletionStatus.UNKNOWN:
        return None, MetricDiagnostic(
            code=MetricDiagnosticCode.METRIC_UNKNOWN_AVAILABILITY,
            severity=_WARNING,
            message="The latest eligible revision of this boundary has unknown completion status.",
            observation_ids=(chosen.observation_id,),
        )
    return chosen, None


def resolve_bar_at_boundary(
    observations: Iterable[Observation],
    request: MetricSelectionRequest,
    *,
    target_start: datetime,
    target_end: datetime,
) -> BoundaryResolution:
    series = eligible_series(observations, request)
    candidates = series.observations
    if request.provider is None and request.provider_scope is ProviderScopeMode.SINGLE_PROVIDER:
        boundary_candidates = [
            item
            for item in candidates
            if bar_start(item) == target_start and bar_end(item) == target_end
        ]
        providers = {bar_provider(item) for item in boundary_candidates}
        if len(providers) > 1:
            ids = tuple(sorted(item.observation_id for item in boundary_candidates))
            return BoundaryResolution(
                observation=None,
                diagnostics=(
                    MetricDiagnostic(
                        code=MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER,
                        severity=_ERROR,
                        message="Multiple providers publish this boundary; an explicit provider is required.",
                        observation_ids=ids,
                    ),
                ),
            )
    elif request.provider_scope is not ProviderScopeMode.SINGLE_PROVIDER:
        raise NotImplementedError(
            f"provider_scope {request.provider_scope.value} is not implemented in Phase 2A"
        )
    filtered = _filter_by_provider(candidates, request.provider)
    groups = _group_by_boundary(filtered)
    group = groups.get((target_start, target_end))
    if not group:
        return BoundaryResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.METRIC_NO_ELIGIBLE_BARS,
                    severity=_WARNING,
                    message="No point-in-time eligible bar exists at the requested boundary.",
                ),
            ),
        )
    resolved, diagnostic = _resolve_group(group)
    return BoundaryResolution(
        observation=resolved,
        diagnostics=() if diagnostic is None else (diagnostic,),
    )


def resolve_trailing_window(
    observations: Iterable[Observation],
    request: MetricSelectionRequest,
    *,
    target_start: datetime,
    window: TrailingWindow,
    target_volume_unit: str | None,
) -> WindowResolution:
    series = eligible_series(observations, request)
    candidates = series.observations
    if request.provider is None and request.provider_scope is ProviderScopeMode.SINGLE_PROVIDER:
        providers = {bar_provider(item) for item in candidates}
        if len(providers) > 1:
            ids = tuple(sorted(item.observation_id for item in candidates))
            return WindowResolution(
                samples=(),
                requested=window.requested_count,
                eligible=0,
                used=0,
                missing=0,
                diagnostics=(
                    MetricDiagnostic(
                        code=MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER,
                        severity=_ERROR,
                        message="Multiple providers publish candidate bars; an explicit provider is required.",
                        observation_ids=ids,
                    ),
                ),
            )
    elif request.provider_scope is not ProviderScopeMode.SINGLE_PROVIDER:
        raise NotImplementedError(
            f"provider_scope {request.provider_scope.value} is not implemented in Phase 2A"
        )
    filtered = _filter_by_provider(candidates, request.provider)
    groups = _group_by_boundary(filtered)

    resolved_boundaries: list[tuple[datetime, Observation | None, MetricDiagnostic | None]] = []
    for (start, _end), group in groups.items():
        if window.exclude_current_bar:
            if start >= target_start:
                continue
        elif start > target_start:
            continue
        resolved, diagnostic = _resolve_group(group)
        resolved_boundaries.append((start, resolved, diagnostic))

    resolved_boundaries.sort(key=lambda item: item[0], reverse=True)

    samples: list[Observation] = []
    diagnostics: list[MetricDiagnostic] = []
    used = 0
    missing = 0
    eligible = 0
    for start, observation, diagnostic in resolved_boundaries:
        if used >= window.requested_count:
            break
        if observation is None:
            if diagnostic is not None:
                diagnostics.append(diagnostic)
            continue
        eligible += 1
        if observation.payload.volume is None:
            missing += 1
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.METRIC_MISSING_VOLUME,
                    severity=_WARNING,
                    message="A candidate bar has no recorded volume; it is excluded, not treated as zero.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        unit = bar_volume_unit(observation)
        if target_volume_unit is not None and unit != target_volume_unit:
            missing += 1
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.VOLUME_BASELINE_MIXED_UNITS,
                    severity=_WARNING,
                    message="A candidate bar reports volume in a different unit and is excluded.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        if observation.payload.volume == 0:
            diagnostics.append(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.METRIC_ZERO_VOLUME_SAMPLE,
                    severity=_INFO,
                    message="A zero-volume bar is retained as a valid sample.",
                    observation_ids=(observation.observation_id,),
                )
            )
        used += 1
        samples.append(observation)

    if not samples:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_BASELINE_WINDOW_EMPTY,
                severity=_ERROR,
                message="No usable bar exists within the requested trailing window.",
            )
        )
    elif used < window.minimum_samples:
        diagnostics.append(
            MetricDiagnostic(
                code=MetricDiagnosticCode.VOLUME_BASELINE_INSUFFICIENT_SAMPLES,
                severity=_ERROR,
                message="Fewer usable samples were found than the required minimum.",
                observation_ids=tuple(sorted(item.observation_id for item in samples)),
            )
        )

    samples.sort(key=lambda item: (bar_start(item), item.observation_id))
    return WindowResolution(
        samples=tuple(samples),
        requested=window.requested_count,
        eligible=eligible,
        used=used,
        missing=missing,
        diagnostics=tuple(diagnostics),
    )
