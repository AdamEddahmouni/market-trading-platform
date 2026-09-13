"""Handoff from recorded news_strategy_evaluation artifacts to forward-test bridge."""

from __future__ import annotations

from typing import Any, Mapping

from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (
    EvaluationDecision,
    PolicyClassification,
    StrategyEvaluationDecision,
)

from .types import ForwardTestEvidenceClass, ForwardTestMode


class RecordedEvalBridgeError(ValueError):
    """Recorded evaluation artifact cannot be bridged."""


def strategy_evaluation_decision_from_recorded(payload: Mapping[str, Any]) -> StrategyEvaluationDecision:
    try:
        policy_class = PolicyClassification(str(payload["policy_classification"]))
        decision = EvaluationDecision(str(payload["decision"]))
    except (KeyError, ValueError) as exc:
        raise RecordedEvalBridgeError("RECORDED_EVAL_DECISION_INVALID") from exc
    if bool(payload.get("execution_authority")):
        raise RecordedEvalBridgeError("RECORDED_EVAL_EXECUTION_AUTHORITY_FORBIDDEN")
    return StrategyEvaluationDecision(
        decision_id=str(payload.get("decision_id") or ""),
        evaluation_run_id=str(payload.get("evaluation_run_id") or ""),
        sample_id=str(payload.get("sample_id") or ""),
        policy_id=str(payload.get("policy_id") or ""),
        policy_version=str(payload.get("policy_version") or ""),
        policy_classification=policy_class,
        config_hash=str(payload.get("config_hash") or ""),
        as_of=str(payload.get("as_of") or ""),
        instrument_id=str(payload.get("instrument_id") or ""),
        asset_class=str(payload.get("asset_class") or ""),
        decision=decision,
        normalized_directional_units=int(payload.get("normalized_directional_units") or 0),
        simulation_only=bool(payload.get("simulation_only", True)),
        execution_authority=False,
        news_event_ids=tuple(str(x) for x in (payload.get("news_event_ids") or [])),
        inference_record_ids=tuple(str(x) for x in (payload.get("inference_record_ids") or [])),
        feature_snapshot_id=str(payload.get("feature_snapshot_id") or ""),
        market_snapshot_ref=str(payload.get("market_snapshot_ref") or ""),
        overlap_flags=tuple(str(x) for x in (payload.get("overlap_flags") or [])),
    )


def recorded_eval_forward_handoff_params(
    decision: StrategyEvaluationDecision,
    *,
    decision_time_ns: int,
    source_time_ns: int,
    test_mode: ForwardTestMode = ForwardTestMode.SIGNAL_ONLY,
) -> dict[str, Any]:
    """Keyword args for ``ForwardTestService.create_decision_from_strategy_evaluation``."""
    return {
        "strategy_decision": decision,
        "decision_time_ns": decision_time_ns,
        "source_time_ns": source_time_ns,
        "test_mode": test_mode,
        "evidence_class": ForwardTestEvidenceClass.SOFTWARE_FIXTURE_ONLY.value,
        "intelligence_provider": "RECORDED_ARTIFACTS_ONLY",
    }


__all__ = [
    "RecordedEvalBridgeError",
    "recorded_eval_forward_handoff_params",
    "strategy_evaluation_decision_from_recorded",
]
