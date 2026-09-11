"""Non-executable strategy evaluation decision construction."""

from __future__ import annotations

from ...canonical import canonical_bytes, sha256_bytes

from .contracts import PolicyClassification, StrategyEvaluationDecision, StrategyFeatureSnapshot
from .policies import PolicyRegistry, StrategyPolicyDefinition, decision_to_units


def build_evaluation_decision(
    *,
    evaluation_run_id: str,
    sample_id: str,
    policy: StrategyPolicyDefinition,
    snapshot: StrategyFeatureSnapshot,
    config_hash: str,
    overlap_flags: tuple[str, ...] = (),
) -> StrategyEvaluationDecision:
    decision = PolicyRegistry().evaluate(policy, snapshot)
    identity = sha256_bytes(
        canonical_bytes(
            {
                "evaluation_run_id": evaluation_run_id,
                "sample_id": sample_id,
                "policy_id": policy.policy_id,
                "policy_version": policy.version,
                "snapshot_hash": snapshot.snapshot_hash,
            }
        )
    )
    return StrategyEvaluationDecision(
        decision_id=f"EVDEC-{identity[:16]}",
        evaluation_run_id=evaluation_run_id,
        sample_id=sample_id,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_classification=policy.classification,
        config_hash=config_hash,
        as_of=snapshot.as_of,
        instrument_id=snapshot.instrument_id,
        asset_class=snapshot.asset_class,
        decision=decision,
        normalized_directional_units=decision_to_units(decision),
        simulation_only=True,
        execution_authority=False,
        news_event_ids=snapshot.news_event_ids,
        inference_record_ids=(
            (snapshot.intelligence.inference_record_id,) if snapshot.intelligence else ()
        ),
        feature_snapshot_id=snapshot.snapshot_id,
        market_snapshot_ref=snapshot.market.market_data_ref,
        overlap_flags=overlap_flags,
    )


def is_abstention(decision: StrategyEvaluationDecision) -> bool:
    return decision.decision.value == "NEUTRAL" or decision.normalized_directional_units == 0


__all__ = ["build_evaluation_decision", "is_abstention"]
