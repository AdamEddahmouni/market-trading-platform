"""Execute the *existing* Phase 3A evaluator and record what it returned.

This module contains no rule logic and no outcome vocabulary of its own. It calls
``squeeze_core.evaluation.evaluate_candidate`` and copies each ``RuleEvaluationResult``'s
outcome verbatim into a ``RuleOutcomeRecord``. A committed test asserts that no
``RuleOutcome`` member is ever named or constructed in this package.
"""

from __future__ import annotations

from squeeze_core.evaluation import evaluate_candidate
from squeeze_core.evaluation.models import (
    CandidateEvaluationPolicy,
    CandidateEvaluationResult,
    RuleEvaluationRequest,
)

from ..operation_readiness.models import Phase3ARuleDependencyRecord
from .models import BlockingReasonCode, RuleOutcomeRecord

#: Batch 07 admissibility status -> why the rule received no substantive evidence.
_BLOCKING_BY_STATUS = {
    "BLOCKED_MISSING_SEMANTICS": None,  # refined per-rule below
    "BLOCKED_MISSING_EVIDENCE": BlockingReasonCode.REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE,
    "BLOCKED_ALIGNMENT": BlockingReasonCode.REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE,
    "BLOCKED_CONFLICT": BlockingReasonCode.REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE,
    "NOT_APPLICABLE": BlockingReasonCode.EVIDENCE_META_RULE_NOT_BAR_DEPENDENT,
}

#: Batch 07 reason code -> the specific blocked-evidence class it implies.
_SEMANTIC_BLOCKERS = (
    (
        "PRICE_ABSOLUTE_LEVEL_CORPORATE_ACTION_UNCONFIRMED",
        BlockingReasonCode.ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07,
    ),
    ("VOLUME_UNIT_UNRESOLVED", BlockingReasonCode.VOLUME_SEMANTICS_BLOCKED_BY_BATCH07),
    (
        "VOLUME_CORPORATE_ACTION_UNKNOWN",
        BlockingReasonCode.VOLUME_SEMANTICS_BLOCKED_BY_BATCH07,
    ),
    (
        "VOLUME_FILTER_STATIONARITY_UNPROVEN",
        BlockingReasonCode.VOLUME_SEMANTICS_BLOCKED_BY_BATCH07,
    ),
)


def blocking_reasons(record: Phase3ARuleDependencyRecord) -> tuple[BlockingReasonCode, ...]:
    """Translate a Batch 07 readiness record into Batch 08 blocking reason codes."""
    reasons: set[BlockingReasonCode] = set()
    observed = {code.value for code in record.reason_codes}
    for reason_value, code in _SEMANTIC_BLOCKERS:
        if reason_value in observed:
            reasons.add(code)
    mapped = _BLOCKING_BY_STATUS.get(record.admissibility_status.value)
    if mapped is not None:
        reasons.add(mapped)
    if (
        record.admissibility_status.value == "BLOCKED_MISSING_EVIDENCE"
        and not record.touches_detection_context_bars
    ):
        reasons.add(BlockingReasonCode.NO_DETECTION_TIME_EVIDENCE_EXISTS)
    return tuple(sorted(reasons, key=lambda item: item.value))


def run_evaluation(
    request: RuleEvaluationRequest, policy: CandidateEvaluationPolicy
) -> CandidateEvaluationResult:
    """Run the existing Phase 3A evaluator. No second evaluator exists."""
    return evaluate_candidate(request, policy)


def rule_outcome_records(
    evaluation: CandidateEvaluationResult,
    readiness_by_rule: dict[str, Phase3ARuleDependencyRecord],
) -> tuple[RuleOutcomeRecord, ...]:
    """Copy the evaluator's outcomes verbatim, annotated with Batch 07 readiness."""
    records = []
    for item in evaluation.rule_results:
        readiness = readiness_by_rule[item.rule_id]
        records.append(
            RuleOutcomeRecord(
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                category=item.category.value,
                outcome=item.outcome.value,
                explanation_code=item.explanation_code,
                rule_result_id=str(item.deterministic_id),
                supporting_observation_ids=item.input_observation_ids,
                supporting_metric_ids=item.input_metric_ids,
                supporting_readiness_ids=item.readiness_snapshot_ids,
                batch07_admissibility_status=readiness.admissibility_status.value,
                blocking_reason_codes=blocking_reasons(readiness),
            )
        )
    return tuple(records)


__all__ = ["blocking_reasons", "rule_outcome_records", "run_evaluation"]
