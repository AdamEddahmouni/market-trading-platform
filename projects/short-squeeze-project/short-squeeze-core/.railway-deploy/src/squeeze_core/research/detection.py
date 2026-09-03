from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.evaluation import CandidateEvaluationResult, RuleOutcome

from .diagnostics import ResearchDiagnostic, ResearchDiagnosticCode
from .models import DetectionPredicatePolicy, DetectionStatus, ResearchDetectionResult


def evaluate_research_detection(
    evaluation: CandidateEvaluationResult,
    policy: DetectionPredicatePolicy,
) -> ResearchDetectionResult:
    by_rule = {item.rule_id: item for item in evaluation.rule_results}
    missing = tuple(rule_id for rule_id in policy.required_rule_ids if rule_id not in by_rule)
    if missing:
        raise ValueError("RESEARCH_DETECTION_REQUIRED_RULE_UNKNOWN", missing)

    required = tuple(by_rule[rule_id] for rule_id in policy.required_rule_ids)
    outcomes = tuple(item.outcome for item in required)
    diagnostics: list[ResearchDiagnostic] = []
    if any(item is RuleOutcome.FAIL for item in outcomes):
        status = DetectionStatus.NOT_DETECTED
        diagnostics.extend(
            ResearchDiagnostic(
                code=ResearchDiagnosticCode.RESEARCH_DETECTION_REQUIRED_RULE_FAILED,
                severity=DiagnosticSeverity.INFO,
                rule_id=item.rule_id,
                input_ids=(str(item.deterministic_id),),
            )
            for item in required if item.outcome is RuleOutcome.FAIL
        )
    elif all(item is RuleOutcome.PASS for item in outcomes):
        status = DetectionStatus.DETECTED
    else:
        status = DetectionStatus.UNEVALUABLE
        code_by_outcome = {
            RuleOutcome.UNKNOWN: ResearchDiagnosticCode.RESEARCH_DETECTION_REQUIRED_RULE_UNKNOWN,
            RuleOutcome.CONFLICTED: ResearchDiagnosticCode.RESEARCH_DETECTION_REQUIRED_RULE_CONFLICTED,
            RuleOutcome.INSUFFICIENT_DATA: ResearchDiagnosticCode.RESEARCH_DETECTION_REQUIRED_RULE_INSUFFICIENT,
            RuleOutcome.NOT_APPLICABLE: ResearchDiagnosticCode.RESEARCH_DETECTION_UNEVALUABLE,
        }
        diagnostics.extend(
            ResearchDiagnostic(
                code=code_by_outcome[item.outcome],
                severity=DiagnosticSeverity.WARNING,
                rule_id=item.rule_id,
                input_ids=(str(item.deterministic_id),),
            )
            for item in required if item.outcome is not RuleOutcome.PASS
        )
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_DETECTION_UNEVALUABLE,
            severity=DiagnosticSeverity.WARNING,
        ))

    return ResearchDetectionResult(
        evaluation_id=str(evaluation.deterministic_id),
        policy_version=policy.policy_version,
        status=status,
        required_rule_ids=policy.required_rule_ids,
        supporting_rule_result_ids=tuple(str(item.deterministic_id) for item in required),
        diagnostics=tuple(diagnostics),
    )


__all__ = ["evaluate_research_detection"]
