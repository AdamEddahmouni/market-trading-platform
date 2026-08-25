"""Immutable snapshot composition engine (BUILD 05)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
    QualityState,
    QualitySummary,
)
from ..contracts.event import EventV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from ..quality.assessment import assess_capabilities, inspect_quality
from ..quality.models import DecisionAction, FindingSeverity, QualityDecision, QualityFindingCode
from ..quality.policy import QualityPolicy
from ..quality.summary import quality_summary_from_assessment
from ..temporal.models import TemporalIntegrityError
from ..temporal.policy import TemporalIntegrityPolicy
from ..temporal.selection import select_events_as_of
from ..temporal.snapshot import require_snapshot_temporally_valid, validate_snapshot_temporal_integrity
from ..temporal.validation import event_sort_key, inspect_event_temporal_integrity, inspect_signal_temporal_integrity
from .canonical import (
    FINGERPRINT_VERSION,
    fingerprint_from_snapshot_parts,
    snapshot_id_from_fingerprint,
)
from .errors import SnapshotBuildError, SnapshotQualityError, SnapshotTemporalError
from .policy import (
    BUILDER_COMPONENT_ID,
    BUILDER_COMPONENT_VERSION,
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
)
from .resolver import RepositoryTemporalResolver

_HARD_EXCLUDE_FINDING_CODES = frozenset(
    {
        QualityFindingCode.FUTURE_INFORMATION.value,
        QualityFindingCode.INVALID_QUOTE.value,
        QualityFindingCode.CROSSED_BOOK.value,
        QualityFindingCode.PROVIDER_DISCONNECTED.value,
    }
)


class ExclusionReason:
    FUTURE = "FUTURE"
    STALE_UNUSABLE = "STALE_UNUSABLE"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
    OUTSIDE_WINDOW = "OUTSIDE_WINDOW"
    DUPLICATE = "DUPLICATE"
    LIMIT_TRUNCATED = "LIMIT_TRUNCATED"
    CAPABILITY_NOT_REQUIRED = "CAPABILITY_NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class SnapshotExclusion:
    record_kind: str
    record_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SnapshotBuildResult:
    snapshot: SnapshotV1 | None
    quality_decision: QualityDecision
    content_fingerprint: str
    selected_event_ids: tuple[str, ...]
    selected_signal_ids: tuple[str, ...]
    excluded: tuple[SnapshotExclusion, ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _builder_component_ref() -> ContractReference:
    return ContractReference(
        kind="component",
        id=BUILDER_COMPONENT_ID,
        schema_version=BUILDER_COMPONENT_VERSION,
    )


def _event_in_scope(
    event: EventV1,
    request: SnapshotBuildRequest,
) -> bool:
    policy = request.composition_policy
    instrument_ids = set(request.scope.instrument_ids)
    if event.instrument_id is None:
        return policy.include_global_events
    if not instrument_ids:
        return True
    return event.instrument_id in instrument_ids


def _signal_in_scope(signal: SignalV1, request: SnapshotBuildRequest) -> bool:
    instrument_ids = set(request.scope.instrument_ids)
    if not instrument_ids:
        return True
    if not signal.scope.instrument_ids:
        return request.composition_policy.include_global_events
    return any(instrument_id in instrument_ids for instrument_id in signal.scope.instrument_ids)


def _within_lookback(event: EventV1, *, decision_time_ns: int, lookback_ns: int | None) -> bool:
    if lookback_ns is None:
        return True
    earliest = decision_time_ns - lookback_ns
    return event.available_time_ns >= earliest


def _event_quality_excluded(findings: tuple[Any, ...]) -> bool:
    for finding in findings:
        if finding.code in _HARD_EXCLUDE_FINDING_CODES:
            return True
        if finding.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL}:
            return True
    return False


def _select_event_candidates(
    events: tuple[EventV1, ...],
    *,
    request: SnapshotBuildRequest,
    event_findings: dict[str, tuple[Any, ...]],
    excluded: list[SnapshotExclusion],
) -> tuple[EventV1, ...]:
    policy = request.composition_policy
    selected: list[EventV1] = []
    seen: set[str] = set()

    eligible = select_events_as_of(
        events,
        request.decision_time_ns,
        require_usable=policy.require_usable_events,
    )
    eligible_ids = {event.event_id for event in eligible}

    for event in events:
        if event.event_id in seen:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.DUPLICATE,
                )
            )
            continue
        seen.add(event.event_id)

        if not _event_in_scope(event, request):
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.OUTSIDE_SCOPE,
                )
            )
            continue

        if policy.event_types and event.event_type.upper() not in policy.event_types:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.CAPABILITY_NOT_REQUIRED,
                )
            )
            continue

        if not _within_lookback(
            event,
            decision_time_ns=request.decision_time_ns,
            lookback_ns=policy.lookback_ns,
        ):
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.OUTSIDE_WINDOW,
                )
            )
            continue

        if event.event_id not in eligible_ids:
            report = inspect_event_temporal_integrity(event, decision_time_ns=request.decision_time_ns)
            reason = ExclusionReason.FUTURE
            if report.violations and not report.eligible:
                if any(v.code.value == "FUTURE_INFORMATION" for v in report.violations):
                    reason = ExclusionReason.FUTURE
                else:
                    reason = ExclusionReason.STALE_UNUSABLE
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=reason,
                )
            )
            continue

        findings = event_findings.get(event.event_id, ())
        if _event_quality_excluded(findings):
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.QUALITY_REJECTED,
                )
            )
            continue

        if event.quality.state == QualityState.INVALID:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.QUALITY_REJECTED,
                )
            )
            continue

        selected.append(event)

    ordered = sorted(selected, key=event_sort_key)
    if len(ordered) > policy.max_events:
        for event in ordered[policy.max_events :]:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.EVENT.value,
                    record_id=event.event_id,
                    reason=ExclusionReason.LIMIT_TRUNCATED,
                )
            )
        ordered = ordered[: policy.max_events]
    return tuple(ordered)


def _select_signal_candidates(
    signals: tuple[SignalV1, ...],
    *,
    request: SnapshotBuildRequest,
    excluded: list[SnapshotExclusion],
) -> tuple[SignalV1, ...]:
    policy = request.composition_policy
    if not policy.include_signals:
        for signal in signals:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.CAPABILITY_NOT_REQUIRED,
                )
            )
        return ()

    selected: list[SignalV1] = []
    seen: set[str] = set()
    for signal in signals:
        if signal.signal_id in seen:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.DUPLICATE,
                )
            )
            continue
        seen.add(signal.signal_id)

        if not _signal_in_scope(signal, request):
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.OUTSIDE_SCOPE,
                )
            )
            continue

        report = inspect_signal_temporal_integrity(signal, decision_time_ns=request.decision_time_ns)
        if not report.eligible:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.FUTURE,
                )
            )
            continue

        if signal.quality.state == QualityState.INVALID:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.QUALITY_REJECTED,
                )
            )
            continue

        selected.append(signal)

    ordered = sorted(selected, key=lambda row: (row.as_of_time_ns, row.signal_id))
    if len(ordered) > policy.max_signals:
        for signal in ordered[policy.max_signals :]:
            excluded.append(
                SnapshotExclusion(
                    record_kind=ContractKind.SIGNAL.value,
                    record_id=signal.signal_id,
                    reason=ExclusionReason.LIMIT_TRUNCATED,
                )
            )
        ordered = ordered[: policy.max_signals]
    return tuple(ordered)


def _event_refs(events: tuple[EventV1, ...]) -> tuple[ContractReference, ...]:
    return tuple(
        ContractReference(kind=ContractKind.EVENT.value, id=event.event_id) for event in events
    )


def _signal_refs(signals: tuple[SignalV1, ...]) -> tuple[ContractReference, ...]:
    return tuple(
        ContractReference(kind=ContractKind.SIGNAL.value, id=signal.signal_id) for signal in signals
    )


def _snapshot_quality(decision: QualityDecision) -> QualitySummary:
    """Derive BUILD 01 summary from assessment with decision fallback."""
    summary = quality_summary_from_assessment(decision.assessment)
    if summary.state == QualityState.UNKNOWN and decision.quality_state != QualityState.UNKNOWN:
        return QualitySummary(state=decision.quality_state, flags=summary.flags)
    return summary


def _policy_metadata(policy: SnapshotCompositionPolicy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "max_events": policy.max_events,
        "max_signals": policy.max_signals,
        "lookback_ns": policy.lookback_ns,
        "event_types": list(policy.event_types),
        "include_global_events": policy.include_global_events,
        "include_signals": policy.include_signals,
        "allow_degraded": policy.allow_degraded,
        "require_usable_events": policy.require_usable_events,
    }


def _quality_allows_snapshot(
    decision: QualityDecision,
    *,
    policy: SnapshotCompositionPolicy,
) -> bool:
    if decision.action == DecisionAction.USE:
        return True
    if decision.action == DecisionAction.DEGRADE:
        return policy.allow_degraded
    return False


def compose_snapshot(
    *,
    request: SnapshotBuildRequest,
    quality_decision: QualityDecision,
    selected_events: tuple[EventV1, ...],
    selected_signals: tuple[SignalV1, ...],
) -> tuple[SnapshotV1, str]:
    """Pure deterministic composition from fixed inputs."""
    quality = _snapshot_quality(quality_decision)
    component_refs = (_builder_component_ref(),)
    fingerprint = fingerprint_from_snapshot_parts(
        decision_time_ns=request.decision_time_ns,
        scope=request.scope,
        quality=quality,
        source_event_refs=_event_refs(selected_events),
        source_signal_refs=_signal_refs(selected_signals),
        component_refs=component_refs,
        composition_policy=request.composition_policy,
    )
    snapshot = SnapshotV1(
        snapshot_id=snapshot_id_from_fingerprint(fingerprint),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        decision_time_ns=request.decision_time_ns,
        scope=request.scope,
        quality=quality,
        source_event_refs=_event_refs(selected_events),
        source_signal_refs=_signal_refs(selected_signals),
        component_refs=component_refs,
        metadata={
            "content_fingerprint": fingerprint,
            "fingerprint_version": FINGERPRINT_VERSION,
            "composition_policy_id": request.composition_policy.policy_id,
            "composition_policy_version": request.composition_policy.policy_version,
            "composition_policy": _policy_metadata(request.composition_policy),
        },
    )
    return snapshot, fingerprint


def inspect_snapshot_build(
    repository: IntelligenceRepository,
    request: SnapshotBuildRequest,
    *,
    quality_decision: QualityDecision | None = None,
    provider_health: tuple[Any, ...] = (),
    temporal_policy: TemporalIntegrityPolicy | None = None,
    quality_policy: QualityPolicy | None = None,
) -> SnapshotBuildResult:
    """Non-throwing diagnostic snapshot composition."""
    excluded: list[SnapshotExclusion] = []
    instrument_id = request.scope.instrument_ids[0] if len(request.scope.instrument_ids) == 1 else None

    raw_events = repository.query_events_as_of(
        request.decision_time_ns,
        instrument_id=instrument_id,
        limit=request.composition_policy.max_events * 4,
        require_usable=False,
        policy=temporal_policy,
    )
    if request.composition_policy.include_global_events and instrument_id is not None:
        global_events = repository.query_events_as_of(
            request.decision_time_ns,
            instrument_id=None,
            limit=request.composition_policy.max_events * 4,
            require_usable=False,
            policy=temporal_policy,
        )
        raw_events = tuple({event.event_id: event for event in (*raw_events, *global_events)}.values())

    raw_signals: tuple[SignalV1, ...] = ()
    if request.composition_policy.include_signals:
        raw_signals = repository.query_signals_as_of(
            request.decision_time_ns,
            instrument_id=instrument_id,
            limit=request.composition_policy.max_signals * 4,
            policy=temporal_policy,
        )

    assessment = inspect_quality(
        events=raw_events,
        decision_time_ns=request.decision_time_ns,
        requirements=request.capability_requirements,
        provider_health=provider_health,
        temporal_policy=temporal_policy,
        policy=quality_policy,
    )
    decision = quality_decision or assess_capabilities(
        events=raw_events,
        decision_time_ns=request.decision_time_ns,
        requirements=request.capability_requirements,
        provider_health=provider_health,
        temporal_policy=temporal_policy,
        policy=quality_policy,
    )

    event_findings = {
        event.event_id: tuple(
            finding
            for finding in assessment.findings
            if finding.event_id == event.event_id
        )
        for event in raw_events
    }

    selected_events = _select_event_candidates(
        raw_events,
        request=request,
        event_findings=event_findings,
        excluded=excluded,
    )
    selected_signals = _select_signal_candidates(raw_signals, request=request, excluded=excluded)

    if not _quality_allows_snapshot(decision, policy=request.composition_policy):
        return SnapshotBuildResult(
            snapshot=None,
            quality_decision=decision,
            content_fingerprint="",
            selected_event_ids=tuple(event.event_id for event in selected_events),
            selected_signal_ids=tuple(signal.signal_id for signal in selected_signals),
            excluded=tuple(excluded),
            diagnostics={
                "quality_action": decision.action.value,
                "eligible_event_count": len(selected_events),
                "eligible_signal_count": len(selected_signals),
            },
        )

    snapshot, fingerprint = compose_snapshot(
        request=request,
        quality_decision=decision,
        selected_events=selected_events,
        selected_signals=selected_signals,
    )
    return SnapshotBuildResult(
        snapshot=snapshot,
        quality_decision=decision,
        content_fingerprint=fingerprint,
        selected_event_ids=tuple(event.event_id for event in selected_events),
        selected_signal_ids=tuple(signal.signal_id for signal in selected_signals),
        excluded=tuple(excluded),
        diagnostics={
            "quality_action": decision.action.value,
            "eligible_event_count": len(selected_events),
            "eligible_signal_count": len(selected_signals),
        },
    )


def build_snapshot(
    repository: IntelligenceRepository,
    request: SnapshotBuildRequest,
    *,
    quality_decision: QualityDecision | None = None,
    provider_health: tuple[Any, ...] = (),
    temporal_policy: TemporalIntegrityPolicy | None = None,
    quality_policy: QualityPolicy | None = None,
    persist: bool = True,
) -> SnapshotBuildResult:
    """Strict snapshot build — raises on quality/temporal/reference failure."""
    result = inspect_snapshot_build(
        repository,
        request,
        quality_decision=quality_decision,
        provider_health=provider_health,
        temporal_policy=temporal_policy,
        quality_policy=quality_policy,
    )
    decision = result.quality_decision
    if decision.action == DecisionAction.FAIL_CLOSED:
        raise SnapshotQualityError(
            f"SNAPSHOT_QUALITY_FAIL_CLOSED:{','.join(decision.reasons) or decision.action.value}",
            decision=decision,
        )
    if decision.action == DecisionAction.ABSTAIN:
        raise SnapshotQualityError(
            f"SNAPSHOT_QUALITY_ABSTAIN:{','.join(decision.reasons) or decision.action.value}",
            decision=decision,
        )
    if not _quality_allows_snapshot(decision, policy=request.composition_policy):
        raise SnapshotQualityError(
            "SNAPSHOT_QUALITY_NOT_PERMITTED",
            decision=decision,
        )
    if result.snapshot is None:
        raise SnapshotBuildError("SNAPSHOT_BUILD_FAILED_WITHOUT_ARTIFACT")

    resolver = RepositoryTemporalResolver(repository)
    report = validate_snapshot_temporal_integrity(
        result.snapshot,
        resolver=resolver,
        policy=temporal_policy,
    )
    try:
        require_snapshot_temporally_valid(
            result.snapshot,
            resolver=resolver,
            policy=temporal_policy,
        )
    except TemporalIntegrityError as exc:
        raise SnapshotTemporalError(str(exc), report=report, cause=exc) from exc

    if persist:
        repository.put_snapshot(result.snapshot)
    return result


class SnapshotBuilder:
    """Orchestrates repository-backed immutable snapshot composition."""

    def __init__(self, repository: IntelligenceRepository) -> None:
        self._repository = repository

    def inspect(
        self,
        request: SnapshotBuildRequest,
        *,
        quality_decision: QualityDecision | None = None,
        provider_health: tuple[Any, ...] = (),
        temporal_policy: TemporalIntegrityPolicy | None = None,
        quality_policy: QualityPolicy | None = None,
    ) -> SnapshotBuildResult:
        return inspect_snapshot_build(
            self._repository,
            request,
            quality_decision=quality_decision,
            provider_health=provider_health,
            temporal_policy=temporal_policy,
            quality_policy=quality_policy,
        )

    def build(
        self,
        request: SnapshotBuildRequest,
        *,
        quality_decision: QualityDecision | None = None,
        provider_health: tuple[Any, ...] = (),
        temporal_policy: TemporalIntegrityPolicy | None = None,
        quality_policy: QualityPolicy | None = None,
        persist: bool = True,
    ) -> SnapshotBuildResult:
        return build_snapshot(
            self._repository,
            request,
            quality_decision=quality_decision,
            provider_health=provider_health,
            temporal_policy=temporal_policy,
            quality_policy=quality_policy,
            persist=persist,
        )


def verify_snapshot_reproducibility(
    repository: IntelligenceRepository,
    *,
    request: SnapshotBuildRequest,
    existing_snapshot: SnapshotV1,
    quality_decision: QualityDecision | None = None,
    provider_health: tuple[Any, ...] = (),
    temporal_policy: TemporalIntegrityPolicy | None = None,
    quality_policy: QualityPolicy | None = None,
) -> str:
    """Recompose and verify identical semantic fingerprint."""
    result = inspect_snapshot_build(
        repository,
        request,
        quality_decision=quality_decision,
        provider_health=provider_health,
        temporal_policy=temporal_policy,
        quality_policy=quality_policy,
    )
    if result.snapshot is None:
        raise SnapshotBuildError("REPRODUCIBILITY_RECOMPOSE_FAILED")
    metadata = existing_snapshot.metadata or {}
    expected = metadata.get("content_fingerprint")
    if expected is not None and result.content_fingerprint != expected:
        raise SnapshotBuildError(
            f"REPRODUCIBILITY_FINGERPRINT_MISMATCH:{expected}!={result.content_fingerprint}",
        )
    if result.snapshot.snapshot_id != existing_snapshot.snapshot_id:
        raise SnapshotBuildError(
            f"REPRODUCIBILITY_ID_MISMATCH:{existing_snapshot.snapshot_id}!={result.snapshot.snapshot_id}",
        )
    return result.content_fingerprint


__all__ = [
    "ExclusionReason",
    "SnapshotBuildResult",
    "SnapshotBuilder",
    "SnapshotExclusion",
    "build_snapshot",
    "compose_snapshot",
    "inspect_snapshot_build",
    "verify_snapshot_reproducibility",
]
