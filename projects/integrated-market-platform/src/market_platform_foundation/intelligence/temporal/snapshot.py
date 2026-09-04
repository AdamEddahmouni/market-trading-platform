"""Snapshot and signal temporal audit helpers (BUILD 02)."""

from __future__ import annotations

from ..contracts.snapshot import SnapshotV1
from .models import (
    TemporalIntegrityError,
    TemporalIntegrityReport,
    TemporalViolation,
    TemporalViolationCode,
    TemporalViolationSeverity,
)
from .policy import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy
from .resolver import TemporalReferenceResolver
from .validation import inspect_event_temporal_integrity, inspect_signal_temporal_integrity


def validate_snapshot_temporal_integrity(
    snapshot: SnapshotV1,
    *,
    resolver: TemporalReferenceResolver,
    policy: TemporalIntegrityPolicy | None = None,
) -> TemporalIntegrityReport:
    """Non-throwing audit that snapshot sources were knowable at decision time."""
    active = policy or DEFAULT_TEMPORAL_POLICY
    decision_time_ns = snapshot.decision_time_ns
    violations: list[TemporalViolation] = []
    eligible = True
    usable = True

    for ref in snapshot.source_event_refs:
        event = resolver.resolve_event(ref)
        if event is None:
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.MISSING_REFERENCE,
                    severity=TemporalViolationSeverity.ERROR,
                    message=f"MISSING_REFERENCE: snapshot {snapshot.snapshot_id} missing event {ref.id}",
                    record_kind="snapshot",
                    record_id=snapshot.snapshot_id,
                    decision_time_ns=decision_time_ns,
                )
            )
            eligible = False
            usable = False
            continue
        event_report = inspect_event_temporal_integrity(
            event, decision_time_ns=decision_time_ns, policy=active
        )
        violations.extend(event_report.violations)
        if not event_report.eligible:
            eligible = False
        if not event_report.usable:
            usable = False

    for ref in snapshot.source_signal_refs:
        signal = resolver.resolve_signal(ref)
        if signal is None:
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.MISSING_REFERENCE,
                    severity=TemporalViolationSeverity.ERROR,
                    message=f"MISSING_REFERENCE: snapshot {snapshot.snapshot_id} missing signal {ref.id}",
                    record_kind="snapshot",
                    record_id=snapshot.snapshot_id,
                    decision_time_ns=decision_time_ns,
                )
            )
            eligible = False
            usable = False
            continue
        signal_report = inspect_signal_temporal_integrity(
            signal, decision_time_ns=decision_time_ns, policy=active
        )
        violations.extend(signal_report.violations)
        if not signal_report.eligible:
            eligible = False
        if not signal_report.usable:
            usable = False

        for event_ref in signal.source_event_refs:
            event = resolver.resolve_event(event_ref)
            if event is None:
                continue
            nested = inspect_event_temporal_integrity(
                event, decision_time_ns=decision_time_ns, policy=active
            )
            violations.extend(nested.violations)
            if not nested.eligible:
                eligible = False
            if not nested.usable:
                usable = False

    if any(v.code == TemporalViolationCode.FUTURE_INFORMATION for v in violations):
        eligible = False
        usable = False

    return TemporalIntegrityReport(eligible=eligible, usable=usable, violations=tuple(violations))


def require_snapshot_temporally_valid(
    snapshot: SnapshotV1,
    *,
    resolver: TemporalReferenceResolver,
    policy: TemporalIntegrityPolicy | None = None,
) -> None:
    """Fail closed when snapshot sources violate temporal integrity."""
    report = validate_snapshot_temporal_integrity(snapshot, resolver=resolver, policy=policy)
    if report.eligible and not report.hard_failures:
        if report.usable:
            return
        primary = next(
            (v for v in report.violations if v.code == TemporalViolationCode.STALE_INFORMATION),
            report.violations[0] if report.violations else None,
        )
        if primary is None:
            return
        raise TemporalIntegrityError(
            primary.message,
            code=primary.code,
            record_kind=primary.record_kind,
            record_id=primary.record_id,
            decision_time_ns=primary.decision_time_ns,
            relevant_time_ns=primary.relevant_time_ns,
            delta_ns=primary.delta_ns,
            violations=report.violations,
        )
    primary = report.hard_failures[0] if report.hard_failures else report.violations[0]
    raise TemporalIntegrityError(
        primary.message,
        code=primary.code,
        record_kind=primary.record_kind,
        record_id=primary.record_id,
        decision_time_ns=primary.decision_time_ns,
        relevant_time_ns=primary.relevant_time_ns,
        delta_ns=primary.delta_ns,
        violations=report.violations,
    )


__all__ = [
    "require_snapshot_temporally_valid",
    "validate_snapshot_temporal_integrity",
]
