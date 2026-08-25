"""Convert detailed assessments to BUILD 01 QualitySummary."""

from __future__ import annotations

from ..contracts.common import QualityState, QualitySummary
from .models import DecisionAction, FindingSeverity, QualityAssessment, QualityFindingCode


_INVALID_CODES = frozenset(
    {
        QualityFindingCode.CROSSED_BOOK.value,
        QualityFindingCode.INVALID_QUOTE.value,
        QualityFindingCode.FUTURE_INFORMATION.value,
        QualityFindingCode.PROVIDER_DISCONNECTED.value,
    }
)


def quality_summary_from_assessment(assessment: QualityAssessment) -> QualitySummary:
    """Deterministically compress a detailed assessment into BUILD 01 summary."""
    flags: list[str] = []
    has_error = False
    has_warning = False
    for finding in assessment.findings:
        if finding.code not in flags:
            flags.append(finding.code)
        if finding.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL}:
            has_error = True
        elif finding.severity == FindingSeverity.WARNING:
            has_warning = True

    if any(code in _INVALID_CODES for code in flags):
        state = QualityState.INVALID
    elif has_error:
        state = QualityState.INVALID
    elif has_warning or flags:
        state = QualityState.DEGRADED
    elif assessment.capability_assessments:
        states = {row.quality_state for row in assessment.capability_assessments}
        if QualityState.INVALID in states:
            state = QualityState.INVALID
        elif QualityState.UNKNOWN in states and QualityState.GOOD not in states:
            state = QualityState.UNKNOWN
        elif QualityState.DEGRADED in states or QualityState.UNKNOWN in states:
            state = QualityState.DEGRADED
        else:
            state = QualityState.GOOD
    else:
        state = QualityState.UNKNOWN

    return QualitySummary(state=state, flags=tuple(flags))


def quality_state_for_action(action: DecisionAction, assessment: QualityAssessment) -> QualityState:
    if action == DecisionAction.USE:
        return QualityState.GOOD
    if action == DecisionAction.DEGRADE:
        return QualityState.DEGRADED
    if action == DecisionAction.ABSTAIN:
        return QualityState.DEGRADED
    summary = quality_summary_from_assessment(assessment)
    if summary.state == QualityState.UNKNOWN:
        return QualityState.INVALID
    return QualityState.INVALID


__all__ = ["quality_state_for_action", "quality_summary_from_assessment"]
