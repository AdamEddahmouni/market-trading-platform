"""Resolve frozen specialist execution contexts without repository expansion."""

from __future__ import annotations

from ..contracts import (
    ContractKind,
    ContractReference,
    DetectionV1,
    EventV1,
    InferenceJobV1,
    QualityState,
    RoutingDecisionV1,
    SignalV1,
    SnapshotV1,
)
from ..persistence.repository import IntelligenceRepository
from .context import SpecialistExecutionContext
from .models import SpecialistDiagnostic, SpecialistDiagnosticCode, SpecialistResult, SpecialistExecutionStatus
from .policy import DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY, MicrostructureSpecialistPolicyV1


def _failed(
    code: SpecialistDiagnosticCode,
    message: str,
    *,
    details: dict[str, object] | None = None,
) -> SpecialistResult:
    return SpecialistResult(
        status=SpecialistExecutionStatus.FAILED,
        diagnostics=(SpecialistDiagnostic(code, message, dict(details or {})),),
    )


def resolve_specialist_context(
    *,
    job: InferenceJobV1,
    repository: IntelligenceRepository,
    policy: MicrostructureSpecialistPolicyV1 | None = None,
) -> tuple[SpecialistExecutionContext | None, SpecialistResult | None]:
    """Resolve only explicitly referenced upstream artifacts."""

    active_policy = policy or DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY
    route = repository.get_routing_decision(job.routing_decision_ref.id)
    if route is None:
        return None, _failed(
            SpecialistDiagnosticCode.REFERENCE_RESOLUTION_FAILED,
            "routing decision not found",
            details={"routing_decision_id": job.routing_decision_ref.id},
        )

    detection = repository.get_detection(job.detection_ref.id)
    if detection is None:
        return None, _failed(
            SpecialistDiagnosticCode.REFERENCE_RESOLUTION_FAILED,
            "detection not found",
            details={"detection_id": job.detection_ref.id},
        )

    if route.detection_ref.id != detection.detection_id:
        return None, _failed(
            SpecialistDiagnosticCode.ROUTE_DETECTION_MISMATCH,
            "route detection ref does not match resolved detection",
            details={"route_detection_id": route.detection_ref.id, "job_detection_id": detection.detection_id},
        )

    if job.detection_ref.id != detection.detection_id:
        return None, _failed(
            SpecialistDiagnosticCode.ROUTE_DETECTION_MISMATCH,
            "job detection ref does not match resolved detection",
            details={"job_detection_id": job.detection_ref.id, "detection_id": detection.detection_id},
        )

    snapshot_id = detection.source_snapshot_ref.id
    if job.source_snapshot_ref is not None and job.source_snapshot_ref.id != snapshot_id:
        return None, _failed(
            SpecialistDiagnosticCode.SOURCE_SNAPSHOT_MISMATCH,
            "job snapshot ref does not match detection snapshot",
            details={"job_snapshot_id": job.source_snapshot_ref.id, "detection_snapshot_id": snapshot_id},
        )

    snapshot = repository.get_snapshot(snapshot_id)
    if snapshot is None:
        return None, _failed(
            SpecialistDiagnosticCode.REFERENCE_RESOLUTION_FAILED,
            "snapshot not found",
            details={"snapshot_id": snapshot_id},
        )

    if not detection.source_signal_refs:
        return None, _failed(
            SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE,
            "detection has no frozen source signal refs",
        )

    signal_ids = tuple(ref.id for ref in detection.source_signal_refs)
    resolved_signals = repository.get_signals(signal_ids)
    resolved_by_id = {row.signal_id: row for row in resolved_signals}
    if len(resolved_by_id) != len(signal_ids):
        missing = sorted(set(signal_ids) - set(resolved_by_id))
        return None, _failed(
            SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE,
            "required source signal missing",
            details={"missing_signal_ids": missing},
        )

    ordered_signals: list[SignalV1] = []
    for ref in detection.source_signal_refs:
        signal = resolved_by_id[ref.id]
        ordered_signals.append(signal)

    resolved_events: list[EventV1] = ()
    if detection.source_event_refs:
        event_ids = tuple(ref.id for ref in detection.source_event_refs)
        resolved_events = list(repository.get_events(event_ids))
        if len(resolved_events) != len(event_ids):
            missing = sorted(set(event_ids) - {row.event_id for row in resolved_events})
            return None, _failed(
                SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE,
                "required source event missing",
                details={"missing_event_ids": missing},
            )

    if detection.quality.state == QualityState.INVALID:
        return None, _failed(
            SpecialistDiagnosticCode.QUALITY_REJECTED,
            "detection quality invalid",
        )
    if detection.quality.state in {QualityState.DEGRADED, QualityState.UNKNOWN} and not active_policy.allow_degraded_inputs:
        return None, SpecialistResult(
            status=SpecialistExecutionStatus.ABSTAINED,
            diagnostics=(
                SpecialistDiagnostic(
                    SpecialistDiagnosticCode.QUALITY_REJECTED,
                    "degraded detection rejected by policy",
                ),
            ),
        )

    context = SpecialistExecutionContext(
        job=job,
        route=route,
        detection=detection,
        snapshot=snapshot,
        signals=tuple(ordered_signals),
        events=tuple(resolved_events),
        policy=active_policy,
    )
    return context, None


__all__ = ["resolve_specialist_context"]
