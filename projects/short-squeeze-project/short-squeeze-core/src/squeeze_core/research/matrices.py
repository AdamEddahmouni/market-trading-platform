from .models import BatchEvaluationResult, RuleOutcomeMatrix, RuleOutcomeMatrixRow


def build_rule_outcome_matrix(batch: BatchEvaluationResult) -> RuleOutcomeMatrix:
    rule_ids = (
        () if not batch.case_results
        else tuple(item.rule_id for item in batch.case_results[0].phase_3a_rule_results)
    )
    rows = tuple(RuleOutcomeMatrixRow(
        case_id=case.case_id,
        symbol=case.symbol,
        evaluation_as_of=case.evaluation_as_of,
        rule_outcomes={item.rule_id: item.outcome.value for item in case.phase_3a_rule_results},
        research_detection_status=case.research_detection_status,
        outcome_label=case.outcome_label,
        research_classification=case.research_classification,
    ) for case in batch.case_results)
    if any(tuple(row.rule_outcomes) != rule_ids for row in rows):
        raise ValueError("RESEARCH_CASE_IDENTITY_CONFLICT")
    return RuleOutcomeMatrix(rule_ids=rule_ids, rows=rows)


__all__ = ["build_rule_outcome_matrix"]
