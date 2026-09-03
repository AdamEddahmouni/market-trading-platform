from .identifiers import deterministic_acquisition_id
from .models import BoundaryEvidence, BoundaryRule, DetectionBoundaryFreeze


_OUTCOME_AWARE_RULES = {BoundaryRule.MAXIMUM_LATER_RETURN}


def freeze_detection_boundary(
    *, case_attempt_id: str, symbol: str, evidence: tuple[BoundaryEvidence, ...],
    rule: BoundaryRule,
) -> DetectionBoundaryFreeze:
    boundary_id = deterministic_acquisition_id({
        "result_type": "DETECTION_BOUNDARY", "case_attempt_id": case_attempt_id,
        "symbol": symbol.strip().upper(), "rule": rule,
    })
    if rule in _OUTCOME_AWARE_RULES:
        return DetectionBoundaryFreeze(
            boundary_id=boundary_id, case_attempt_id=case_attempt_id, symbol=symbol,
            boundary_rule=rule, frozen_before_outcome_access=False, review_status="REJECTED",
            diagnostic_codes=("OUTCOME_AWARE_BOUNDARY_REJECTED",),
        )
    candidates = tuple(evidence)
    if rule is BoundaryRule.FIRST_ELIGIBLE_COMPLETED_BAR_AT_OR_AFTER_DISCOVERY:
        candidates = tuple(item for item in candidates if item.completed_bar)
    elif rule is BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP:
        candidates = tuple(item for item in candidates if item.original_platform_surfaced)
    elif rule is BoundaryRule.MANUALLY_RECONSTRUCTED_WITH_EVIDENCE:
        candidates = tuple(item for item in candidates if item.manual_review_approved)
    if not candidates:
        return DetectionBoundaryFreeze(
            boundary_id=boundary_id, case_attempt_id=case_attempt_id, symbol=symbol,
            boundary_rule=rule, frozen_before_outcome_access=True, review_status="BLOCKED",
            diagnostic_codes=("DETECTION_BOUNDARY_UNRESOLVED",),
        )
    selected = min(candidates, key=lambda item: (item.timestamp, item.source_artifact_id))
    return DetectionBoundaryFreeze(
        boundary_id=boundary_id, case_attempt_id=case_attempt_id, symbol=symbol,
        boundary_timestamp=selected.timestamp, boundary_source="DISCOVERY_EVIDENCE",
        boundary_source_artifact_id=selected.source_artifact_id, boundary_rule=rule,
        frozen_before_outcome_access=True, review_status="FROZEN",
    )


__all__ = ["freeze_detection_boundary"]
