from decimal import Decimal

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import Quality, QualityState

from ..diagnostics import EvaluationDiagnostic, EvaluationDiagnosticCode
from ..models import (
    RuleDefinition, RuleEvaluationRequest, RuleEvaluationResult, RuleOutcome,
    ThresholdOperator,
)


_QUALITY_BY_OUTCOME = {
    RuleOutcome.PASS: QualityState.KNOWN_VALUE,
    RuleOutcome.FAIL: QualityState.KNOWN_VALUE,
    RuleOutcome.UNKNOWN: QualityState.UNAVAILABLE,
    RuleOutcome.CONFLICTED: QualityState.CONFLICTED,
    RuleOutcome.INSUFFICIENT_DATA: QualityState.MISSING,
    RuleOutcome.NOT_APPLICABLE: QualityState.NOT_APPLICABLE,
}


def result(
    request: RuleEvaluationRequest,
    definition: RuleDefinition,
    outcome: RuleOutcome,
    *,
    observed_value: Decimal | int | None = None,
    observed_unit: str | None = None,
    operator: ThresholdOperator | None = None,
    threshold_values: tuple[Decimal, ...] | None = None,
    threshold_unit: str | None = None,
    observation_ids: tuple[str, ...] = (),
    metric_ids: tuple[str, ...] = (),
    readiness_ids: tuple[str, ...] = (),
    diagnostic_code: EvaluationDiagnosticCode | None = None,
    explanation_code: str | None = None,
) -> RuleEvaluationResult:
    if definition.thresholds and threshold_values is None:
        threshold_values = tuple(item.value for item in definition.thresholds)
    if definition.thresholds and operator is None:
        operator = definition.thresholds[0].operator
    if definition.thresholds and threshold_unit is None:
        threshold_unit = definition.thresholds[0].unit
    diagnostics = ()
    if diagnostic_code is not None:
        diagnostics = (EvaluationDiagnostic(
            code=diagnostic_code,
            severity=(DiagnosticSeverity.INFO if outcome in {RuleOutcome.PASS, RuleOutcome.FAIL}
                      else DiagnosticSeverity.WARNING),
            rule_id=definition.rule_id,
            input_ids=tuple(sorted(set(observation_ids + metric_ids + readiness_ids))),
        ),)
    state = _QUALITY_BY_OUTCOME[outcome]
    quality = Quality(
        state=state,
        reasons=() if state is QualityState.KNOWN_VALUE else ((explanation_code or diagnostic_code.value),),
        evaluated_at=request.as_of,
    )
    return RuleEvaluationResult(
        rule_id=definition.rule_id, rule_version=definition.rule_version,
        category=definition.category, policy_version=request.policy_version,
        symbol=request.symbol, asset_class=request.asset_class, as_of=request.as_of,
        outcome=outcome,
        observed_value=None if observed_value is None else Decimal(observed_value),
        observed_unit=observed_unit, operator=operator,
        threshold_values=threshold_values or (), threshold_unit=threshold_unit,
        provider_scope=request.provider_scope, input_observation_ids=observation_ids,
        input_metric_ids=metric_ids, readiness_snapshot_ids=readiness_ids,
        quality=quality, diagnostics=diagnostics,
        explanation_code=explanation_code or (
            "EVALUATION_CONDITION_SATISFIED" if outcome is RuleOutcome.PASS
            else "EVALUATION_CONDITION_NOT_SATISFIED" if outcome is RuleOutcome.FAIL
            else diagnostic_code.value if diagnostic_code is not None
            else f"EVALUATION_{outcome.value}"
        ),
    )


def compare(value: Decimal, operator: ThresholdOperator, thresholds: tuple[Decimal, ...]) -> bool:
    if operator is ThresholdOperator.GREATER_THAN_OR_EQUAL:
        return value >= thresholds[0]
    if operator is ThresholdOperator.LESS_THAN_OR_EQUAL:
        return value <= thresholds[0]
    if operator is ThresholdOperator.BETWEEN_INCLUSIVE:
        return thresholds[0] <= value <= thresholds[1]
    if operator is ThresholdOperator.EQUAL:
        return value == thresholds[0]
    raise ValueError(f"operator {operator.value} is not numeric")


__all__ = ["compare", "result"]

