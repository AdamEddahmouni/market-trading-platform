"""Validation plan construction (BUILD 19)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import ExperimentManifestV1
from ..training.authorization import holdout_boundary_ns
from ..training.types import CandidateArtifactV1
from .identity import derive_validation_plan_id
from .temporal_knowledge import DEFAULT_TEMPORAL_KNOWLEDGE_POLICY
from .types import (
    HoldoutSpec,
    StatisticalPlan,
    ValidationPlanV1,
    WalkForwardMode,
    WalkForwardSpec,
)


def build_validation_plan(
    experiment: ExperimentManifestV1,
    candidates: tuple[CandidateArtifactV1, ...],
    *,
    control_ref: str,
    fold_boundaries_ns: tuple[int, ...] | None = None,
    walk_forward_mode: WalkForwardMode = WalkForwardMode.EXPANDING,
    fold_candidate_ids: tuple[str | None, ...] = (),
    purge_ns: int = 0,
    embargo_ns: int = 0,
    statistical_plan: StatisticalPlan | None = None,
    guardrail_metrics: tuple[str, ...] = (),
    minimum_paired_sample: int = 5,
) -> ValidationPlanV1:
    if not candidates:
        raise ValueError("CANDIDATES_REQUIRED")

    holdout_start = holdout_boundary_ns(experiment)
    holdout_end = experiment.data_spec.decision_end_ns
    if holdout_start is None or holdout_start >= holdout_end:
        holdout_start = experiment.metadata.get("holdout_start_ns", holdout_end - 1)
        if holdout_start >= holdout_end:
            raise ValueError("HOLDOUT_RANGE_INVALID")

    walk_forward: WalkForwardSpec | None = None
    if experiment.validation_requirements.requires_walk_forward:
        if fold_boundaries_ns is None:
            dev_end = holdout_start
            dev_start = experiment.data_spec.decision_start_ns
            midpoint = dev_start + (dev_end - dev_start) // 2
            fold_boundaries_ns = (dev_start, midpoint, dev_end)
        walk_forward = WalkForwardSpec(
            mode=walk_forward_mode,
            fold_boundaries_ns=fold_boundaries_ns,
            fold_candidate_ids=fold_candidate_ids,
        )

    stats = statistical_plan or StatisticalPlan(
        block_length=2,
        replicate_count=200,
        seed=19,
        confidence_level=0.95,
        minimum_paired_sample=minimum_paired_sample,
        criterion_upper_ci_bound_lt_zero=True,
    )

    guardrails = guardrail_metrics or tuple(
        g.metric_name for g in experiment.guardrails
    )

    plan_body = ValidationPlanV1(
        validation_plan_id="PENDING",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        experiment_id=experiment.experiment_id,
        candidate_ids=tuple(c.candidate_id for c in candidates),
        candidate_artifact_hashes=tuple(c.artifact_hash for c in candidates),
        control_ref=control_ref,
        target_kind=experiment.data_spec.target_kind,
        horizon_ns=experiment.data_spec.horizon_ns,
        mode=experiment.data_spec.mode,
        scenario_id=experiment.data_spec.scenario_id,
        validation_method="WALK_FORWARD_PLUS_LOCKED_HOLDOUT",
        walk_forward_spec=walk_forward,
        purge_ns=purge_ns if experiment.validation_requirements.requires_purge else 0,
        embargo_ns=embargo_ns if experiment.validation_requirements.requires_embargo else 0,
        holdout_spec=HoldoutSpec(
            holdout_start_ns=int(holdout_start),
            holdout_end_ns=holdout_end,
        ),
        primary_metric=experiment.metric_plan.primary_metric,
        guardrail_metrics=guardrails,
        statistical_plan=stats,
        temporal_knowledge_policy=DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
        minimum_paired_sample=minimum_paired_sample,
    )
    plan_id = derive_validation_plan_id(plan_body)
    return ValidationPlanV1(
        validation_plan_id=plan_id,
        schema_version=plan_body.schema_version,
        experiment_id=plan_body.experiment_id,
        candidate_ids=plan_body.candidate_ids,
        candidate_artifact_hashes=plan_body.candidate_artifact_hashes,
        control_ref=plan_body.control_ref,
        target_kind=plan_body.target_kind,
        horizon_ns=plan_body.horizon_ns,
        mode=plan_body.mode,
        scenario_id=plan_body.scenario_id,
        validation_method=plan_body.validation_method,
        walk_forward_spec=plan_body.walk_forward_spec,
        purge_ns=plan_body.purge_ns,
        embargo_ns=plan_body.embargo_ns,
        holdout_spec=plan_body.holdout_spec,
        primary_metric=plan_body.primary_metric,
        guardrail_metrics=plan_body.guardrail_metrics,
        statistical_plan=plan_body.statistical_plan,
        temporal_knowledge_policy=plan_body.temporal_knowledge_policy,
        minimum_paired_sample=plan_body.minimum_paired_sample,
        metadata=plan_body.metadata,
    )


__all__ = ["build_validation_plan"]
