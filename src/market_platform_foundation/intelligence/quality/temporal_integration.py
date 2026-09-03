"""Map BUILD 02 temporal reports to BUILD 04 quality findings."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..temporal.models import TemporalIntegrityReport, TemporalViolationCode, TemporalViolationSeverity
from .models import FindingSeverity, QualityFinding, QualityFindingCode, capability_for_event_type


_TEMPORAL_TO_QUALITY: dict[TemporalViolationCode, str] = {
    TemporalViolationCode.FUTURE_INFORMATION: QualityFindingCode.FUTURE_INFORMATION.value,
    TemporalViolationCode.STALE_INFORMATION: QualityFindingCode.STALE_INFORMATION.value,
    TemporalViolationCode.CLOCK_SKEW: QualityFindingCode.CLOCK_DRIFT.value,
    TemporalViolationCode.OUT_OF_ORDER: QualityFindingCode.OUT_OF_ORDER.value,
    TemporalViolationCode.EXACT_DUPLICATE: QualityFindingCode.EXACT_DUPLICATE.value,
    TemporalViolationCode.CONFLICTING_DUPLICATE: QualityFindingCode.CONFLICTING_DUPLICATE.value,
}


def _severity_from_temporal(severity: TemporalViolationSeverity) -> FindingSeverity:
    if severity == TemporalViolationSeverity.ERROR:
        return FindingSeverity.ERROR
    if severity == TemporalViolationSeverity.WARNING:
        return FindingSeverity.WARNING
    return FindingSeverity.INFO


def findings_from_temporal_report(
    event: EventV1,
    report: TemporalIntegrityReport,
) -> tuple[QualityFinding, ...]:
    """Translate temporal diagnostics into objective quality findings."""
    capability = capability_for_event_type(event.event_type)
    findings: list[QualityFinding] = []
    for violation in report.violations:
        code = _TEMPORAL_TO_QUALITY.get(violation.code, violation.code.value)
        findings.append(
            QualityFinding(
                code=code,
                severity=_severity_from_temporal(violation.severity),
                message=violation.message,
                provider_id=event.source.provider_id,
                capability=capability,
                instrument_id=event.instrument_id,
                observed_at_ns=event.available_time_ns,
                event_id=event.event_id,
                evidence={
                    "temporal_code": violation.code.value,
                    "delta_ns": violation.delta_ns,
                    "policy_context": violation.policy_context,
                },
            )
        )
    return tuple(findings)


def is_future_information(report: TemporalIntegrityReport) -> bool:
    return any(v.code == TemporalViolationCode.FUTURE_INFORMATION for v in report.violations)


__all__ = ["findings_from_temporal_report", "is_future_information"]
