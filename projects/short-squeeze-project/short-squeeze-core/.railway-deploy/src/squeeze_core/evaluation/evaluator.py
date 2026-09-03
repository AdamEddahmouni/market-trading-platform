from .candidate import build_candidate_evaluation
from .diagnostics import EvaluationDiagnosticCode
from .models import CandidateEvaluationPolicy, RuleCategory, RuleEvaluationRequest, RuleOutcome
from .policies import UnknownPolicyError, validate_enabled_rules
from .rules import (
    evaluate_catalyst_rule, evaluate_evidence_validity_rule, evaluate_momentum_rule,
    evaluate_short_pressure_rule,
)
from .rules.common import result


_EVALUATORS = {
    RuleCategory.MOMENTUM_DISCOVERY: evaluate_momentum_rule,
    RuleCategory.SHORT_PRESSURE_CONFIRMATION: evaluate_short_pressure_rule,
    RuleCategory.CATALYST_EVIDENCE: evaluate_catalyst_rule,
    RuleCategory.EVIDENCE_VALIDITY: evaluate_evidence_validity_rule,
}


def evaluate_candidate(request: RuleEvaluationRequest, policy: CandidateEvaluationPolicy):
    if request.policy_version != policy.policy_version:
        raise UnknownPolicyError(request.policy_version)
    definitions = validate_enabled_rules(policy, request.enabled_rule_ids)
    results = tuple(
        result(
            request, item, RuleOutcome.NOT_APPLICABLE,
            diagnostic_code=EvaluationDiagnosticCode.EVALUATION_NOT_APPLICABLE,
        )
        if request.asset_class not in item.applicable_asset_classes
        else _EVALUATORS[item.category](request, item)
        for item in definitions
    )
    return build_candidate_evaluation(request, policy, results)


__all__ = ["evaluate_candidate"]
