"""Shared fixtures for BUILD 20 promotion governance tests."""

from __future__ import annotations

import tempfile

from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import (
    ChampionScopeV1,
    ComplexityPolicy,
    ComplexityPolicyKind,
    GuardrailRule,
    MetricDirection,
    PromotionEngine,
    StatisticalRequirementKind,
    build_promotion_policy,
)
from market_platform_foundation.intelligence.research_experiments.types import ComplexityBudget, EvidenceTier
from market_platform_foundation.intelligence.training.datasets import build_dataset_from_examples
from market_platform_foundation.intelligence.training.search import expand_candidate_specs
from market_platform_foundation.intelligence.training.trainers import get_trainer
from market_platform_foundation.intelligence.training.types import TrainerKind
from market_platform_foundation.intelligence.validation import (
    ValidationEngine,
    ValidationExample,
    ValidationRunContext,
    build_validation_plan,
    statistical_candidate_profile,
)
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.test_baseline_fixtures import default_target
from tests.intelligence.test_training_factory import _experiment_manifest, _synthetic_examples
from tests.intelligence.test_validation_temporal_firewall import (
    _holdout_examples,
    _manifest_with_holdout,
    _trained_candidate,
)

DEFAULT_SCOPE = ChampionScopeV1(
    component="baseline-prediction",
    target_kind="direction_up_down",
    horizon_ns=HORIZON_5M,
    mode="ACTUAL_LIVE",
)


def default_promotion_policy(**overrides):
    kwargs = {
        "champion_scope": DEFAULT_SCOPE,
        "required_improvement": 0.001,
        "minimum_holdout_samples": 4,
        "minimum_shadow_samples": 0,
        "statistical_requirement": StatisticalRequirementKind.NONE,
    }
    kwargs.update(overrides)
    return build_promotion_policy(**kwargs)


def shadow_promotion_policy(**overrides):
    kwargs = {
        "champion_scope": DEFAULT_SCOPE,
        "required_improvement": 0.001,
        "minimum_holdout_samples": 4,
        "minimum_shadow_samples": 4,
        "minimum_shadow_duration_ns": 10,
        "require_shadow_evidence": True,
        "statistical_requirement": StatisticalRequirementKind.NONE,
    }
    kwargs.update(overrides)
    return build_promotion_policy(**kwargs)


def validated_candidate_bundle(*, candidate_better: bool = True):
    repo = InMemoryIntelligenceRepository()
    manifest = _manifest_with_holdout(T + 8)
    candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
    plan = build_validation_plan(
        manifest,
        (candidate,),
        control_ref="baseline_control",
        fold_boundaries_ns=(T, T + 4, T + 8),
        minimum_paired_sample=3,
    )
    engine = ValidationEngine(repo)
    report = engine.validate(
        ValidationRunContext(
            plan=plan,
            experiment=manifest,
            candidates=(candidate,),
            training_dataset=dataset_manifest,
            holdout_examples=_holdout_examples(candidate_better=candidate_better),
            fold_examples={},
            knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
            artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
            guardrail_thresholds={},
        )
    )
    return repo, manifest, candidate, artifact_bytes, report, plan


def bootstrap_control_champion(engine: PromotionEngine, candidate, *, effective_from_ns: int = T):
    return engine.bootstrap_champion(
        champion_scope=DEFAULT_SCOPE,
        candidate=candidate,
        effective_from_ns=effective_from_ns,
    )


def shadow_observations(count: int, *, challenger_better: bool = True, start_ns: int = T + 100):
    rows = []
    for idx in range(count):
        label = 1 if idx % 2 == 0 else 0
        if challenger_better:
            challenger_p = 0.85 if label == 1 else 0.15
            champion_p = 0.65 if label == 1 else 0.35
        else:
            challenger_p = 0.65 if label == 1 else 0.35
            champion_p = 0.65 if label == 1 else 0.35
        rows.append(
            {
                "opportunity_key": f"opp-{idx}",
                "decision_time_ns": start_ns + idx * 5,
                "champion_forecast_id": f"fc-ch-{idx}",
                "challenger_forecast_id": f"fc-cl-{idx}",
                "outcome_id": f"out-{idx}",
                "settled": True,
                "champion_probability": champion_p,
                "challenger_probability": challenger_p,
                "binary_label": label,
            }
        )
    return rows
