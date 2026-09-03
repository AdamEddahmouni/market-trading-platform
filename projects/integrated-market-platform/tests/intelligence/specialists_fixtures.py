"""Deterministic BUILD 11 specialist test fixtures."""

from __future__ import annotations

import dataclasses

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    ExpertDomain,
    InferenceJobV1,
    QualityState,
    QualitySummary,
    RouteAction,
    RoutingDecisionV1,
    RoutingPriority,
    SemanticEventType,
    SignalV1,
    SnapshotV1,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality import IntelligenceCapability
from market_platform_foundation.intelligence.routing import (
    DetectionFrame,
    DetectionPolicyV1,
    EventDetectorEngine,
    RoutingPolicyV1,
    SmartRouter,
)
from market_platform_foundation.intelligence.scheduling import (
    InferenceScheduler,
    derive_inference_job_id,
)
from tests.intelligence.routing_fixtures import T, WINDOW_NS, quality_decision, signal, snapshot


def order_flow_detection(
    *,
    previous_nss: float = -0.35,
    current_nss: float = 0.42,
    snap1_id: str = "snap-of-prev",
    snap2_id: str = "snap-of-curr",
    quality: QualityState = QualityState.GOOD,
) -> tuple[SnapshotV1, SnapshotV1, SignalV1, SignalV1, DetectionV1]:
    snap1 = snapshot(snap1_id, decision_time_ns=T, quality=quality)
    snap2 = snapshot(snap2_id, decision_time_ns=T + 1, quality=quality)
    sig_prev = signal(snap1, f"sig-nss-prev-{snap1_id}", "net_signed_share", previous_nss, window_ns=WINDOW_NS, quality=quality)
    sig_curr = signal(snap2, f"sig-nss-curr-{snap2_id}", "net_signed_share", current_nss, window_ns=WINDOW_NS, quality=quality)

    policy = DetectionPolicyV1(allow_degraded_inputs=quality != QualityState.GOOD)
    detector = EventDetectorEngine(policy)
    detector.detect(
        DetectionFrame(
            snapshot=snap1,
            signals=(sig_prev,),
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=snap1.decision_time_ns,
            ),
        )
    )
    result = detector.detect(
        DetectionFrame(
            snapshot=snap2,
            signals=(sig_curr,),
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=snap2.decision_time_ns,
            ),
        )
    )
    assert len(result.detections) == 1
    detection = result.detections[0]
    assert detection.semantic_event_type == SemanticEventType.ORDER_FLOW_REVERSAL
    return snap1, snap2, sig_prev, sig_curr, detection


def liquidity_detection(
    *,
    previous_spread: float = 40.0,
    current_spread: float = 60.0,
    snap1_id: str = "snap-liq-prev",
    snap2_id: str = "snap-liq-curr",
    quality: QualityState = QualityState.GOOD,
) -> tuple[SnapshotV1, SnapshotV1, SignalV1, SignalV1, DetectionV1]:
    snap1 = snapshot(snap1_id, decision_time_ns=T, quality=quality)
    snap2 = snapshot(snap2_id, decision_time_ns=T + 1, quality=quality)
    sig_prev = signal(snap1, f"sig-spread-prev-{snap1_id}", "spread_bps", previous_spread, quality=quality)
    sig_curr = signal(snap2, f"sig-spread-curr-{snap2_id}", "spread_bps", current_spread, quality=quality)

    detector = EventDetectorEngine(DetectionPolicyV1())
    detector.detect(
        DetectionFrame(
            snapshot=snap1,
            signals=(sig_prev,),
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.DEPTH,
                decision_time_ns=snap1.decision_time_ns,
            ),
        )
    )
    result = detector.detect(
        DetectionFrame(
            snapshot=snap2,
            signals=(sig_curr,),
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.DEPTH,
                decision_time_ns=snap2.decision_time_ns,
            ),
        )
    )
    assert len(result.detections) == 1
    detection = result.detections[0]
    assert detection.semantic_event_type == SemanticEventType.LIQUIDITY_EVENT
    return snap1, snap2, sig_prev, sig_curr, detection


def routed_microstructure_job(
    detection: DetectionV1,
    active_snapshot: SnapshotV1,
    *,
    signals: tuple[SignalV1, ...] = (),
    repo: InMemoryIntelligenceRepository | None = None,
    scheduler_time_ns: int = T,
) -> tuple[InMemoryIntelligenceRepository, RoutingDecisionV1, InferenceJobV1]:
    repository = repo or InMemoryIntelligenceRepository()
    repository.put_snapshot(active_snapshot)
    for row in signals:
        if repository.get_snapshot(row.source_snapshot_ref.id) is None:
            source_snap = snapshot(row.source_snapshot_ref.id, decision_time_ns=row.as_of_time_ns)
            repository.put_snapshot(source_snap)
        repository.put_signal(row)
    repository.put_detection(detection)

    router = SmartRouter(RoutingPolicyV1())
    route = router.route(
        detection,
        quality_decision=quality_decision(
            IntelligenceCapability.QUOTES,
            IntelligenceCapability.TRADES,
            decision_time_ns=detection.detected_at_ns,
        ),
    )
    repository.put_routing_decision(route)
    assert route.route_action == RouteAction.ROUTE

    scheduler = InferenceScheduler()
    admitted = scheduler.submit_route(
        route,
        scheduler_time_ns=scheduler_time_ns,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=active_snapshot.snapshot_id),
    )
    assert admitted.job is not None
    repository.put_inference_job(admitted.job)
    return repository, route, admitted.job


def manual_detection(
    *,
    event_type: SemanticEventType,
    signal_refs: tuple[ContractReference, ...],
    snapshot_id: str = "snap-manual",
    identity_context: dict[str, str] | None = None,
    severity: DetectionSeverity = DetectionSeverity.MEDIUM,
    quality: QualityState = QualityState.GOOD,
    reason_codes: tuple[str, ...] = ("FIXTURE_TRIGGER",),
) -> DetectionV1:
    return DetectionV1(
        detection_id=f"DET-manual-{event_type.value}",
        schema_version="1",
        semantic_event_type=event_type,
        detected_at_ns=T,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
        source_signal_refs=signal_refs,
        detector_lineage=ComponentLineage(component_id="fixture-detector", component_version="1"),
        scope=snapshot(snapshot_id).scope,
        severity=severity,
        reason_codes=reason_codes,
        quality=QualitySummary(state=quality),
        identity_context=dict(identity_context or {}),
    )


def replace_detection_signals(detection: DetectionV1, signals: tuple[SignalV1, ...]) -> DetectionV1:
    refs = tuple(ContractReference(kind=ContractKind.SIGNAL.value, id=row.signal_id) for row in signals)
    return dataclasses.replace(detection, source_signal_refs=refs)


__all__ = [
    "liquidity_detection",
    "manual_detection",
    "order_flow_detection",
    "replace_detection_signals",
    "routed_microstructure_job",
]
