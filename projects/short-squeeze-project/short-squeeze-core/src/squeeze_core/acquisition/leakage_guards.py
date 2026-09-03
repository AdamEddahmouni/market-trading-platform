from .models import LeakageAuditRequest, LeakageAuditResult


_OUTCOME_TOKENS = ("outcome", "later_return", "maximum_observed_move", "maximum_return")
# Every stage that must be frozen and hashed before any outcome artifact is read.
# The request and result share one code because both are the Phase 3A evaluation freeze.
_FREEZE_STAGES = (
    ("plan_frozen_at", "OUTCOME_ARTIFACT_CAPTURED_BEFORE_PLAN_FREEZE"),
    ("boundary_frozen_at", "OUTCOME_ARTIFACT_CAPTURED_BEFORE_BOUNDARY_FREEZE"),
    ("evaluation_request_frozen_at", "OUTCOME_ARTIFACT_CAPTURED_BEFORE_EVALUATION_FREEZE"),
    ("evaluation_result_frozen_at", "OUTCOME_ARTIFACT_CAPTURED_BEFORE_EVALUATION_FREEZE"),
)


def _contains_outcome(fields: tuple[str, ...]) -> bool:
    return any(any(token in field.lower() for token in _OUTCOME_TOKENS) for field in fields)


def audit_outcome_leakage(request: LeakageAuditRequest) -> LeakageAuditResult:
    diagnostics: list[str] = []
    layers = (
        (request.discovery_input_fields, "OUTCOME_DATA_PRESENT_IN_DISCOVERY_INPUT"),
        (request.eligibility_input_fields, "OUTCOME_DATA_PRESENT_IN_ELIGIBILITY_INPUT"),
        (request.boundary_input_fields, "OUTCOME_DATA_PRESENT_IN_BOUNDARY_INPUT"),
        (request.evaluation_input_fields, "OUTCOME_DATA_PRESENT_IN_EVALUATION_INPUT"),
    )
    diagnostics.extend(code for fields, code in layers if _contains_outcome(fields))
    diagnostics.extend(
        code for field, code in _FREEZE_STAGES
        if request.outcome_captured_at < getattr(request, field)
    )
    if request.discovery_manifest_id == request.outcome_manifest_id:
        diagnostics.append("OUTCOME_MANIFEST_NOT_SEPARATE")
    flags = (
        (request.plan_changed_after_outcome_access, "ACQUISITION_PLAN_CHANGED_AFTER_OUTCOME_ACCESS"),
        (request.outcome_aware_selection_indicator, "OUTCOME_AWARE_SELECTION_INDICATOR"),
        (request.maximum_return_selection_indicator, "MAXIMUM_RETURN_SELECTION_INDICATOR"),
        (request.post_event_article_used_as_discovery_source, "POST_EVENT_ARTICLE_USED_AS_DISCOVERY_SOURCE"),
    )
    diagnostics.extend(code for enabled, code in flags if enabled)
    if diagnostics:
        diagnostics.append("LEAKAGE_AUDIT_FAILED")
    else:
        diagnostics.append("LEAKAGE_AUDIT_PASSED")
    passed = diagnostics == ["LEAKAGE_AUDIT_PASSED"]
    return LeakageAuditResult(
        case_attempt_id=request.case_attempt_id, passed=passed,
        publication_blocked=not passed, diagnostic_codes=tuple(diagnostics),
    )


__all__ = ["audit_outcome_leakage"]
