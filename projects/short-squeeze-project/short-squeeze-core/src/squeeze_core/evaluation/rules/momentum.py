from decimal import Decimal

from squeeze_core.contracts import EventType, MarketSnapshotPayload, QualityState
from squeeze_core.metrics import MetricName, MetricUnit

from ..diagnostics import EvaluationDiagnosticCode
from ..models import RuleDefinition, RuleEvaluationRequest, RuleOutcome, ThresholdOperator
from ..selectors import is_insufficient_metric, observations_for_event, select_metric
from .common import compare, result


def _provider_required(request: RuleEvaluationRequest, definition: RuleDefinition):
    if definition.provider_scope_required and not request.provider_scope:
        return result(request, definition, RuleOutcome.UNKNOWN,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PROVIDER_SCOPE_REQUIRED)
    return None


def _metric_rule(
    request: RuleEvaluationRequest, definition: RuleDefinition,
    metric_name: MetricName, expected_unit: MetricUnit, unavailable_code: EvaluationDiagnosticCode,
):
    metric = select_metric(request, metric_name)
    if metric is None:
        return result(request, definition, RuleOutcome.UNKNOWN, diagnostic_code=unavailable_code)
    metric_ids = (str(metric.deterministic_id),)
    if metric.quality.state is QualityState.CONFLICTED:
        return result(request, definition, RuleOutcome.CONFLICTED, metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_CONFLICTED)
    if is_insufficient_metric(metric):
        return result(request, definition, RuleOutcome.INSUFFICIENT_DATA, metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_HISTORY_INSUFFICIENT)
    if metric.value is None:
        return result(request, definition, RuleOutcome.UNKNOWN, metric_ids=metric_ids,
                      diagnostic_code=unavailable_code)
    if metric.unit is not expected_unit:
        return result(request, definition, RuleOutcome.INSUFFICIENT_DATA,
                      observed_value=metric.value, observed_unit=metric.unit.value,
                      metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_UNIT_INCOMPATIBLE)
    threshold = definition.thresholds[0]
    outcome = RuleOutcome.PASS if compare(metric.value, threshold.operator, (threshold.value,)) else RuleOutcome.FAIL
    return result(request, definition, outcome, observed_value=metric.value,
                  observed_unit=metric.unit.value, metric_ids=metric_ids)


def evaluate_momentum_rule(
    request: RuleEvaluationRequest, definition: RuleDefinition
):
    applicable = _provider_required(request, definition)
    if applicable is not None:
        return applicable

    if definition.rule_id in {"PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE"}:
        bars = observations_for_event(request, EventType.BAR)
        observation_ids = tuple(str(item.observation_id) for item in bars)
        if definition.rule_id == "MARKET_DATA_AVAILABLE":
            return result(request, definition, RuleOutcome.PASS if bars else RuleOutcome.UNKNOWN,
                          observed_value=len(bars) if bars else None,
                          observed_unit="OBSERVATIONS" if bars else None,
                          observation_ids=observation_ids,
                          diagnostic_code=None if bars else EvaluationDiagnosticCode.EVALUATION_PRICE_UNAVAILABLE)
        completed = tuple(item for item in bars
                          if str(item.provenance.provider_metadata.get("status")) == "COMPLETED")
        if definition.rule_id == "COMPLETED_BAR_AVAILABLE":
            if completed:
                return result(request, definition, RuleOutcome.PASS, observed_value=len(completed),
                              observed_unit="OBSERVATIONS", observation_ids=tuple(str(item.observation_id) for item in completed))
            if bars:
                return result(request, definition, RuleOutcome.FAIL, observed_value=0,
                              observed_unit="OBSERVATIONS", observation_ids=observation_ids,
                              diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PARTIAL_BAR)
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PRICE_UNAVAILABLE)
        if not completed:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          observation_ids=observation_ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PRICE_UNAVAILABLE)
        selected = completed[-1]
        value = selected.payload.close
        minimum = next(item.value for item in definition.thresholds
                       if item.operator is ThresholdOperator.GREATER_THAN_OR_EQUAL)
        maximum = next(item.value for item in definition.thresholds
                       if item.operator is ThresholdOperator.LESS_THAN_OR_EQUAL)
        thresholds = (minimum, maximum)
        outcome = RuleOutcome.PASS if compare(value, ThresholdOperator.BETWEEN_INCLUSIVE, thresholds) else RuleOutcome.FAIL
        return result(request, definition, outcome, observed_value=value, observed_unit="PRICE",
                      operator=ThresholdOperator.BETWEEN_INCLUSIVE,
                      threshold_values=thresholds,
                      observation_ids=(str(selected.observation_id),))

    if definition.rule_id == "PERCENTAGE_CHANGE_MINIMUM":
        return _metric_rule(request, definition, MetricName.PERCENTAGE_RETURN, MetricUnit.PERCENT,
                            EvaluationDiagnosticCode.EVALUATION_RETURN_UNAVAILABLE)
    if definition.rule_id == "RELATIVE_VOLUME_MINIMUM":
        return _metric_rule(request, definition, MetricName.RELATIVE_VOLUME, MetricUnit.RATIO,
                            EvaluationDiagnosticCode.EVALUATION_RELATIVE_VOLUME_UNAVAILABLE)
    if definition.rule_id == "FLOAT_MAXIMUM":
        snapshots = observations_for_event(request, EventType.MARKET_SNAPSHOT)
        known = tuple(item for item in snapshots if isinstance(item.payload, MarketSnapshotPayload)
                      and item.payload.float_shares is not None)
        if not known:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          observation_ids=tuple(str(item.observation_id) for item in snapshots),
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_FLOAT_UNAVAILABLE)
        selected = known[-1]
        value = Decimal(selected.payload.float_shares)
        threshold = definition.thresholds[0]
        outcome = RuleOutcome.PASS if compare(value, threshold.operator, (threshold.value,)) else RuleOutcome.FAIL
        return result(request, definition, outcome, observed_value=value, observed_unit="SHARES",
                      observation_ids=(str(selected.observation_id),))
    raise ValueError(f"unsupported momentum rule: {definition.rule_id}")


__all__ = ["evaluate_momentum_rule"]
