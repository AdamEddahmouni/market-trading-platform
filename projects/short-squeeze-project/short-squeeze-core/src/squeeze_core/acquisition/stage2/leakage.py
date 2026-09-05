"""Post-outcome leakage audit for Phase 3E Stage 2.

Delegates to the existing Phase 3D audit engine. Outcome manifests are captured
strictly after every Phase 3A freeze stage.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from squeeze_core.acquisition.leakage_guards import audit_outcome_leakage
from squeeze_core.acquisition.models import LeakageAuditRequest, LeakageAuditResult
from squeeze_core.acquisition.phase3a_freeze.leakage import (
    BOUNDARY_INPUT_FIELDS,
    BOUNDARY_OFFSET_SECONDS,
    DISCOVERY_INPUT_FIELDS,
    ELIGIBILITY_INPUT_FIELDS,
    EVALUATION_INPUT_FIELDS,
    PLAN_OFFSET_SECONDS,
    REQUEST_OFFSET_SECONDS,
    RESULT_OFFSET_SECONDS,
)
from squeeze_core.serialization import canonical_json_bytes

from .constants import DISCOVERY_MANIFEST_ID, FROZEN_BOUNDARY

# Outcome capture sits strictly after the Phase 3A result freeze.
OUTCOME_CAPTURED_OFFSET_SECONDS = 6


def _at(boundary: datetime, offset: int) -> datetime:
    return boundary + timedelta(seconds=offset)


def build_post_outcome_audit_request(
    *,
    case_id: str,
    outcome_manifest_id: str,
    boundary: datetime = FROZEN_BOUNDARY,
    discovery_manifest_id: str = DISCOVERY_MANIFEST_ID,
) -> LeakageAuditRequest:
    """Assemble audit input with a real (post-freeze) outcome capture timestamp."""
    return LeakageAuditRequest(
        case_attempt_id=case_id,
        discovery_input_fields=DISCOVERY_INPUT_FIELDS,
        eligibility_input_fields=ELIGIBILITY_INPUT_FIELDS,
        boundary_input_fields=BOUNDARY_INPUT_FIELDS,
        evaluation_input_fields=EVALUATION_INPUT_FIELDS,
        plan_frozen_at=_at(boundary, PLAN_OFFSET_SECONDS),
        boundary_frozen_at=_at(boundary, BOUNDARY_OFFSET_SECONDS),
        evaluation_request_frozen_at=_at(boundary, REQUEST_OFFSET_SECONDS),
        evaluation_result_frozen_at=_at(boundary, RESULT_OFFSET_SECONDS),
        outcome_captured_at=_at(boundary, OUTCOME_CAPTURED_OFFSET_SECONDS),
        discovery_manifest_id=discovery_manifest_id,
        outcome_manifest_id=outcome_manifest_id,
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )


def audit_post_outcome_case(
    *,
    case_id: str,
    outcome_manifest_id: str,
    boundary: datetime | None = None,
) -> LeakageAuditResult:
    """Run the existing leakage audit for one Stage 2 case with outcomes."""
    return audit_outcome_leakage(
        build_post_outcome_audit_request(
            case_id=case_id,
            outcome_manifest_id=outcome_manifest_id,
            boundary=boundary or FROZEN_BOUNDARY,
        )
    )


def audit_post_outcome_case_violation(
    *,
    case_id: str,
    outcome_manifest_id: str,
) -> LeakageAuditResult:
    """Return a failed audit when outcome capture precedes the result freeze."""
    request = build_post_outcome_audit_request(
        case_id=case_id,
        outcome_manifest_id=outcome_manifest_id,
    )
    violated = request.model_copy(
        update={"outcome_captured_at": request.evaluation_request_frozen_at}
    )
    return audit_outcome_leakage(violated)


def serialize_audit_summary(audits: tuple[LeakageAuditResult, ...]) -> bytes:
    payload = {
        "schema_version": "1.0.0",
        "stage": "phase-3e-stage2-post-outcome",
        "audits": [
            {
                "case_attempt_id": item.case_attempt_id,
                "passed": item.passed,
                "publication_blocked": item.publication_blocked,
                "diagnostic_codes": list(item.diagnostic_codes),
            }
            for item in audits
        ],
        "passed_count": sum(1 for item in audits if item.passed),
        "failed_count": sum(1 for item in audits if not item.passed),
    }
    return canonical_json_bytes(payload)


__all__ = [
    "OUTCOME_CAPTURED_OFFSET_SECONDS",
    "audit_post_outcome_case",
    "audit_post_outcome_case_violation",
    "build_post_outcome_audit_request",
    "serialize_audit_summary",
]
