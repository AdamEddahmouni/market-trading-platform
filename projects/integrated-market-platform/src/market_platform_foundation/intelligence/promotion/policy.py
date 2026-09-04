"""Promotion policy construction helpers (BUILD 20)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import EvidenceTier
from ..validation.types import ValidationDisposition
from .identity import derive_promotion_policy_id
from .types import (
    ChampionScopeV1,
    ComplexityPolicy,
    ComplexityPolicyKind,
    GuardrailRule,
    MetricDirection,
    PromotionPolicyV1,
    StatisticalRequirementKind,
)


def build_promotion_policy(
    *,
    champion_scope: ChampionScopeV1,
    primary_metric: str = "brier_score",
    primary_metric_direction: MetricDirection = MetricDirection.LOWER_IS_BETTER,
    required_improvement: float = 0.005,
    guardrails: tuple[GuardrailRule, ...] = (),
    minimum_walk_forward_folds: int = 0,
    minimum_holdout_samples: int = 8,
    minimum_shadow_samples: int = 0,
    minimum_shadow_duration_ns: int = 0,
    require_shadow_evidence: bool = False,
    require_forward_shadow_evidence: bool = False,
    allowed_shadow_evidence_tiers: tuple[EvidenceTier, ...] = (
        EvidenceTier.ACTUAL_LIVE,
        EvidenceTier.OBSERVED_REPLAY,
    ),
    statistical_requirement: StatisticalRequirementKind = StatisticalRequirementKind.HOLDOUT_PAIRED_CI_IMPROVEMENT,
    complexity_policy: ComplexityPolicy | None = None,
    allowed_validation_modes: tuple[str, ...] = ("COUNTERFACTUAL", "OBSERVED_REPLAY"),
) -> PromotionPolicyV1:
    policy_body = PromotionPolicyV1(
        promotion_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        required_validation_dispositions=(ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA,),
        require_clean_contamination=True,
        require_temporal_knowledge_pass=True,
        require_artifact_integrity=True,
        primary_metric=primary_metric,
        primary_metric_direction=primary_metric_direction,
        required_improvement=required_improvement,
        secondary_metrics=(),
        guardrails=guardrails,
        minimum_walk_forward_folds=minimum_walk_forward_folds,
        minimum_holdout_samples=minimum_holdout_samples,
        minimum_shadow_samples=minimum_shadow_samples,
        minimum_shadow_duration_ns=minimum_shadow_duration_ns,
        require_locked_holdout=True,
        require_shadow_evidence=require_shadow_evidence,
        require_forward_shadow_evidence=require_forward_shadow_evidence,
        allowed_shadow_evidence_tiers=allowed_shadow_evidence_tiers,
        statistical_requirement=statistical_requirement,
        complexity_policy=complexity_policy
        or ComplexityPolicy(
            kind=ComplexityPolicyKind.TIERED_MARGIN,
            base_required_improvement=required_improvement,
            minor_complexity_additional_margin=0.005,
            major_complexity_additional_margin=0.01,
        ),
        allowed_validation_modes=allowed_validation_modes,
    )
    policy_id = derive_promotion_policy_id(policy_body)
    return PromotionPolicyV1(
        promotion_policy_id=policy_id,
        schema_version=policy_body.schema_version,
        champion_scope=policy_body.champion_scope,
        required_validation_dispositions=policy_body.required_validation_dispositions,
        require_clean_contamination=policy_body.require_clean_contamination,
        require_temporal_knowledge_pass=policy_body.require_temporal_knowledge_pass,
        require_artifact_integrity=policy_body.require_artifact_integrity,
        primary_metric=policy_body.primary_metric,
        primary_metric_direction=policy_body.primary_metric_direction,
        required_improvement=policy_body.required_improvement,
        secondary_metrics=policy_body.secondary_metrics,
        guardrails=policy_body.guardrails,
        minimum_walk_forward_folds=policy_body.minimum_walk_forward_folds,
        minimum_holdout_samples=policy_body.minimum_holdout_samples,
        minimum_shadow_samples=policy_body.minimum_shadow_samples,
        minimum_shadow_duration_ns=policy_body.minimum_shadow_duration_ns,
        require_locked_holdout=policy_body.require_locked_holdout,
        require_shadow_evidence=policy_body.require_shadow_evidence,
        require_forward_shadow_evidence=policy_body.require_forward_shadow_evidence,
        allowed_shadow_evidence_tiers=policy_body.allowed_shadow_evidence_tiers,
        statistical_requirement=policy_body.statistical_requirement,
        complexity_policy=policy_body.complexity_policy,
        allowed_validation_modes=policy_body.allowed_validation_modes,
        implementation_version=policy_body.implementation_version,
        metadata=policy_body.metadata,
    )


__all__ = ["build_promotion_policy"]
