"""Standard replay decision pipeline through BUILD 05/06 (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import ContractKind, ContractReference
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..persistence.repository import IntelligenceRepository
from ..quality.models import QualityDecision
from ..routing import (
    DetectionFrame,
    DetectionPolicyV1,
    EventDetectorEngine,
    RoutingPolicyV1,
    SmartRouter,
)
from ..signals import FastSignalEngine, SignalComputationRequest
from ..snapshots import SnapshotBuildRequest, SnapshotBuildResult, build_snapshot, resolve_snapshot
from ..temporal.policy import TemporalIntegrityPolicy
from ..quality.policy import QualityPolicy
from .models import ReplayDecisionResult
from .visibility import ReplayVisibleRepository


@dataclass(frozen=True, slots=True)
class ReplayPipelineConfig:
    snapshot_request: SnapshotBuildRequest | None = None
    signal_request: SignalComputationRequest | None = None
    persist_outputs: bool = True
    quality_decision: QualityDecision | None = None
    quality_decisions: tuple[QualityDecision, ...] = ()
    provider_health: tuple[Any, ...] = ()
    temporal_policy: TemporalIntegrityPolicy | None = None
    quality_policy: QualityPolicy | None = None
    enable_build_09: bool = False
    detection_policy: DetectionPolicyV1 | None = None
    routing_policy: RoutingPolicyV1 | None = None

    def __post_init__(self) -> None:
        times = [row.assessment.decision_time_ns for row in self.quality_decisions]
        if len(times) != len(set(times)):
            raise ValueError("DUPLICATE_REPLAY_QUALITY_DECISION_TIME")

    def quality_at(self, decision_time_ns: int) -> QualityDecision | None:
        for row in self.quality_decisions:
            if row.assessment.decision_time_ns == decision_time_ns:
                return row
        if (
            self.quality_decision is not None
            and self.quality_decision.assessment.decision_time_ns == decision_time_ns
        ):
            return self.quality_decision
        return None


def _process_build_09(
    *,
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...],
    events: tuple,
    quality_decision: QualityDecision | None,
    output_repository: IntelligenceRepository,
    config: ReplayPipelineConfig,
    detector_engine: EventDetectorEngine | None,
    smart_router: SmartRouter | None,
) -> tuple[tuple[ContractReference, ...], tuple[ContractReference, ...]]:
    if not config.enable_build_09:
        return (), ()
    if quality_decision is None:
        raise ValueError("BUILD_09_QUALITY_DECISION_REQUIRED_AT_DECISION_TIME")
    engine = detector_engine or EventDetectorEngine(config.detection_policy)
    router = smart_router or SmartRouter(config.routing_policy)
    detected = engine.detect(
        DetectionFrame(
            snapshot=snapshot,
            signals=signals,
            events=events,
            quality_decision=quality_decision,
        )
    )
    routes = router.route_all(detected.detections, quality_decision=quality_decision)
    if config.persist_outputs:
        for detection in detected.detections:
            output_repository.put_detection(detection)
        for route in routes:
            output_repository.put_routing_decision(route)
    detection_refs = tuple(
        ContractReference(kind=ContractKind.DETECTION.value, id=row.detection_id)
        for row in detected.detections
    )
    route_refs = tuple(
        ContractReference(kind=ContractKind.ROUTING_DECISION.value, id=row.routing_decision_id)
        for row in routes
    )
    return detection_refs, route_refs


def process_replay_decision(
    visible_repository: ReplayVisibleRepository,
    output_repository: IntelligenceRepository,
    *,
    decision_time_ns: int,
    config: ReplayPipelineConfig,
    detector_engine: EventDetectorEngine | None = None,
    smart_router: SmartRouter | None = None,
) -> ReplayDecisionResult:
    """Build snapshot and optional signals at a replay decision point."""
    repo = visible_repository.with_decision_time(decision_time_ns)
    if config.snapshot_request is None:
        return ReplayDecisionResult(decision_time_ns=decision_time_ns)

    request = SnapshotBuildRequest(
        decision_time_ns=decision_time_ns,
        scope=config.snapshot_request.scope,
        composition_policy=config.snapshot_request.composition_policy,
        capability_requirements=config.snapshot_request.capability_requirements,
    )
    exact_quality_decision = config.quality_at(decision_time_ns)
    active_quality_decision = exact_quality_decision or config.quality_decision
    built: SnapshotBuildResult = build_snapshot(
        repo,
        request,
        quality_decision=active_quality_decision,
        provider_health=config.provider_health,
        temporal_policy=config.temporal_policy,
        quality_policy=config.quality_policy,
        persist=config.persist_outputs,
    )
    snapshot = built.snapshot
    if snapshot is None:
        return ReplayDecisionResult(
            decision_time_ns=decision_time_ns,
            quality_decision=built.quality_decision,
            diagnostics={"eligible_event_count": len(built.selected_event_ids)},
        )

    if config.persist_outputs:
        output_repository.put_snapshot(snapshot)

    signal_refs: list[ContractReference] = []
    signal_rows: tuple[SignalV1, ...] = ()
    if config.signal_request is not None:
        resolved = resolve_snapshot(snapshot, repo)
        engine = FastSignalEngine()
        if config.persist_outputs:
            signal_result = engine.compute_and_persist(
                resolved,
                output_repository,
                config.signal_request,
            )
        else:
            signal_result = engine.compute(resolved, config.signal_request)
        for signal in signal_result.signals:
            signal_refs.append(
                ContractReference(kind=ContractKind.SIGNAL.value, id=signal.signal_id)
            )
        signal_rows = signal_result.signals

    events = repo.get_events(tuple(ref.id for ref in snapshot.source_event_refs))
    detection_refs, route_refs = _process_build_09(
        snapshot=snapshot,
        signals=signal_rows,
        events=events,
        quality_decision=exact_quality_decision,
        output_repository=output_repository,
        config=config,
        detector_engine=detector_engine,
        smart_router=smart_router,
    )

    return ReplayDecisionResult(
        decision_time_ns=decision_time_ns,
        snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot.snapshot_id),
        signal_refs=tuple(signal_refs),
        detection_refs=detection_refs,
        routing_decision_refs=route_refs,
        quality_decision=built.quality_decision,
        diagnostics={
            "eligible_event_count": len(built.selected_event_ids),
            "content_fingerprint": built.content_fingerprint,
        },
    )


def live_like_sequential_decision(
    source_events: tuple,
    output_repository: IntelligenceRepository,
    *,
    decision_time_ns: int,
    config: ReplayPipelineConfig,
    detector_engine: EventDetectorEngine | None = None,
    smart_router: SmartRouter | None = None,
) -> ReplayDecisionResult:
    """Test harness: expose events at recorded availability, then decide."""
    visible_events = [
        event for event in source_events if event.available_time_ns <= decision_time_ns
    ]
    for event in visible_events:
        output_repository.put_event(event)
    request = config.snapshot_request
    if request is None:
        return ReplayDecisionResult(decision_time_ns=decision_time_ns)
    built_request = SnapshotBuildRequest(
        decision_time_ns=decision_time_ns,
        scope=request.scope,
        composition_policy=request.composition_policy,
        capability_requirements=request.capability_requirements,
    )
    exact_quality_decision = config.quality_at(decision_time_ns)
    active_quality_decision = exact_quality_decision or config.quality_decision
    built = build_snapshot(
        output_repository,
        built_request,
        quality_decision=active_quality_decision,
        provider_health=config.provider_health,
        temporal_policy=config.temporal_policy,
        quality_policy=config.quality_policy,
        persist=config.persist_outputs,
    )
    snapshot = built.snapshot
    if snapshot is None:
        return ReplayDecisionResult(
            decision_time_ns=decision_time_ns,
            quality_decision=built.quality_decision,
        )
    signal_refs: list[ContractReference] = []
    signal_rows: tuple[SignalV1, ...] = ()
    if config.signal_request is not None:
        resolved = resolve_snapshot(snapshot, output_repository)
        engine = FastSignalEngine()
        signal_result = engine.compute_and_persist(
            resolved,
            output_repository,
            config.signal_request,
        )
        for signal in signal_result.signals:
            signal_refs.append(
                ContractReference(kind=ContractKind.SIGNAL.value, id=signal.signal_id)
            )
        signal_rows = signal_result.signals
    events = output_repository.get_events(tuple(ref.id for ref in snapshot.source_event_refs))
    detection_refs, route_refs = _process_build_09(
        snapshot=snapshot,
        signals=signal_rows,
        events=events,
        quality_decision=exact_quality_decision,
        output_repository=output_repository,
        config=config,
        detector_engine=detector_engine,
        smart_router=smart_router,
    )
    return ReplayDecisionResult(
        decision_time_ns=decision_time_ns,
        snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot.snapshot_id),
        signal_refs=tuple(signal_refs),
        detection_refs=detection_refs,
        routing_decision_refs=route_refs,
        quality_decision=built.quality_decision,
        diagnostics={"content_fingerprint": built.content_fingerprint},
    )


__all__ = [
    "ReplayPipelineConfig",
    "live_like_sequential_decision",
    "process_replay_decision",
]
