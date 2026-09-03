"""Opportunity policy construction helpers (BUILD 21)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..evaluation.types import ProbabilityView
from ..fusion.types import FINAL_FORECAST_STAGE
from ..promotion.types import ChampionScopeV1
from ..quality.models import IntelligenceCapability
from .identity import derive_opportunity_policy_id
from .types import OpportunityPolicyV1


def build_opportunity_policy(
    *,
    champion_scope: ChampionScopeV1,
    probability_view: ProbabilityView = ProbabilityView.OPERATIONAL,
    reference_probability: float = 0.5,
    minimum_probability_edge: float = 0.05,
    minimum_probability_edge_strict: bool = False,
    require_calibrated_probability: bool = False,
    max_forecast_age_ns: int | None = None,
    max_opportunity_lifetime_ns: int | None = None,
    max_spread_bps: float | None = 50.0,
    require_spread_bps: bool = False,
    max_predictive_entropy: float | None = None,
    require_uncertainty: bool = False,
    allow_ood: bool = False,
    allow_degraded_quality: bool = False,
    required_capabilities: tuple[IntelligenceCapability, ...] = (),
    allowed_regimes: tuple[str, ...] = (),
    require_regime: bool = False,
    minimum_net_economic_edge_bps: float | None = None,
    allowed_forecast_stages: tuple[str, ...] = (FINAL_FORECAST_STAGE,),
    allowed_contributor_roles: tuple[str, ...] = ("PRODUCTION",),
) -> OpportunityPolicyV1:
    body = OpportunityPolicyV1(
        opportunity_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        allowed_forecast_stages=allowed_forecast_stages,
        allowed_contributor_roles=allowed_contributor_roles,
        probability_view=probability_view,
        reference_probability=reference_probability,
        minimum_probability_edge=minimum_probability_edge,
        minimum_probability_edge_strict=minimum_probability_edge_strict,
        require_calibrated_probability=require_calibrated_probability,
        max_forecast_age_ns=max_forecast_age_ns,
        max_opportunity_lifetime_ns=max_opportunity_lifetime_ns,
        max_spread_bps=max_spread_bps,
        require_spread_bps=require_spread_bps,
        max_predictive_entropy=max_predictive_entropy,
        require_uncertainty=require_uncertainty,
        allow_ood=allow_ood,
        allow_degraded_quality=allow_degraded_quality,
        required_capabilities=required_capabilities,
        allowed_regimes=allowed_regimes,
        require_regime=require_regime,
        minimum_net_economic_edge_bps=minimum_net_economic_edge_bps,
    )
    policy_id = derive_opportunity_policy_id(body)
    return OpportunityPolicyV1(
        opportunity_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        allowed_forecast_stages=body.allowed_forecast_stages,
        allowed_contributor_roles=body.allowed_contributor_roles,
        probability_view=body.probability_view,
        reference_probability=body.reference_probability,
        minimum_probability_edge=body.minimum_probability_edge,
        minimum_probability_edge_strict=body.minimum_probability_edge_strict,
        require_calibrated_probability=body.require_calibrated_probability,
        max_forecast_age_ns=body.max_forecast_age_ns,
        max_opportunity_lifetime_ns=body.max_opportunity_lifetime_ns,
        max_spread_bps=body.max_spread_bps,
        require_spread_bps=body.require_spread_bps,
        max_predictive_entropy=body.max_predictive_entropy,
        require_uncertainty=body.require_uncertainty,
        allow_ood=body.allow_ood,
        allow_degraded_quality=body.allow_degraded_quality,
        required_capabilities=body.required_capabilities,
        allowed_regimes=body.allowed_regimes,
        require_regime=body.require_regime,
        minimum_net_economic_edge_bps=body.minimum_net_economic_edge_bps,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


__all__ = ["build_opportunity_policy"]
