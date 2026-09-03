from decimal import Decimal

from squeeze_core.contracts import (
    BorrowAvailabilityPayload, BorrowFeePayload, EventType, PublishedShortInterestPayload,
    QualityState,
)
from squeeze_core.metrics import MetricName, MetricUnit

from ..diagnostics import EvaluationDiagnosticCode
from ..models import RuleDefinition, RuleEvaluationRequest, RuleOutcome
from ..selectors import is_insufficient_metric, observations_for_event, select_metric
from .common import compare, result


_METRIC_RULES = {
    "SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM": (
        MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE, MetricUnit.PERCENT,
        EvaluationDiagnosticCode.EVALUATION_SHORT_INTEREST_CHANGE_UNAVAILABLE,
    ),
    "DAYS_TO_COVER_MINIMUM": (
        MetricName.DAYS_TO_COVER, MetricUnit.DAYS,
        EvaluationDiagnosticCode.EVALUATION_DAYS_TO_COVER_UNAVAILABLE,
    ),
    "BORROW_FEE_CHANGE_MINIMUM": (
        MetricName.BORROW_FEE_ABSOLUTE_CHANGE, MetricUnit.PERCENTAGE_POINTS,
        EvaluationDiagnosticCode.EVALUATION_BORROW_FEE_UNAVAILABLE,
    ),
    "BORROW_AVAILABILITY_CHANGE_MAXIMUM": (
        MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE, MetricUnit.SHARES,
        EvaluationDiagnosticCode.EVALUATION_BORROW_AVAILABILITY_UNAVAILABLE,
    ),
}


def _metric_rule(request: RuleEvaluationRequest, definition: RuleDefinition):
    name, expected_unit, unavailable = _METRIC_RULES[definition.rule_id]
    metric = select_metric(request, name)
    if metric is None:
        return result(request, definition, RuleOutcome.UNKNOWN, diagnostic_code=unavailable)
    metric_ids = (str(metric.deterministic_id),)
    if metric.quality.state is QualityState.CONFLICTED:
        return result(request, definition, RuleOutcome.CONFLICTED, metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_CONFLICTED)
    if is_insufficient_metric(metric):
        return result(request, definition, RuleOutcome.INSUFFICIENT_DATA, metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_REQUIRED_HISTORY_INSUFFICIENT)
    if metric.value is None:
        return result(request, definition, RuleOutcome.UNKNOWN, metric_ids=metric_ids,
                      diagnostic_code=unavailable)
    if metric.unit is not expected_unit:
        return result(request, definition, RuleOutcome.INSUFFICIENT_DATA,
                      observed_value=metric.value, observed_unit=metric.unit.value,
                      metric_ids=metric_ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_UNIT_INCOMPATIBLE)
    threshold = definition.thresholds[0]
    outcome = RuleOutcome.PASS if compare(metric.value, threshold.operator, (threshold.value,)) else RuleOutcome.FAIL
    return result(request, definition, outcome, observed_value=metric.value,
                  observed_unit=metric.unit.value, metric_ids=metric_ids)


def _direct_value(request: RuleEvaluationRequest, definition: RuleDefinition):
    if definition.rule_id == "BORROW_FEE_MINIMUM":
        event_type = EventType.BORROW_FEE
        unavailable = EvaluationDiagnosticCode.EVALUATION_BORROW_FEE_UNAVAILABLE
        unit = "PERCENT"
        getter = lambda item: item.payload.annualized_fee_percent if isinstance(item.payload, BorrowFeePayload) else None
    else:
        event_type = EventType.BORROW_AVAILABILITY
        unavailable = EvaluationDiagnosticCode.EVALUATION_BORROW_AVAILABILITY_UNAVAILABLE
        unit = "SHARES"
        getter = lambda item: item.payload.available_shares if isinstance(item.payload, BorrowAvailabilityPayload) else None
    items = observations_for_event(request, event_type)
    if request.borrow_provider is not None:
        items = tuple(
            item for item in items if item.provenance.provider == request.borrow_provider
        )
    ids = tuple(str(item.observation_id) for item in items)
    if request.borrow_provider is None and len({item.provenance.provider for item in items}) > 1:
        return result(request, definition, RuleOutcome.UNKNOWN, observation_ids=ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PROVIDER_SCOPE_REQUIRED)
    if any(item.quality.state is QualityState.CONFLICTED for item in items):
        return result(request, definition, RuleOutcome.CONFLICTED, observation_ids=ids,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_CONFLICTED)
    known = tuple((item, getter(item)) for item in items if getter(item) is not None)
    if not known:
        return result(request, definition, RuleOutcome.UNKNOWN, observation_ids=ids,
                      diagnostic_code=unavailable)
    selected, raw = known[-1]
    value = Decimal(raw)
    threshold = definition.thresholds[0]
    outcome = RuleOutcome.PASS if compare(value, threshold.operator, (threshold.value,)) else RuleOutcome.FAIL
    return result(request, definition, outcome, observed_value=value, observed_unit=unit,
                  observation_ids=(str(selected.observation_id),))


def evaluate_short_pressure_rule(
    request: RuleEvaluationRequest, definition: RuleDefinition
):
    if definition.applicable_asset_classes and request.asset_class not in definition.applicable_asset_classes:
        return result(request, definition, RuleOutcome.NOT_APPLICABLE,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_NOT_APPLICABLE)
    if definition.provider_scope_required and not request.provider_scope:
        return result(request, definition, RuleOutcome.UNKNOWN,
                      diagnostic_code=EvaluationDiagnosticCode.EVALUATION_PROVIDER_SCOPE_REQUIRED)
    if definition.rule_id == "PUBLISHED_SHORT_INTEREST_AVAILABLE":
        items = observations_for_event(request, EventType.PUBLISHED_SHORT_INTEREST)
        ids = tuple(str(item.observation_id) for item in items)
        if any(item.quality.state is QualityState.CONFLICTED for item in items):
            return result(request, definition, RuleOutcome.CONFLICTED, observation_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_INPUT_CONFLICTED)
        known = tuple(item for item in items if isinstance(item.payload, PublishedShortInterestPayload)
                      and item.payload.short_shares is not None)
        if not known:
            return result(request, definition, RuleOutcome.UNKNOWN, observation_ids=ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_SHORT_INTEREST_UNAVAILABLE)
        return result(request, definition, RuleOutcome.PASS, observed_value=len(known),
                      observed_unit="OBSERVATIONS",
                      observation_ids=tuple(str(item.observation_id) for item in known))
    if definition.rule_id in _METRIC_RULES:
        return _metric_rule(request, definition)
    if definition.rule_id in {"BORROW_FEE_MINIMUM", "BORROW_AVAILABILITY_MAXIMUM"}:
        return _direct_value(request, definition)
    raise ValueError(f"unsupported short-pressure rule: {definition.rule_id}")


__all__ = ["evaluate_short_pressure_rule"]
