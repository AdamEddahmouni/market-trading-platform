"""Counterfactual detection policy evaluation from stored rule outcomes."""

from __future__ import annotations

from squeeze_core.contracts import Quality, QualityState
from squeeze_core.evaluation import (
    CandidateEvaluationResult,
    RuleCategory,
    RuleEvaluationResult,
    RuleOutcome,
)
from squeeze_core.evaluation.candidate import summarize_results
from squeeze_core.research.classification import classify_research_case
from squeeze_core.research.detection import evaluate_research_detection
from squeeze_core.research.models import DetectionPredicatePolicy, ResearchDatasetRow


def detection_policy_from_spec(spec) -> DetectionPredicatePolicy:
    return DetectionPredicatePolicy(
        policy_version=spec.policy_version,
        required_rule_ids=spec.required_rule_ids,
        provisional=spec.provisional,
        rationale_code=spec.rationale_code,
    )


def _quality_for_outcome(outcome: RuleOutcome) -> Quality:
    state = {
        RuleOutcome.PASS: QualityState.KNOWN_VALUE,
        RuleOutcome.FAIL: QualityState.KNOWN_VALUE,
        RuleOutcome.UNKNOWN: QualityState.UNAVAILABLE,
        RuleOutcome.CONFLICTED: QualityState.CONFLICTED,
        RuleOutcome.INSUFFICIENT_DATA: QualityState.MISSING,
        RuleOutcome.NOT_APPLICABLE: QualityState.NOT_APPLICABLE,
    }[outcome]
    return Quality(
        state=state,
        reasons=() if state is QualityState.KNOWN_VALUE else (outcome.value,),
    )


def _rule_results_from_row(row: ResearchDatasetRow) -> tuple[RuleEvaluationResult, ...]:
    results: list[RuleEvaluationResult] = []
    for rule_id, outcome_value in sorted(row.rule_outcomes.items()):
        outcome = RuleOutcome(outcome_value)
        results.append(
            RuleEvaluationResult(
                rule_id=rule_id,
                rule_version="calibration.v1",
                category=_category_for_rule(rule_id),
                policy_version=row.phase_3a_policy_version,
                symbol=row.symbol,
                asset_class=row.asset_class,
                as_of=row.evaluation_as_of,
                outcome=outcome,
                observed_value=row.rule_observed_values.get(rule_id),
                threshold_values=row.rule_threshold_values.get(rule_id, ()),
                quality=_quality_for_outcome(outcome),
                explanation_code="CALIBRATION_RULE_REPLAY",
            )
        )
    return tuple(results)


def _evaluation_from_row(row: ResearchDatasetRow) -> CandidateEvaluationResult:
    rule_results = _rule_results_from_row(row)
    return CandidateEvaluationResult(
        evaluation_version="candidate_evaluation.v1",
        policy_version=row.phase_3a_policy_version,
        symbol=row.symbol,
        asset_class=row.asset_class,
        as_of=row.evaluation_as_of,
        enabled_rule_ids=tuple(sorted(row.rule_outcomes)),
        rule_results=rule_results,
        results_by_category=summarize_results(rule_results),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
def _category_for_rule(rule_id: str) -> RuleCategory:
    if rule_id in {
        "PRICE_RANGE",
        "PERCENTAGE_CHANGE_MINIMUM",
        "RELATIVE_VOLUME_MINIMUM",
        "FLOAT_MAXIMUM",
        "MARKET_DATA_AVAILABLE",
        "COMPLETED_BAR_AVAILABLE",
    }:
        return RuleCategory.MOMENTUM_DISCOVERY
    if "BORROW" in rule_id or "SHORT_INTEREST" in rule_id or rule_id in {
        "DAYS_TO_COVER_MINIMUM",
        "PUBLISHED_SHORT_INTEREST_AVAILABLE",
    }:
        return RuleCategory.SHORT_PRESSURE_CONFIRMATION
    if rule_id.startswith("NEWS") or rule_id in {
        "SEC_FILING_AVAILABLE",
        "CORPORATE_ACTION_CONTEXT_AVAILABLE",
    }:
        return RuleCategory.CATALYST_EVIDENCE
    return RuleCategory.EVIDENCE_VALIDITY


def apply_detection_policy(
    row: ResearchDatasetRow,
    policy: DetectionPredicatePolicy,
) -> ResearchDatasetRow:
    evaluation = _evaluation_from_row(row)
    detection = evaluate_research_detection(evaluation, policy)
    classification = classify_research_case(
        row.case_id,
        detection.status,
        row.outcome_label,
        str(detection.deterministic_id),
        row.outcome_observation_id,
    )
    return row.model_copy(
        update={
            "research_detection_policy_version": policy.policy_version,
            "research_detection_status": detection.status,
            "research_classification": classification.classification,
        }
    )


__all__ = ["apply_detection_policy", "detection_policy_from_spec"]
