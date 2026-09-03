"""Shadow challenger evidence assembly (BUILD 20)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..evaluation.metrics import compute_brier_contribution, compute_log_loss_contribution
from ..research_experiments.types import EvidenceTier
from .errors import PromotionError
from .identity import derive_shadow_evidence_id
from .types import (
    ShadowEvidenceManifestV1,
    ShadowMatchedObservation,
)


def build_shadow_evidence_manifest(
    *,
    challenger_registration_id: str,
    champion_assignment_id: str,
    promotion_policy_id: str,
    evidence_tier: EvidenceTier,
    matched_observations: tuple[ShadowMatchedObservation, ...],
    unmatched_champion_count: int = 0,
    unmatched_challenger_count: int = 0,
    require_settlement_complete: bool = True,
    evaluation_report_ids: tuple[str, ...] = (),
) -> ShadowEvidenceManifestV1:
    if not matched_observations:
        raise PromotionError("SHADOW_OBSERVATIONS_REQUIRED")
    decision_times = [obs.decision_time_ns for obs in matched_observations]
    decision_start_ns = min(decision_times)
    decision_end_ns = max(decision_times)
    duration_ns = decision_end_ns - decision_start_ns
    settlement_complete = all(obs.settled for obs in matched_observations)
    if require_settlement_complete and not settlement_complete:
        raise PromotionError("SHADOW_SETTLEMENT_INCOMPLETE")

    body = ShadowEvidenceManifestV1(
        shadow_evidence_id="",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        challenger_registration_id=challenger_registration_id,
        champion_assignment_id=champion_assignment_id,
        promotion_policy_id=promotion_policy_id,
        evidence_tier=evidence_tier,
        decision_start_ns=decision_start_ns,
        decision_end_ns=decision_end_ns,
        matched_observations=matched_observations,
        unmatched_champion_count=unmatched_champion_count,
        unmatched_challenger_count=unmatched_challenger_count,
        sample_count=len(matched_observations),
        duration_ns=duration_ns,
        settlement_complete=settlement_complete,
        evaluation_report_ids=evaluation_report_ids,
    )
    evidence_id = derive_shadow_evidence_id(body)
    return ShadowEvidenceManifestV1(
        shadow_evidence_id=evidence_id,
        schema_version=body.schema_version,
        challenger_registration_id=body.challenger_registration_id,
        champion_assignment_id=body.champion_assignment_id,
        promotion_policy_id=body.promotion_policy_id,
        evidence_tier=body.evidence_tier,
        decision_start_ns=body.decision_start_ns,
        decision_end_ns=body.decision_end_ns,
        matched_observations=body.matched_observations,
        unmatched_champion_count=body.unmatched_champion_count,
        unmatched_challenger_count=body.unmatched_challenger_count,
        sample_count=body.sample_count,
        duration_ns=body.duration_ns,
        settlement_complete=body.settlement_complete,
        evaluation_report_ids=body.evaluation_report_ids,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


def aggregate_shadow_metric(
    observations: tuple[ShadowMatchedObservation, ...],
    *,
    metric_name: str,
    role: str,
    log_loss_epsilon: float = 1e-15,
) -> float | None:
    values: list[float] = []
    for obs in observations:
        if obs.binary_label is None:
            continue
        probability = obs.challenger_probability if role == "challenger" else obs.champion_probability
        if metric_name == "brier_score":
            values.append(compute_brier_contribution(probability, obs.binary_label))
        elif metric_name == "log_loss":
            values.append(compute_log_loss_contribution(probability, obs.binary_label, log_loss_epsilon))
        elif metric_name == "directional_hit_rate":
            predicted_up = probability >= 0.5
            actual_up = obs.binary_label == 1
            values.append(1.0 if predicted_up == actual_up else 0.0)
        else:
            return None
    if not values:
        return None
    return sum(values) / len(values)


def shadow_paired_deltas(
    observations: tuple[ShadowMatchedObservation, ...],
    *,
    metric_name: str,
    log_loss_epsilon: float = 1e-15,
) -> tuple[float, ...]:
    deltas: list[float] = []
    for obs in observations:
        if obs.binary_label is None:
            continue
        y = obs.binary_label
        if metric_name == "brier_score":
            challenger = compute_brier_contribution(obs.challenger_probability, y)
            champion = compute_brier_contribution(obs.champion_probability, y)
            deltas.append(challenger - champion)
        elif metric_name == "log_loss":
            challenger = compute_log_loss_contribution(obs.challenger_probability, y, log_loss_epsilon)
            champion = compute_log_loss_contribution(obs.champion_probability, y, log_loss_epsilon)
            deltas.append(challenger - champion)
        elif metric_name == "directional_hit_rate":
            challenger_hit = 1.0 if (obs.challenger_probability >= 0.5) == (y == 1) else 0.0
            champion_hit = 1.0 if (obs.champion_probability >= 0.5) == (y == 1) else 0.0
            deltas.append(challenger_hit - champion_hit)
    return tuple(deltas)


__all__ = [
    "aggregate_shadow_metric",
    "build_shadow_evidence_manifest",
    "shadow_paired_deltas",
]
