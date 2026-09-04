"""Core temporal inspection and fail-closed enforcement (BUILD 02)."""

from __future__ import annotations

from typing import Any

from ..contracts.event import EventV1, event_v1_to_dict
from ..contracts.signal import SignalV1
from .models import (
    TemporalEligibility,
    TemporalIntegrityError,
    TemporalIntegrityReport,
    TemporalViolation,
    TemporalViolationCode,
    TemporalViolationSeverity,
)
from .policy import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy


def _event_semantic_fingerprint(event: EventV1) -> tuple[Any, ...]:
    body = event_v1_to_dict(event)
    return (
        body["event_type"],
        body["event_time_ns"],
        body["available_time_ns"],
        body.get("provider_time_ns"),
        body.get("received_time_ns"),
        body.get("instrument_id"),
        body["payload"],
        body.get("metadata") or {},
    )


def event_sort_key(event: EventV1) -> tuple[int, int, int, str]:
    """Stable deterministic ordering for point-in-time selection."""
    return (
        event.available_time_ns,
        event.received_time_ns if event.received_time_ns is not None else 0,
        event.event_time_ns,
        event.event_id,
    )


def inspect_event_temporal_integrity(
    event: EventV1,
    *,
    decision_time_ns: int,
    policy: TemporalIntegrityPolicy | None = None,
) -> TemporalIntegrityReport:
    """Non-throwing temporal inspection for a single event."""
    active = policy or DEFAULT_TEMPORAL_POLICY
    violations: list[TemporalViolation] = []
    record_kind = "event"
    record_id = event.event_id

    if event.available_time_ns > decision_time_ns:
        delta = event.available_time_ns - decision_time_ns
        violations.append(
            TemporalViolation(
                code=TemporalViolationCode.FUTURE_INFORMATION,
                severity=TemporalViolationSeverity.ERROR,
                message=(
                    f"FUTURE_INFORMATION: event {record_id} available at {event.available_time_ns}ns, "
                    f"after decision cutoff {decision_time_ns}ns"
                ),
                record_kind=record_kind,
                record_id=record_id,
                decision_time_ns=decision_time_ns,
                relevant_time_ns=event.available_time_ns,
                delta_ns=delta,
            )
        )
        return TemporalIntegrityReport(eligible=False, usable=False, violations=tuple(violations))

    eligible = True

    if active.require_event_time_before_decision and event.event_time_ns > decision_time_ns:
        violations.append(
            TemporalViolation(
                code=TemporalViolationCode.FUTURE_INFORMATION,
                severity=TemporalViolationSeverity.ERROR,
                message=(
                    f"FUTURE_INFORMATION: event {record_id} event_time {event.event_time_ns}ns "
                    f"after decision cutoff {decision_time_ns}ns"
                ),
                record_kind=record_kind,
                record_id=record_id,
                decision_time_ns=decision_time_ns,
                relevant_time_ns=event.event_time_ns,
                delta_ns=event.event_time_ns - decision_time_ns,
                policy_context="require_event_time_before_decision",
            )
        )
        return TemporalIntegrityReport(eligible=False, usable=False, violations=tuple(violations))

    age_ns = decision_time_ns - event.available_time_ns
    max_age = active.max_age_for_category(event.event_type)
    stale = max_age is not None and age_ns > max_age
    if stale:
        violations.append(
            TemporalViolation(
                code=TemporalViolationCode.STALE_INFORMATION,
                severity=TemporalViolationSeverity.WARNING,
                message=(
                    f"STALE_INFORMATION: event {record_id} age {age_ns}ns exceeds "
                    f"max_age {max_age}ns at decision {decision_time_ns}ns"
                ),
                record_kind=record_kind,
                record_id=record_id,
                decision_time_ns=decision_time_ns,
                relevant_time_ns=event.available_time_ns,
                delta_ns=age_ns,
            )
        )

    if (
        event.received_time_ns is not None
        and event.available_time_ns < event.received_time_ns
    ):
        violations.append(
            TemporalViolation(
                code=TemporalViolationCode.INVALID_TEMPORAL_RELATION,
                severity=TemporalViolationSeverity.WARNING,
                message=(
                    f"INVALID_TEMPORAL_RELATION: event {record_id} available_time "
                    f"{event.available_time_ns}ns precedes received_time "
                    f"{event.received_time_ns}ns"
                ),
                record_kind=record_kind,
                record_id=record_id,
                decision_time_ns=decision_time_ns,
                relevant_time_ns=event.received_time_ns,
                delta_ns=event.received_time_ns - event.available_time_ns,
            )
        )

    if event.provider_time_ns is not None and event.received_time_ns is not None:
        skew_ns = event.provider_time_ns - event.received_time_ns
        ahead_limit = active.max_provider_clock_ahead_ns
        behind_limit = active.max_provider_clock_behind_ns
        skew_violation = False
        if ahead_limit is not None and skew_ns > ahead_limit:
            skew_violation = True
        if behind_limit is not None and (-skew_ns) > behind_limit:
            skew_violation = True
        if skew_violation:
            severity = (
                TemporalViolationSeverity.ERROR
                if active.clock_skew_severity_error
                else TemporalViolationSeverity.WARNING
            )
            violations.append(
                TemporalViolation(
                    code=TemporalViolationCode.CLOCK_SKEW,
                    severity=severity,
                    message=(
                        f"CLOCK_SKEW: event {record_id} provider_time-received_time "
                        f"delta {skew_ns}ns outside configured tolerance"
                    ),
                    record_kind=record_kind,
                    record_id=record_id,
                    decision_time_ns=decision_time_ns,
                    relevant_time_ns=event.provider_time_ns,
                    delta_ns=skew_ns,
                )
            )

    usable = eligible
    if stale and active.reject_stale_for_usability:
        usable = False
    if any(v.severity == TemporalViolationSeverity.ERROR for v in violations):
        usable = False

    return TemporalIntegrityReport(eligible=eligible, usable=usable, violations=tuple(violations))


