from squeeze_core.contracts import EventType, NewsItemPayload

from ..diagnostics import EvaluationDiagnosticCode
from ..models import RuleDefinition, RuleEvaluationRequest, RuleOutcome
from ..selectors import observations_for_event
from .common import result


_WITHDRAWN = {"WITHDRAWN", "DELETED"}


def _active_news(request: RuleEvaluationRequest):
    return tuple(
        item for item in observations_for_event(request, EventType.NEWS_ITEM)
        if str(item.provenance.provider_metadata.get("status")) not in _WITHDRAWN
    )


def evaluate_catalyst_rule(request: RuleEvaluationRequest, definition: RuleDefinition):
    rule_id = definition.rule_id
    if rule_id in {"NEWS_AVAILABLE", "NEWS_AVAILABLE_BEFORE_AS_OF", "NEWS_TIMESTAMP_KNOWN"}:
        items = _active_news(request)
        ids = tuple(str(item.observation_id) for item in items)
        future = tuple(
            item for item in request.input_observations
            if item.event_type is EventType.NEWS_ITEM
            and item.source_timestamp > request.as_of
            and (not request.provider_scope or item.provenance.provider in request.provider_scope)
        )
        if rule_id == "NEWS_AVAILABLE_BEFORE_AS_OF" and not items and future:
            future_ids = tuple(str(item.observation_id) for item in future)
            return result(request, definition, RuleOutcome.FAIL, observed_value=0,
                          observed_unit="OBSERVATIONS", observation_ids=future_ids,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_NEWS_AFTER_AS_OF)
        if not items:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_NEWS_UNAVAILABLE)
        if rule_id == "NEWS_TIMESTAMP_KNOWN":
            known = tuple(item for item in items if isinstance(item.payload, NewsItemPayload)
                          and item.payload.published_at is not None)
            if not known:
                return result(request, definition, RuleOutcome.UNKNOWN, observation_ids=ids,
                              diagnostic_code=EvaluationDiagnosticCode.EVALUATION_NEWS_TIMESTAMP_UNKNOWN)
            return result(request, definition, RuleOutcome.PASS, observed_value=len(known),
                          observed_unit="OBSERVATIONS",
                          observation_ids=tuple(str(item.observation_id) for item in known))
        return result(request, definition, RuleOutcome.PASS, observed_value=len(items),
                      observed_unit="OBSERVATIONS", observation_ids=ids)

    if rule_id == "SEC_FILING_AVAILABLE":
        items = observations_for_event(request, EventType.SEC_FILING)
        if not items:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_SEC_FILING_UNAVAILABLE)
        return result(request, definition, RuleOutcome.PASS, observed_value=len(items),
                      observed_unit="OBSERVATIONS",
                      observation_ids=tuple(str(item.observation_id) for item in items))

    if rule_id == "CORPORATE_ACTION_CONTEXT_AVAILABLE":
        items = observations_for_event(request, EventType.CORPORATE_ACTION)
        if not items:
            return result(request, definition, RuleOutcome.UNKNOWN,
                          diagnostic_code=EvaluationDiagnosticCode.EVALUATION_CORPORATE_ACTION_UNAVAILABLE)
        return result(request, definition, RuleOutcome.PASS, observed_value=len(items),
                      observed_unit="OBSERVATIONS",
                      observation_ids=tuple(str(item.observation_id) for item in items))
    raise ValueError(f"unsupported catalyst rule: {rule_id}")


__all__ = ["evaluate_catalyst_rule"]
