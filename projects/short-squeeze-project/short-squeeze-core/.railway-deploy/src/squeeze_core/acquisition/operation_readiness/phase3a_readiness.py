"""Phase 3A rule dependency-readiness and per-case request-readiness.

This is dependency analysis, NOT rule evaluation: it emits admissibility statuses only,
never PASS/FAIL, never a RuleEvaluationResult, and never executes an evaluation. It does
not import the evaluation runtime. Request-readiness answers only whether a syntactically
and semantically valid request could be constructed from frozen identity without
fabrication -- it never instantiates or runs one.
"""

from __future__ import annotations

from .admissibility import AdmissibilityContext, assess_operation
from .dependencies import PHASE3A_RULE_DEPENDENCIES
from .models import (
    AdmissibilityStatus,
    OperationDependency,
    OperationKind,
    Phase3ARequestReadiness,
    Phase3ARuleDependencyRecord,
    ReasonCode,
    SemanticDependency,
)

_SEMANTIC_FIELDS = (
    "price_adjustment_absolute",
    "price_adjustment_ratio",
    "dividend_adjustment",
    "volume_unit",
    "volume_corporate_action",
    "volume_filter_stationarity",
    "timestamp_boundary",
    "session_completeness",
)


def required_semantic_fields(sem: SemanticDependency) -> tuple[str, ...]:
    return tuple(field for field in _SEMANTIC_FIELDS if getattr(sem, field))


def build_rule_record(
    dep: OperationDependency, category: str, ctx: AdmissibilityContext
) -> Phase3ARuleDependencyRecord:
    sem_fields = required_semantic_fields(dep.semantic_dependency)

    if dep.kind is OperationKind.EVIDENCE_META:
        # Meta-rules validate the whole assembled request, not the bars in isolation.
        status = AdmissibilityStatus.NOT_APPLICABLE
        reasons: tuple[ReasonCode, ...] = (ReasonCode.OPERATION_INDEPENDENT_OF_THIS_EVIDENCE,)
    elif not dep.touches_detection_context_bars:
        # A rule whose required domain is not in this evidence set is blocked for lack
        # of its evidence; the detection-context bars are not its evidence.
        status = AdmissibilityStatus.BLOCKED_MISSING_EVIDENCE
        reasons = (ReasonCode.REQUIRED_DOMAIN_ABSENT,)
    else:
        admissibility = assess_operation(dep, ctx)
        status = admissibility.status
        reasons = admissibility.reason_codes

    return Phase3ARuleDependencyRecord(
        rule_id=dep.operation,
        category=category,
        required_domains=dep.required_domains,
        required_metric_names=dep.required_metric_names,
        required_semantic_fields=sem_fields,
        touches_detection_context_bars=dep.touches_detection_context_bars,
        admissibility_status=status,
        reason_codes=reasons,
    )


def build_all_rule_records(
    ctx: AdmissibilityContext,
) -> tuple[Phase3ARuleDependencyRecord, ...]:
    return tuple(
        build_rule_record(dep, category, ctx)
        for dep, category in PHASE3A_RULE_DEPENDENCIES
    )


def assess_request_readiness(
    *,
    has_frozen_symbol: bool,
    has_frozen_boundary_as_of: bool,
    has_policy_version: bool,
    has_enabled_rule_ids: bool,
) -> Phase3ARequestReadiness:
    """Readiness of *constructing* a Phase 3A request -- never of running one.

    The Phase 3A contract (``RuleEvaluationRequest``) defaults all evidence-input tuples
    to empty and ``RuleOutcome`` includes ``INSUFFICIENT_DATA``/``UNKNOWN``. A request
    built from frozen identity alone (symbol, as_of = frozen boundary, policy_version,
    enabled rule ids) is therefore valid without fabricating any evidence field. Missing
    evidence legitimately drives dependent rules to INSUFFICIENT_DATA/UNKNOWN. This
    function checks only that the frozen identity needed for a non-fabricated skeleton is
    present; it does not construct or evaluate the request.
    """
    if (
        has_frozen_symbol
        and has_frozen_boundary_as_of
        and has_policy_version
        and has_enabled_rule_ids
    ):
        return Phase3ARequestReadiness.PHASE3A_REQUEST_READY
    return Phase3ARequestReadiness.PHASE3A_REQUEST_BLOCKED


__all__ = [
    "required_semantic_fields",
    "build_rule_record",
    "build_all_rule_records",
    "assess_request_readiness",
]
