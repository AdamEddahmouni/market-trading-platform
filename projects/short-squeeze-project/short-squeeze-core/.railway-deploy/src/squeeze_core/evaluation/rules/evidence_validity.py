from squeeze_core.readiness import (
    DomainCoverageSnapshot, EvidenceConflictSummary, InputSufficiencyResult,
)

from ..diagnostics import EvaluationDiagnosticCode
from ..models import RuleDefinition, RuleEvaluationRequest, RuleOutcome
from .common import result


def _readiness(request: RuleEvaluationRequest, model):
    return next((item for item in request.input_readiness_results if isinstance(item, model)), None)


def evaluate_evidence_validity_rule(
    request: RuleEvaluationRequest, definition: RuleDefinition
):
    rule_id = definition.rule_id
    if rule_id == "NO_DEFAULT_SUBSTITUTION":
        if request.default_substitution_fields:
            return result(request, definition, RuleOutcome.FAIL, observed_value=0,
                          observed_unit="BOOLEAN",
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_DEFAULT_SUBSTITUTION_FORBIDDEN)
        return result(request, definition, RuleOutcome.PASS, observed_value=1,
                      observed_unit="BOOLEAN")
    if rule_id == "PROVIDER_SCOPE_EXPLICIT":
        if not request.provider_scope:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PROVIDER_SCOPE_REQUIRED)
        return result(request, definition, RuleOutcome.PASS,
                      observed_value=len(request.provider_scope), observed_unit="PROVIDERS")

    if rule_id == "REQUIRED_DOMAINS_PRESENT":
        snapshot = _readiness(request, DomainCoverageSnapshot)
        if snapshot is None:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_UNAVAILABLE)
        ids = (str(snapshot.deterministic_id),)
        if snapshot.conflicted_domains:
            return result(request, definition, RuleOutcome.CONFLICTED, readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_DOMAIN_CONFLICTED)
        if snapshot.unknown_domains or snapshot.unavailable_domains:
            return result(request, definition, RuleOutcome.UNKNOWN, readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_DOMAIN_UNKNOWN)
        if snapshot.missing_domains:
            return result(request, definition, RuleOutcome.FAIL, observed_value=0,
                          observed_unit="DOMAINS", readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_DOMAIN_MISSING)
        if not snapshot.requested_domains:
            return result(request, definition, RuleOutcome.UNKNOWN, readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_UNAVAILABLE)
        return result(request, definition, RuleOutcome.PASS,
                      observed_value=len(snapshot.present_domains), observed_unit="DOMAINS",
                      readiness_ids=ids)

    if rule_id == "NO_MATERIAL_CONFLICTS":
        summary = _readiness(request, EvidenceConflictSummary)
        if summary is None:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_UNAVAILABLE)
        ids = (str(summary.deterministic_id),)
        if summary.conflict_count:
            return result(request, definition, RuleOutcome.CONFLICTED,
                          observed_value=summary.conflict_count, observed_unit="CONFLICTS",
                          readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_CONFLICTED)
        return result(request, definition, RuleOutcome.PASS, observed_value=0,
                      observed_unit="CONFLICTS", readiness_ids=ids)

    sufficiency = _readiness(request, InputSufficiencyResult)
    if sufficiency is None:
        return result(request, definition, RuleOutcome.UNKNOWN,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_UNAVAILABLE)
    ids = (str(sufficiency.deterministic_id),)
    if rule_id == "POINT_IN_TIME_ELIGIBLE":
        if sufficiency.point_in_time_failures:
            return result(request, definition, RuleOutcome.FAIL, observed_value=0,
                          observed_unit="BOOLEAN", readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_UNAVAILABLE)
        return result(request, definition, RuleOutcome.PASS, observed_value=1,
                      observed_unit="BOOLEAN", readiness_ids=ids)
    if rule_id == "REQUIRED_UNITS_COMPATIBLE":
        if sufficiency.incompatible_inputs:
            return result(request, definition, RuleOutcome.INSUFFICIENT_DATA,
                          observed_value=len(sufficiency.incompatible_inputs),
                          observed_unit="INCOMPATIBLE_INPUTS", readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_UNIT_INCOMPATIBLE)
        return result(request, definition, RuleOutcome.PASS, observed_value=0,
                      observed_unit="INCOMPATIBLE_INPUTS", readiness_ids=ids)
    if rule_id == "REQUIRED_HISTORY_SUFFICIENT":
        if sufficiency.insufficient_history_inputs:
            return result(request, definition, RuleOutcome.INSUFFICIENT_DATA,
                          observed_value=len(sufficiency.insufficient_history_inputs),
                          observed_unit="INSUFFICIENT_INPUTS", readiness_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_HISTORY_INSUFFICIENT)
        return result(request, definition, RuleOutcome.PASS, observed_value=0,
                      observed_unit="INSUFFICIENT_INPUTS", readiness_ids=ids)
    raise ValueError(f"unsupported evidence-validity rule: {rule_id}")


__all__ = ["evaluate_evidence_validity_rule"]
