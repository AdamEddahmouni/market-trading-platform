from collections.abc import Iterable

from squeeze_core.contracts import EventType, Observation, QualityState
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.metrics import MetricName

from .models import EvaluationMetric, RuleEvaluationRequest


def eligible_observations(request: RuleEvaluationRequest) -> tuple[Observation, ...]:
    policy = PointInTimeEvidencePolicy(
        as_of=request.as_of,
        include_published_short_interest_domain=True,
        include_sec_filings_domain=True,
        include_trading_halts_domain=True,
        include_news_domain=True,
        include_market_bars_domain=True,
    )
    bundle = build_point_in_time_evidence(request.symbol, request.input_observations, policy)
    scoped = tuple(
        item for item in bundle.observations
        if not request.provider_scope or item.provenance.provider in request.provider_scope
    )
    return tuple(sorted(scoped, key=lambda item: (item.source_timestamp, str(item.observation_id))))


def observations_for_event(
    request: RuleEvaluationRequest, event_type: EventType
) -> tuple[Observation, ...]:
    return tuple(item for item in eligible_observations(request) if item.event_type is event_type)


def latest_observation(
    request: RuleEvaluationRequest, event_type: EventType
) -> Observation | None:
    items = observations_for_event(request, event_type)
    return items[-1] if items else None


def select_metric(request: RuleEvaluationRequest, metric_name: MetricName) -> EvaluationMetric | None:
    candidates = tuple(
        item for item in request.input_metrics
        if getattr(item, "metric_name", None) is metric_name
        and item.symbol == request.symbol
        and item.asset_class is request.asset_class
        and item.as_of <= request.as_of
        and (not request.provider_scope or getattr(item, "provider", None) in request.provider_scope)
    )
    return sorted(candidates, key=lambda item: (item.as_of, str(item.deterministic_id)))[-1] if candidates else None


def is_insufficient_metric(metric: EvaluationMetric) -> bool:
    if metric.quality.state is QualityState.MISSING:
        return True
    return any(
        "INSUFFICIENT" in item.code.value or "ZERO_BASELINE" in item.code.value
        for item in getattr(metric, "diagnostics", ())
    )


__all__ = [
    "eligible_observations", "is_insufficient_metric", "latest_observation",
    "observations_for_event", "select_metric",
]

