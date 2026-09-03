from squeeze_core.contracts import Quality, QualityState

from .models import (
    CandidateEvaluationPolicy, CandidateEvaluationResult, CategoryEvaluationSummary,
    RuleCategory, RuleEvaluationRequest, RuleEvaluationResult, RuleOutcome,
)


def summarize_results(
    results: tuple[RuleEvaluationResult, ...]
) -> tuple[CategoryEvaluationSummary, ...]:
    summaries = []
    for category in RuleCategory:
        selected = tuple(item for item in results if item.category is category)
        counts = {outcome: sum(item.outcome is outcome for item in selected) for outcome in RuleOutcome}
        summaries.append(CategoryEvaluationSummary(
            category=category,
            pass_count=counts[RuleOutcome.PASS],
            fail_count=counts[RuleOutcome.FAIL],
            unknown_count=counts[RuleOutcome.UNKNOWN],
            conflicted_count=counts[RuleOutcome.CONFLICTED],
            insufficient_data_count=counts[RuleOutcome.INSUFFICIENT_DATA],
            not_applicable_count=counts[RuleOutcome.NOT_APPLICABLE],
        ))
    return tuple(summaries)


def build_candidate_evaluation(
    request: RuleEvaluationRequest,
    policy: CandidateEvaluationPolicy,
    results: tuple[RuleEvaluationResult, ...],
) -> CandidateEvaluationResult:
    return CandidateEvaluationResult(
        evaluation_version=policy.evaluation_version,
        policy_version=policy.policy_version,
        symbol=request.symbol,
        asset_class=request.asset_class,
        as_of=request.as_of,
        enabled_rule_ids=request.enabled_rule_ids,
        rule_results=results,
        results_by_category=summarize_results(results),
        input_observation_ids=tuple(
            observation_id for item in results for observation_id in item.input_observation_ids
        ),
        input_metric_ids=tuple(metric_id for item in results for metric_id in item.input_metric_ids),
        readiness_snapshot_ids=tuple(
            readiness_id for item in results for readiness_id in item.readiness_snapshot_ids
        ),
        quality=Quality(state=QualityState.KNOWN_VALUE, evaluated_at=request.as_of),
        diagnostics=tuple(diagnostic for item in results for diagnostic in item.diagnostics),
    )


__all__ = ["build_candidate_evaluation", "summarize_results"]

