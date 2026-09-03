"""Per-case leakage audit, delegated to the existing Phase 3D audit engine.

No second audit engine is written: this module only assembles a
``LeakageAuditRequest`` describing the Batch 08 freeze ordering and calls
``acquisition.leakage_guards.audit_outcome_leakage``.

The freeze stage times are *logical ordinals*, not wall clock: they are derived from a
fixed offset sequence anchored on the frozen boundary, so a re-run produces byte-identical
audit inputs. ``outcome_captured_at`` is a sentinel strictly after every freeze stage
because no outcome was captured at all — which is exactly what the audit must prove.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..leakage_guards import audit_outcome_leakage
from ..models import LeakageAuditRequest, LeakageAuditResult

#: Logical freeze ordinals, in seconds after the frozen boundary. Order is what the audit
#: checks; the values are deterministic and carry no wall-clock information.
PLAN_OFFSET_SECONDS = 0
BOUNDARY_OFFSET_SECONDS = 1
EVIDENCE_ASSOCIATION_OFFSET_SECONDS = 2
REQUEST_OFFSET_SECONDS = 3
RESULT_OFFSET_SECONDS = 4
#: No outcome exists. The sentinel sits strictly after every freeze stage so the audit's
#: "outcome captured before stage X" checks all pass.
NO_OUTCOME_SENTINEL_OFFSET_SECONDS = 5

#: Field names actually present in each Batch 08 layer, for the audit's token scan.
DISCOVERY_INPUT_FIELDS = ("case_id", "symbol", "discovery_source_class", "boundary_rule")
ELIGIBILITY_INPUT_FIELDS = ("case_id", "symbol", "eligibility_state")
BOUNDARY_INPUT_FIELDS = ("boundary_id", "boundary_time", "boundary_rule")
EVALUATION_INPUT_FIELDS = (
    "detection_context_artifact_sha256",
    "detection_context_artifact_byte_length",
    "definitely_completed_bar_close",
    "percentage_return_metric_id",
    "domain_coverage_snapshot_id",
    "evidence_conflict_summary_id",
    "input_sufficiency_result_id",
    "phase3a_policy_version",
    "enabled_rule_ids",
)


def _at(boundary: datetime, offset: int) -> datetime:
    return boundary + timedelta(seconds=offset)


def build_audit_request(
    *,
    case_id: str,
    boundary: datetime,
    discovery_manifest_id: str,
) -> LeakageAuditRequest:
    """Assemble the audit input describing this case's freeze ordering."""
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
        outcome_captured_at=_at(boundary, NO_OUTCOME_SENTINEL_OFFSET_SECONDS),
        discovery_manifest_id=discovery_manifest_id,
        # A separate manifest id is required by the audit; no outcome manifest exists, so
        # a distinct explicit sentinel is used rather than reusing the discovery id.
        outcome_manifest_id=f"{case_id}::NO_OUTCOME_MANIFEST",
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )


def audit_case(
    *, case_id: str, boundary: datetime, discovery_manifest_id: str
) -> LeakageAuditResult:
    """Run the existing Phase 3D leakage audit for one frozen case."""
    return audit_outcome_leakage(
        build_audit_request(
            case_id=case_id,
            boundary=boundary,
            discovery_manifest_id=discovery_manifest_id,
        )
    )


def ordering_holds(request: LeakageAuditRequest) -> bool:
    """Explicit assertion of the required freeze ordering, independent of the audit.

    ``LeakageAuditRequest`` has no evidence-association field, so that stage is checked
    here against its own logical ordinal, which sits between boundary and request.
    """
    evidence_association_at = _at(
        request.boundary_frozen_at - timedelta(seconds=BOUNDARY_OFFSET_SECONDS),
        EVIDENCE_ASSOCIATION_OFFSET_SECONDS,
    )
    return (
        request.plan_frozen_at
        <= request.boundary_frozen_at
        < evidence_association_at
        < request.evaluation_request_frozen_at
        < request.evaluation_result_frozen_at
        < request.outcome_captured_at
    )


__all__ = [
    "BOUNDARY_INPUT_FIELDS",
    "DISCOVERY_INPUT_FIELDS",
    "ELIGIBILITY_INPUT_FIELDS",
    "EVALUATION_INPUT_FIELDS",
    "audit_case",
    "build_audit_request",
    "ordering_holds",
]
