"""Structured quality/capability errors (BUILD 04)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import QualityState
from .models import DecisionAction, IntelligenceCapability, QualityDecision


class QualityCapabilityError(ValueError):
    """Fail-closed quality enforcement error with structured context."""

    def __init__(
        self,
        message: str,
        *,
        decision: QualityDecision,
        finding_codes: tuple[str, ...] = (),
        missing_capabilities: tuple[IntelligenceCapability, ...] = (),
    ) -> None:
        super().__init__(message)
        self.decision = decision
        self.action = decision.action
        self.quality_state = decision.quality_state
        self.finding_codes = finding_codes
        self.missing_capabilities = missing_capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "action": self.action.value,
            "quality_state": self.quality_state.value,
            "finding_codes": list(self.finding_codes),
            "missing_capabilities": [cap.value for cap in self.missing_capabilities],
            "policy_id": self.decision.assessment.policy_id,
            "policy_version": self.decision.assessment.policy_version,
            "decision_time_ns": self.decision.assessment.decision_time_ns,
        }


def raise_if_fail_closed(decision: QualityDecision) -> None:
    if decision.action != DecisionAction.FAIL_CLOSED:
        return
    codes = tuple(sorted({finding.code for finding in decision.assessment.findings}))
    raise QualityCapabilityError(
        f"QUALITY_FAIL_CLOSED: {', '.join(decision.reasons) or 'hard quality invariant violated'}",
        decision=decision,
        finding_codes=codes,
        missing_capabilities=decision.missing_requirements,
    )


__all__ = ["QualityCapabilityError", "raise_if_fail_closed"]
