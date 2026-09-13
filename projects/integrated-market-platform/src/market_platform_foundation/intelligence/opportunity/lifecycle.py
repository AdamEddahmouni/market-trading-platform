"""Operator review-row lifecycle. Not an enum on frozen OpportunityV1."""

from __future__ import annotations

from enum import StrEnum

from .types import AssessmentAction


class OperatorLifecycleState(StrEnum):
    DETECTED = "DETECTED"
    NORMALIZED = "NORMALIZED"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    RANKED = "RANKED"
    REVIEWED = "REVIEWED"
    WATCHED = "WATCHED"
    DISMISSED = "DISMISSED"
    PAPER_PREVIEWED = "PAPER_PREVIEWED"
    EXPIRED = "EXPIRED"


_ACK_STATES = {
    OperatorLifecycleState.REVIEWED,
    OperatorLifecycleState.WATCHED,
    OperatorLifecycleState.DISMISSED,
    OperatorLifecycleState.PAPER_PREVIEWED,
}


class OperatorLifecycleError(ValueError):
    """Illegal operator-lifecycle transition."""


def derive_lifecycle_from_assessment(action: AssessmentAction | str | None) -> OperatorLifecycleState:
    if action is None:
        return OperatorLifecycleState.NORMALIZED
    value = AssessmentAction(str(action))
    if value == AssessmentAction.EMIT:
        return OperatorLifecycleState.ELIGIBLE
    return OperatorLifecycleState.INELIGIBLE


def apply_operator_ack(
    current: OperatorLifecycleState | str,
    ack: OperatorLifecycleState | str,
) -> OperatorLifecycleState:
    current_state = OperatorLifecycleState(str(current))
    ack_state = OperatorLifecycleState(str(ack))
    if ack_state not in _ACK_STATES:
        raise OperatorLifecycleError("OPERATOR_ACK_INVALID")
    if current_state == OperatorLifecycleState.DISMISSED and ack_state != OperatorLifecycleState.DISMISSED:
        raise OperatorLifecycleError("OPERATOR_LIFECYCLE_ILLEGAL_TRANSITION")
    return ack_state