def inspect_signal_temporal_integrity(
    signal: SignalV1,
    *,
    decision_time_ns: int,
    policy: TemporalIntegrityPolicy | None = None,
) -> TemporalIntegrityReport:
    """Non-throwing temporal inspection for a signal against a decision cutoff."""
    _ = policy  # reserved for future signal-specific freshness rules
    violations: list[TemporalViolation] = []
    if signal.as_of_time_ns > decision_time_ns:
        delta = signal.as_of_time_ns - decision_time_ns
        violations.append(
            TemporalViolation(
                code=TemporalViolationCode.SIGNAL_AS_OF_AFTER_DECISION,
                severity=TemporalViolationSeverity.ERROR,
                message=(
                    f"SIGNAL_AS_OF_AFTER_DECISION: signal {signal.signal_id} as_of_time "
                    f"{signal.as_of_time_ns}ns after decision cutoff {decision_time_ns}ns"
                ),
                record_kind="signal",
                record_id=signal.signal_id,
                decision_time_ns=decision_time_ns,
                relevant_time_ns=signal.as_of_time_ns,
                delta_ns=delta,
            )
        )
        return TemporalIntegrityReport(eligible=False, usable=False, violations=tuple(violations))
    return TemporalIntegrityReport(eligible=True, usable=True)


def inspect_temporal_integrity(
    record: EventV1 | SignalV1,
    *,
    decision_time_ns: int,
    policy: TemporalIntegrityPolicy | None = None,
) -> TemporalIntegrityReport:
    """Dispatch non-throwing temporal inspection by record kind."""
    if isinstance(record, EventV1):
        return inspect_event_temporal_integrity(record, decision_time_ns=decision_time_ns, policy=policy)
    if isinstance(record, SignalV1):
        return inspect_signal_temporal_integrity(record, decision_time_ns=decision_time_ns, policy=policy)
    raise TypeError(f"UNSUPPORTED_TEMPORAL_RECORD:{type(record).__name__}")


def temporal_eligibility(
    event: EventV1,
    *,
    decision_time_ns: int,
    policy: TemporalIntegrityPolicy | None = None,
) -> TemporalEligibility:
    report = inspect_event_temporal_integrity(event, decision_time_ns=decision_time_ns, policy=policy)
    return TemporalEligibility(eligible=report.eligible, usable=report.usable)


def is_temporally_eligible(
    event: EventV1,
    *,
    decision_time_ns: int,
) -> bool:
    """Availability-only eligibility — anti-lookahead gate."""
    return event.available_time_ns <= decision_time_ns


def require_temporally_usable(
    record: EventV1 | SignalV1,
    *,
    decision_time_ns: int,
    policy: TemporalIntegrityPolicy | None = None,
) -> None:
    """Fail closed when a record cannot be used at the decision point."""
    report = inspect_temporal_integrity(record, decision_time_ns=decision_time_ns, policy=policy)
    if report.usable:
        return
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


def classify_duplicate_events(
    prior: EventV1 | None,
    incoming: EventV1,
) -> TemporalViolationCode | None:
    """Classify duplicate identity relative to a prior event with the same id."""
    if prior is None:
        return None
    if _event_semantic_fingerprint(prior) == _event_semantic_fingerprint(incoming):
        return TemporalViolationCode.EXACT_DUPLICATE
    return TemporalViolationCode.CONFLICTING_DUPLICATE


__all__ = [
    "classify_duplicate_events",
    "event_sort_key",
    "inspect_event_temporal_integrity",
    "inspect_signal_temporal_integrity",
    "inspect_temporal_integrity",
    "is_temporally_eligible",
    "require_temporally_usable",
    "temporal_eligibility",
]
