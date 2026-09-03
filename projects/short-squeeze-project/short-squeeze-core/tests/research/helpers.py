from datetime import datetime, timezone

from squeeze_core.evaluation import CandidateEvaluationResult, RuleEvaluationResult, RuleOutcome
from tests.evaluation.biya_helpers import EARLIEST, POLICY, request
from squeeze_core.evaluation import evaluate_candidate


AS_OF = datetime(2026, 7, 17, 14, 23, 58, tzinfo=timezone.utc)
BASE_EVALUATION = evaluate_candidate(request(EARLIEST), POLICY)
REQUIRED_RULES = ("PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE")


def evaluation_with_required_outcomes(outcomes: tuple[RuleOutcome, RuleOutcome, RuleOutcome]):
    replacements = dict(zip(REQUIRED_RULES, outcomes, strict=True))
    results = []
    for result in BASE_EVALUATION.rule_results:
        if result.rule_id not in replacements:
            results.append(result)
            continue
        values = result.model_dump(exclude={"deterministic_id"})
        values["outcome"] = replacements[result.rule_id]
        results.append(RuleEvaluationResult(**values))
    values = BASE_EVALUATION.model_dump(exclude={"deterministic_id", "rule_results"})
    return CandidateEvaluationResult(**values, rule_results=tuple(results))
