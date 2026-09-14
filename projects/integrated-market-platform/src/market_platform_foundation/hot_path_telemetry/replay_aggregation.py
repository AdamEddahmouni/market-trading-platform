"""Aggregate hot-path timestamps and quality from BUILD 07 replay outputs."""

from __future__ import annotations

from typing import Any

from market_platform_foundation.intelligence.contracts.detection import DetectionV1
from market_platform_foundation.intelligence.contracts.event import EventV1
from market_platform_foundation.intelligence.contracts.routing_decision import RoutingDecisionV1
from market_platform_foundation.intelligence.persistence.repository import IntelligenceRepository
from market_platform_foundation.intelligence.replay.models import ReplayRunResult

from .models import HOT_PATH_TIMESTAMP_NAMES, HotPathQualityCounters
from .quality_mapping import apply_finding_code, record_normalized_success
from .stats import empty_presence, latency_summary


def _event_row(event: EventV1) -> dict[str, int | None]:
    return {
        "source_event_at": event.event_time_ns,
        "provider_received_at": event.provider_time_ns,
        "imp_received_at": event.received_time_ns,
        "normalized_at": None,
        "router_dispatched_at": None,
        "detected_at": None,
        "opportunity_created_at": None,
        "operator_surfaced_at": None,
    }


def presence_from_event_rows(rows: list[dict[str, int | None]]) -> dict[str, dict[str, int]]:
    presence = {name: empty_presence() for name in HOT_PATH_TIMESTAMP_NAMES}
    for row in rows:
        for name in HOT_PATH_TIMESTAMP_NAMES:
            bucket = presence[name]
            if row.get(name) is None:
                presence[name] = {
                    "present_count": bucket["present_count"],
                    "missing_count": bucket["missing_count"] + 1,
                }
            else:
                presence[name] = {
                    "present_count": bucket["present_count"] + 1,
                    "missing_count": bucket["missing_count"],
                }
    return presence


def quality_from_replay_result(
    result: ReplayRunResult,
    *,
    events: tuple[EventV1, ...] = (),
) -> HotPathQualityCounters:
    counters = HotPathQualityCounters(received=result.trace_summary.delivered_count)
    if events:
        counters = record_normalized_success(counters, count=len(events))
    for decision in result.decision_results:
        qd = decision.quality_decision
        if qd is None:
            continue
        for finding in qd.assessment.findings:
            counters = apply_finding_code(counters, finding.code)
    return counters


def aggregate_replay_outputs(
    result: ReplayRunResult,
    repository: IntelligenceRepository,
) -> dict[str, Any]:
    events = tuple(
        repository.iter_events_by_availability(
            start_time_ns=0,
            end_time_ns=max(result.end_time_ns, result.start_time_ns),
        )
    )
    event_rows = [_event_row(event) for event in events]
    presence = presence_from_event_rows(event_rows)

    detections: list[DetectionV1] = []
    routes: list[RoutingDecisionV1] = []
    for decision in result.decision_results:
        for ref in decision.detection_refs:
            row = repository.get_detection(ref.id)
            if row is not None:
                detections.append(row)
        for ref in decision.routing_decision_refs:
            row = repository.get_routing_decision(ref.id)
            if row is not None:
                routes.append(row)

    if detections:
        detected_presence = empty_presence()
        detected_presence["present_count"] = len(detections)
        detected_presence["missing_count"] = max(0, len(event_rows) - len(detections))
        presence["detected_at"] = detected_presence
    if routes:
        route_presence = empty_presence()
        route_presence["present_count"] = len(routes)
        route_presence["missing_count"] = max(0, len(detections) - len(routes))
        presence["router_dispatched_at"] = route_presence

    detect_to_route_samples: list[int] = []
    detect_to_route_missing = 0
    for detection in detections:
        matched = [route for route in routes if route.detection_ref.id == detection.detection_id]
        if not matched:
            detect_to_route_missing += 1
            continue
        route = matched[0]
        delta = route.decision_time_ns - detection.detected_at_ns
        if delta >= 0:
            detect_to_route_samples.append(delta)
        else:
            detect_to_route_missing += 1

    segments = {
        "detected_to_router_dispatched": latency_summary(
            detect_to_route_samples,
            missing_pair_count=detect_to_route_missing,
        ),
    }

    return {
        "event_count": len(events),
        "detection_count": len(detections),
        "routing_decision_count": len(routes),
        "timestamp_presence": presence,
        "latency_segments_ns": segments,
        "quality_counters": quality_from_replay_result(result, events=events).to_dict(),
    }


__all__ = ["aggregate_replay_outputs", "presence_from_event_rows", "quality_from_replay_result"]
