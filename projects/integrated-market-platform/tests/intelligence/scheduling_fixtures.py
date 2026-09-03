"""Deterministic BUILD 10 scheduler test fixtures."""

from __future__ import annotations

import dataclasses

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    ExpertDomain,
    QualityState,
    QualitySummary,
    RouteAction,
    RoutingDecisionV1,
    RoutingPriority,
)
from tests.intelligence.routing_fixtures import T

SCHEDULER_T = T


def sample_route(
    route_id: str = "ROUTE-abc",
    *,
    priority: RoutingPriority = RoutingPriority.HIGH,
    decision_time_ns: int = SCHEDULER_T,
    deadline_offset_ns: int = 5_000_000_000,
    ttl_ns: int = 30_000_000_000,
    expert_domain: ExpertDomain = ExpertDomain.MICROSTRUCTURE,
    metadata: dict[str, object] | None = None,
) -> RoutingDecisionV1:
    return RoutingDecisionV1(
        routing_decision_id=route_id,
        schema_version="1",
        detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id="DET-abc"),
        decision_time_ns=decision_time_ns,
        expert_domain=expert_domain,
        route_action=RouteAction.ROUTE,
        priority=priority,
        reason_codes=("FIXTURE_ROUTE",),
        required_capabilities=("QUOTES", "TRADES"),
        optional_capabilities=("DEPTH",),
        deadline_time_ns=decision_time_ns + deadline_offset_ns,
        expires_at_ns=decision_time_ns + ttl_ns,
        ttl_ns=ttl_ns,
        quality=QualitySummary(state=QualityState.GOOD),
        router_lineage=ComponentLineage(component_id="smart-router", component_version="1"),
        metadata=dict(metadata or {"instrument_id": "US:XYZ", "semantic_event_type": "ORDER_FLOW_REVERSAL"}),
    )


def route_with_priority(priority: RoutingPriority, route_id: str) -> RoutingDecisionV1:
    return sample_route(route_id, priority=priority)


def expired_route(route_id: str = "ROUTE-expired") -> RoutingDecisionV1:
    return sample_route(route_id, ttl_ns=1)


def replace_route(route: RoutingDecisionV1, **kwargs: object) -> RoutingDecisionV1:
    return dataclasses.replace(route, **kwargs)
