"""Capability-aware source selection (BUILD 04)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import QualityState
from .models import CapabilityAssessment, DecisionAction, IntelligenceCapability, QualityFindingCode
from .policy import QualityPolicy


@dataclass(frozen=True, slots=True)
class SourceSelectionResult:
    """Deterministic source selection without network side effects."""

    capability: IntelligenceCapability
    selected_provider_id: str | None
    alternatives: tuple[str, ...]
    quality_state: QualityState
    action: DecisionAction
    reason: str
    retained_conflict: bool = False


def select_usable_source(
    capability: IntelligenceCapability,
    *,
    provider_assessments: tuple[CapabilityAssessment, ...],
    instrument_id: str | None = None,
    policy: QualityPolicy | None = None,
) -> SourceSelectionResult:
    """Select the best eligible provider for a capability."""
    _ = policy
    scoped = [
        row
        for row in provider_assessments
        if row.capability == capability and (instrument_id is None or row.instrument_id == instrument_id)
    ]
    usable = [
        row
        for row in scoped
        if row.quality_state in {QualityState.GOOD, QualityState.DEGRADED}
        and row.dimensions.temporally_legal is not False
    ]
    usable_sorted = sorted(
        usable,
        key=lambda row: (
            0 if row.quality_state == QualityState.GOOD else 1,
            row.provider_id,
        ),
    )
    conflict = any(
        finding.code == QualityFindingCode.PROVIDER_CONFLICT.value for row in scoped for finding in row.findings
    )
    if not usable_sorted:
        return SourceSelectionResult(
            capability=capability,
            selected_provider_id=None,
            alternatives=tuple(sorted({row.provider_id for row in scoped})),
            quality_state=QualityState.INVALID,
            action=DecisionAction.ABSTAIN,
            reason="no eligible provider",
            retained_conflict=conflict,
        )
    selected = usable_sorted[0]
    alternatives = tuple(row.provider_id for row in usable_sorted[1:])
    action = DecisionAction.USE if selected.quality_state == QualityState.GOOD else DecisionAction.DEGRADE
    reason = "primary healthy source" if not alternatives else "fallback to next healthy source"
    if conflict:
        reason = f"{reason}; provider conflict retained"
        if selected.quality_state == QualityState.DEGRADED:
            action = DecisionAction.DEGRADE
    return SourceSelectionResult(
        capability=capability,
        selected_provider_id=selected.provider_id,
        alternatives=alternatives,
        quality_state=selected.quality_state,
        action=action,
        reason=reason,
        retained_conflict=conflict,
    )


__all__ = ["SourceSelectionResult", "select_usable_source"]
