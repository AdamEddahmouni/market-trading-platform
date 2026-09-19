"""IBP non-stub SUT: BUILD 09 SmartRouter + grounded evidence inference (no gold, no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...assistant.grounded_inference import GroundedEvidenceInference
from ..contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SemanticEventType,
)
from ..quality import DecisionAction, IntelligenceCapability, QualityAssessment, QualityDecision
from ..routing import RoutingPolicyV1, SmartRouter
from .contamination import assert_no_evaluator_gold_in_system_bundle
from .admitted_factual_gold.admitted_evidence_context import build_admitted_evidence_context
from .admitted_factual_gold.types import IBP_FACTUAL_SMOKE_PROTOCOL_VERSION
from .grounded_fact_extraction import (
    GROUNDED_FACT_EXTRACTION_VERSION,
    answer_admitted_factual_question,
)
from .historical_evidence_context import build_historical_fixture_evidence_context
from .sut_profiles import (
    IBP_FACTS_SUT_MODEL_ID,
    IBP_FACTS_SUT_PROFILE_ID,
    IBP_FACTS_SUT_VERSION,
)

_ROUTER_BASE_TIME_NS = 1_700_000_000_000_000_000
_SCOPE = IntelligenceScope(instrument_ids=("IBP-FIXTURE",))

_BLIND_MODE_EVENT: dict[str, SemanticEventType] = {
    "A": SemanticEventType.ORDER_FLOW_REVERSAL,
    "B": SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY,
    "C": SemanticEventType.BORROW_CHANGE,
    "D": SemanticEventType.NEWS_EVENT,
    "E": SemanticEventType.REGIME_SHIFT,
}

_BLIND_MODE_CAPABILITIES: dict[str, tuple[IntelligenceCapability, ...]] = {
    "A": (IntelligenceCapability.QUOTES, IntelligenceCapability.TRADES),
    "B": (IntelligenceCapability.OPTIONS_CHAIN,),
    "C": (IntelligenceCapability.SHORT_INTEREST,),
    "D": (IntelligenceCapability.NEWS,),
    "E": (IntelligenceCapability.MACRO, IntelligenceCapability.QUOTES),
}


def ibp_blind_mode_routing_plan(blind_mode: str | None) -> tuple[SemanticEventType, tuple[IntelligenceCapability, ...]]:
    mode = str(blind_mode or "A")
    if mode not in _BLIND_MODE_EVENT:
        raise ValueError(f"IBP_BLIND_MODE_UNSUPPORTED:{mode}")
    return _BLIND_MODE_EVENT[mode], _BLIND_MODE_CAPABILITIES[mode]


def _detection_for_blind_mode(
    blind_mode: str,
    *,
    context_reset_token: str,
    case_id: str,
) -> DetectionV1:
    event_type, _ = ibp_blind_mode_routing_plan(blind_mode)
    detected_at = _ROUTER_BASE_TIME_NS + abs(hash(context_reset_token)) % 1_000_000
    return DetectionV1(
        detection_id=f"IBP-DET-{case_id}",
        schema_version="1",
        semantic_event_type=event_type,
        detected_at_ns=detected_at,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=f"ibp-snap-{case_id}"),
        detector_lineage=ComponentLineage(component_id="ibp-facts-sut", component_version=IBP_FACTS_SUT_VERSION),
        scope=_SCOPE,
        severity=DetectionSeverity.MEDIUM,
        reason_codes=("IBP_BLIND_MODE_FIXTURE",),
        quality=QualitySummary(state=QualityState.GOOD),
    )


def _quality_decision_for_mode(
    blind_mode: str,
    *,
    decision_time_ns: int,
) -> QualityDecision:
    _, capabilities = ibp_blind_mode_routing_plan(blind_mode)
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=DecisionAction.USE,
        quality_state=QualityState.GOOD,
        assessment=assessment,
        satisfied_requirements=capabilities,
        degraded_requirements=(),
        reasons=("IBP_HISTORICAL_FIXTURE_CAPABILITIES",),
    )


def _load_historical_fixture_summary(repository_root: Path, fixture_rel: str | None) -> dict[str, Any] | None:
    if not fixture_rel:
        return None
    path = repository_root / fixture_rel
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload and all(isinstance(value, list) for value in payload.values()):
        rows: list[Any] = []
        for value in payload.values():
            rows.extend(value)
        row_count = len(rows)
        instruments = sorted(
            {
                str(row.get("code") or row.get("instrument_id") or row.get("symbol") or "UNKNOWN")
                for row in rows[:32]
                if isinstance(row, dict)
            }
        )
    elif isinstance(payload, list):
        row_count = len(payload)
        instruments = sorted({str(row.get("instrument_id") or row.get("symbol") or "UNKNOWN") for row in payload[:32]})
    elif isinstance(payload, dict):
        rows = payload.get("rows") or payload.get("bars") or []
        row_count = len(rows) if isinstance(rows, list) else 0
        instruments = sorted({str(payload.get("instrument_id") or payload.get("symbol") or "UNKNOWN")})
    else:
        return None
    return {
        "fixture_path": fixture_rel,
        "row_count": row_count,
        "instruments": instruments[:8],
        "authority": "HISTORICAL_DEVELOPMENT",
    }


def _facts_prompt(case_id: str, blind_mode: str, *, question_text: str | None = None) -> str:
    if question_text:
        return (
            f"IBP bounded factual probe for {case_id}; "
            f"question: {question_text}; cite admitted evidence only."
        )
    return (
        f"IBP bounded facts probe for {case_id} blind mode {blind_mode}; "
        "cite grounded historical development evidence only."
    )


def _routing_template_for_factual(blind_input: dict[str, Any]) -> str | None:
    routing = blind_input.get("routing_expectation") or {}
    template = routing.get("template")
    return str(template) if template else None


def run_ibp_facts_sut(
    blind_input: dict[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Route through SmartRouter and grounded inference without evaluator gold."""
    assert_no_evaluator_gold_in_system_bundle(blind_input)
    blind_mode = str(blind_input.get("blind_mode") or "A")
    case_id = str(blind_input["case_id"])
    context_reset_token = str(blind_input.get("context_reset_token") or "")
    factual_protocol = blind_input.get("protocol_version") == IBP_FACTUAL_SMOKE_PROTOCOL_VERSION
    routing_template = _routing_template_for_factual(blind_input) if factual_protocol else None
    question = blind_input.get("question") if factual_protocol else None
    question_text = question.get("text") if isinstance(question, dict) else None

    detection = _detection_for_blind_mode(
        blind_mode,
        context_reset_token=context_reset_token,
        case_id=case_id,
    )
    quality = _quality_decision_for_mode(blind_mode, decision_time_ns=detection.detected_at_ns)
    router = SmartRouter(RoutingPolicyV1())
    route = router.route(detection, quality_decision=quality)

    fixture_rel = blind_input.get("historical_harness_fixture")
    admitted_loaded: list[str] = []
    evidence_data_mode = "FIXTURE_REPLAY"
    evidence_context: dict[str, Any] = {
        "ibp_case_id": case_id,
        "ibp_blind_mode": blind_mode,
    }
    if factual_protocol:
        evidence_set = blind_input.get("evidence_set") or {}
        admitted_context = build_admitted_evidence_context(repository_root, evidence_set)
        admitted_loaded = list(admitted_context.get("admitted_evidence_artifacts_loaded") or ())
        evidence_context = {**admitted_context, **evidence_context}
        evidence_data_mode = str(admitted_context.get("evidence_data_mode") or evidence_data_mode)
    else:
        fixture_summary = _load_historical_fixture_summary(repository_root, fixture_rel)
        evidence_context["historical_fixture"] = fixture_summary
        grounded_context = build_historical_fixture_evidence_context(
            repository_root,
            str(fixture_rel) if fixture_rel else None,
        )
        if grounded_context is not None:
            evidence_context = {**grounded_context, **evidence_context}

    structured_facts: list[dict[str, Any]] = []
    factual_disposition: str | None = None
    inference_provider_id = IBP_FACTS_SUT_MODEL_ID.split(":")[0]
    inference_model_id = IBP_FACTS_SUT_MODEL_ID.split(":")[-1]
    abstention_reason: str | None = None

    if factual_protocol and isinstance(question, dict):
        factual_outcome = answer_admitted_factual_question(
            question=question,
            temporal_cutoff=blind_input.get("temporal_cutoff"),
            evidence_set=blind_input.get("evidence_set") or {},
            repository_root=repository_root,
            answer_normalization=blind_input.get("answer_normalization"),
        )
        factual_disposition = factual_outcome.disposition.value
        structured_facts = [dict(row) for row in factual_outcome.structured_facts]
        answer = factual_outcome.answer
        abstention_reason = factual_outcome.abstention_reason
        inference_model_id = f"deterministic.v1+{GROUNDED_FACT_EXTRACTION_VERSION}"
    else:
        inference = GroundedEvidenceInference()
        outcome = inference.infer(
            _facts_prompt(case_id, blind_mode, question_text=question_text),
            evidence_context=evidence_context,
        )
        inference_provider_id = outcome.provider_id
        inference_model_id = outcome.model_id
        abstention_reason = outcome.abstention_reason
        answer = "UNKNOWN" if outcome.abstained or not outcome.content.strip() else outcome.content.strip()
    operator_close = "OK"
    if factual_protocol:
        freshness = "ADMITTED_EVIDENCE_FIXED" if admitted_loaded else "FIXTURE"
        authority = "ADMITTED_EVIDENCE_FIXED" if admitted_loaded else "FIXTURE"
        provenance_complete = bool(admitted_loaded)
    else:
        fixture_summary = evidence_context.get("historical_fixture")
        freshness = "HISTORICAL_DEVELOPMENT" if fixture_summary else "FIXTURE"
        authority = "HISTORICAL_DEVELOPMENT"
        provenance_complete = True

    response = {
        "case_id": case_id,
        "sut_profile_id": IBP_FACTS_SUT_PROFILE_ID,
        "sut_model_id": IBP_FACTS_SUT_MODEL_ID,
        "sut_version": IBP_FACTS_SUT_VERSION,
        "blind_mode": blind_mode,
        "routing": routing_template or blind_mode,
        "routing_template": routing_template,
        "route_action": route.route_action.value,
        "routing_decision_id": route.routing_decision_id,
        "expert_domain": route.expert_domain.value,
        "answer": answer,
        "freshness": freshness,
        "authority": authority,
        "provenance_complete": provenance_complete,
        "inference_provider_id": inference_provider_id,
        "inference_model_id": inference_model_id,
        "inference_abstention_reason": abstention_reason,
        "final_state": "CLOSED",
        "operator_close": operator_close,
        "catastrophic": False,
        "context_reset_token": context_reset_token,
        "evidence_data_mode": evidence_data_mode,
        "live_promotion_allowed": False,
    }
    if factual_protocol:
        response["admitted_evidence_artifacts_loaded"] = admitted_loaded
        response["protocol_version"] = IBP_FACTUAL_SMOKE_PROTOCOL_VERSION
        response["structured_facts"] = structured_facts
        response["grounded_fact_extraction_version"] = GROUNDED_FACT_EXTRACTION_VERSION
        if factual_disposition is not None:
            response["factual_answer_disposition"] = factual_disposition
    else:
        fixture_summary = evidence_context.get("historical_fixture")
        response["historical_fixture_loaded"] = fixture_summary is not None
    return response


__all__ = [
    "ibp_blind_mode_routing_plan",
    "run_ibp_facts_sut",
]
