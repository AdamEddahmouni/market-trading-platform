"""Evaluation-shadow records — zero order authority."""

from __future__ import annotations

from .contracts import EvaluationDecision, EvaluationShadowRecord, StrategyEvaluationDecision
from .errors import EvaluationError, EvaluationErrorCode
from .hashing import shadow_record_hash


def build_shadow_record(
    decision: StrategyEvaluationDecision,
    *,
    recorded_at: str,
) -> EvaluationShadowRecord:
    if decision.execution_authority:
        raise EvaluationError(
            EvaluationErrorCode.SHADOW_EXECUTION_AUTHORITY,
            "shadow record cannot carry execution authority",
        )
    body = {
        "evaluation_run_id": decision.evaluation_run_id,
        "decision_id": decision.decision_id,
        "as_of": decision.as_of,
        "instrument_id": decision.instrument_id,
        "decision": decision.decision.value,
        "normalized_directional_units": decision.normalized_directional_units,
        "simulation_only": decision.simulation_only,
        "execution_authority": decision.execution_authority,
        "feature_snapshot_id": decision.feature_snapshot_id,
        "recorded_at": recorded_at,
    }
    shadow_hash = shadow_record_hash(body)
    return EvaluationShadowRecord(
        shadow_id=f"EVSHDW-{shadow_hash[:16]}",
        evaluation_run_id=decision.evaluation_run_id,
        decision_id=decision.decision_id,
        as_of=decision.as_of,
        instrument_id=decision.instrument_id,
        decision=EvaluationDecision(decision.decision.value),
        normalized_directional_units=decision.normalized_directional_units,
        simulation_only=True,
        execution_authority=False,
        feature_snapshot_id=decision.feature_snapshot_id,
        recorded_at=recorded_at,
        shadow_hash=shadow_hash,
    )


def assert_not_executable(shadow: EvaluationShadowRecord) -> None:
    if shadow.execution_authority or not shadow.simulation_only:
        raise EvaluationError(
            EvaluationErrorCode.SHADOW_EXECUTION_AUTHORITY,
            "shadow record is not executable-safe",
        )


__all__ = ["assert_not_executable", "build_shadow_record"]
