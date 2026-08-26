"""Shared fixtures for BUILD 21 opportunity governance tests."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    ForecastEstimate,
    ForecastV1,
    SnapshotV1,
    ComponentLineage,
)
from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.fusion.types import FINAL_FORECAST_STAGE, ForecastContributorRole
from market_platform_foundation.intelligence.opportunity import OpportunityContext, build_opportunity_policy
from market_platform_foundation.intelligence.promotion.types import ChampionAssignmentV1
from market_platform_foundation.intelligence.quality.models import DecisionAction
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE
from tests.intelligence.routing_fixtures import quality_decision
from tests.intelligence.test_baseline_fixtures import (
    default_horizon,
    default_target,
    QUALITY,
    sample_snapshot,
    statistical_feature_signal,
)


def default_opportunity_policy(**overrides):
    kwargs = {
        "champion_scope": DEFAULT_SCOPE,
        "minimum_probability_edge": 0.05,
        "max_spread_bps": 50.0,
        "max_forecast_age_ns": HORIZON_5M,
    }
    kwargs.update(overrides)
    return build_opportunity_policy(**kwargs)


def champion_forecast(
    champion: ChampionAssignmentV1,
    *,
    forecast_id: str = "fc-champion-1",
    snapshot: SnapshotV1 | None = None,
    probability: float = 0.70,
    calibrated_probability: float | None = 0.72,
    decision_time_ns: int = T,
    forecast_stage: str = FINAL_FORECAST_STAGE,
    contributor_role: str = ForecastContributorRole.PRODUCTION.value,
    predictive_entropy: float | None = 0.2,
) -> ForecastV1:
    snapshot = snapshot or sample_snapshot()
    horizon = default_horizon()
    uncertainty: dict = {}
    if predictive_entropy is not None:
        uncertainty["predictive_entropy"] = predictive_entropy
    metadata = {
        "contributor_role": contributor_role,
        "forecast_stage": forecast_stage,
        "champion_candidate_id": champion.candidate_id,
        "candidate_artifact_hash": champion.candidate_artifact_hash,
        "uncertainty_receipt": {
            "predictive_entropy": predictive_entropy,
            "ood_reasons": [],
        },
    }
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=snapshot.scope,
        decision_time_ns=decision_time_ns,
        snapshot_id=snapshot.snapshot_id,
        target=default_target(),
        horizon=horizon,
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
            raw_score=probability,
            calibrated_probability=calibrated_probability,
        ),
        quality=QUALITY,
        resolve_time_ns=decision_time_ns + horizon.duration_ns,
        uncertainty=uncertainty,
        component_lineage=ComponentLineage(
            component_id="champion-model",
            component_version="1",
            model_id=champion.candidate_id,
            model_version="1",
        ),
        metadata=metadata,
    )


def default_opportunity_context(
    snapshot: SnapshotV1 | None = None,
    *,
    spread_bps: float = 10.0,
    decision_time_ns: int = T + 1_000_000_000,
    depth_imbalance: float | None = 0.1,
) -> OpportunityContext:
    snapshot = snapshot or sample_snapshot()
    spread_signal = statistical_feature_signal(
        snapshot_id=snapshot.snapshot_id,
        signal_type="spread_bps",
        value=spread_bps,
        signal_id="sig-spread",
        calculator_id="spread-calculator",
    )
    return OpportunityContext(
        snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot.snapshot_id),
        snapshot_available_time_ns=snapshot.decision_time_ns,
        signal_refs=(ContractReference(kind=ContractKind.SIGNAL.value, id=spread_signal.signal_id),),
        spread_bps=spread_bps,
        spread_available_time_ns=decision_time_ns,
        depth_imbalance=depth_imbalance,
        depth_available_time_ns=decision_time_ns,
        quality_decision=quality_decision(),
        mode=DEFAULT_SCOPE.mode,
    )


__all__ = [
    "champion_forecast",
    "default_opportunity_context",
    "default_opportunity_policy",
]
