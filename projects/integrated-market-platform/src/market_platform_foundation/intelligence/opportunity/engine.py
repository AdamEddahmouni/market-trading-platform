"""Governed opportunity engine (BUILD 21)."""

from __future__ import annotations

import math

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
    OpportunitySide,
    QualitySummary,
)
from ..contracts.forecast import ForecastV1
from ..contracts.opportunity import OpportunityV1
from ..evaluation.provenance import probability_for_view
from ..evaluation.types import forecast_role, ProbabilityView
from ..fusion.types import ForecastContributorRole
from ..promotion.types import ChampionAssignmentV1
from ..quality.models import DecisionAction
from .context import context_refs, validate_context_pit
from .economics import (
    assess_economic_value,
    extract_ood_reasons,
    extract_predictive_entropy,
    meets_edge_threshold,
    probability_edge_for_side,
    side_from_probability,
)
from .errors import OpportunityError
from .identity import derive_opportunity_assessment_id, derive_opportunity_id
from ..governance.types import RuntimeGovernanceState
from .types import (
    AssessmentAction,
    AssessmentReasonCode,
    EconomicValueStatus,
    OpportunityAssessmentResult,
    OpportunityAssessmentV1,
    OpportunityContext,
    OpportunityPolicyV1,
)


def forecast_expiry_ns(forecast: ForecastV1) -> int:
    if forecast.resolve_time_ns is not None:
        return forecast.resolve_time_ns
    return forecast.decision_time_ns + forecast.horizon.duration_ns


def forecast_matches_champion(forecast: ForecastV1, assignment: ChampionAssignmentV1) -> bool:
    scope = assignment.champion_scope
    if forecast.target.target_kind != scope.target_kind:
        return False
    if forecast.horizon.duration_ns != scope.horizon_ns:
        return False
    meta_candidate = forecast.metadata.get("champion_candidate_id") or forecast.metadata.get("candidate_id")
    meta_hash = forecast.metadata.get("candidate_artifact_hash")
    if meta_candidate is not None and meta_candidate != assignment.candidate_id:
        return False
    if meta_hash is not None and meta_hash != assignment.candidate_artifact_hash:
        return False
    if meta_candidate is None and meta_hash is None:
        return False
    return True


class OpportunityEngine:
    """Deterministic champion-governed opportunity assessment."""

    def assess(
        self,
        *,
        forecast: ForecastV1,
        policy: OpportunityPolicyV1,
        context: OpportunityContext,
        champion_at_forecast: ChampionAssignmentV1,
        champion_at_opportunity: ChampionAssignmentV1,
        opportunity_decision_time_ns: int,
        runtime_governance: RuntimeGovernanceState | None = None,
    ) -> OpportunityAssessmentResult:
        reason_codes: list[AssessmentReasonCode] = []
        action = AssessmentAction.EMIT

        if runtime_governance is not None and not runtime_governance.opportunities_allowed:
            return self._finalize(
                forecast=forecast,
                policy=policy,
                context=context,
                champion_assignment=champion_at_opportunity,
                opportunity_decision_time_ns=opportunity_decision_time_ns,
                action=AssessmentAction.FAIL_CLOSED,
                reason_codes=[AssessmentReasonCode.RUNTIME_GOVERNANCE_DISABLED],
                probability=None,
                probability_edge=None,
                side=None,
                quality_action=None,
                uncertainty_entropy=None,
                spread_bps=None,
                economic_status=EconomicValueStatus.UNAVAILABLE,
                expires_at_ns=None,
            )

        if opportunity_decision_time_ns < forecast.decision_time_ns:
            return self._finalize(
                forecast=forecast,
                policy=policy,
                context=context,
                champion_assignment=champion_at_opportunity,
                opportunity_decision_time_ns=opportunity_decision_time_ns,
                action=AssessmentAction.FAIL_CLOSED,
                reason_codes=[AssessmentReasonCode.OPPORTUNITY_TIME_BEFORE_FORECAST],
                probability=None,
                probability_edge=None,
                side=None,
                quality_action=None,
                uncertainty_entropy=None,
                spread_bps=None,
                economic_status=EconomicValueStatus.UNAVAILABLE,
                expires_at_ns=None,
            )

        try:
            validate_context_pit(context, opportunity_decision_time_ns=opportunity_decision_time_ns)
        except OpportunityError:
            return self._finalize(
                forecast=forecast,
                policy=policy,
                context=context,
                champion_assignment=champion_at_opportunity,
                opportunity_decision_time_ns=opportunity_decision_time_ns,
                action=AssessmentAction.FAIL_CLOSED,
                reason_codes=[AssessmentReasonCode.TEMPORAL_INTEGRITY_VIOLATION],
                probability=None,
                probability_edge=None,
                side=None,
                quality_action=None,
                uncertainty_entropy=None,
                spread_bps=None,
                economic_status=EconomicValueStatus.UNAVAILABLE,
                expires_at_ns=None,
            )

        if champion_at_forecast.effective_from_ns > forecast.decision_time_ns:
            reason_codes.append(AssessmentReasonCode.CHAMPION_NOT_EFFECTIVE)
            action = AssessmentAction.SUPPRESS

        if champion_at_forecast.assignment_id != champion_at_opportunity.assignment_id:
            reason_codes.append(AssessmentReasonCode.CHAMPION_CHANGED_SINCE_FORECAST)
            action = AssessmentAction.SUPPRESS

        if not forecast_matches_champion(forecast, champion_at_forecast):
            reason_codes.append(AssessmentReasonCode.FORECAST_NOT_FROM_GOVERNED_CHAMPION)
            action = AssessmentAction.SUPPRESS

        role = forecast_role(forecast)
        if role not in policy.allowed_contributor_roles:
            reason_codes.append(AssessmentReasonCode.FORECAST_ROLE_NOT_ALLOWED)
            action = AssessmentAction.SUPPRESS
        if role == ForecastContributorRole.CONTROL.value:
            reason_codes.append(AssessmentReasonCode.FORECAST_ROLE_NOT_ALLOWED)
            action = AssessmentAction.SUPPRESS

        stage = str(forecast.metadata.get("forecast_stage", ""))
        if stage and stage not in policy.allowed_forecast_stages:
            reason_codes.append(AssessmentReasonCode.FORECAST_STAGE_NOT_ALLOWED)
            action = AssessmentAction.SUPPRESS

        expiry_ns = forecast_expiry_ns(forecast)
        if opportunity_decision_time_ns >= expiry_ns:
            reason_codes.append(AssessmentReasonCode.FORECAST_EXPIRED)
            action = AssessmentAction.SUPPRESS

        if policy.max_forecast_age_ns is not None:
            age_ns = opportunity_decision_time_ns - forecast.decision_time_ns
            if age_ns > policy.max_forecast_age_ns:
                reason_codes.append(AssessmentReasonCode.FORECAST_TOO_OLD)
                action = AssessmentAction.SUPPRESS
            elif age_ns == policy.max_forecast_age_ns and action == AssessmentAction.EMIT:
                pass

        quality_action: str | None = None
        if context.quality_decision is not None:
            quality_action = context.quality_decision.action.value
            if context.quality_decision.action == DecisionAction.FAIL_CLOSED:
                reason_codes.append(AssessmentReasonCode.QUALITY_FAIL_CLOSED)
                action = AssessmentAction.FAIL_CLOSED
            elif context.quality_decision.action == DecisionAction.ABSTAIN:
                reason_codes.append(AssessmentReasonCode.QUALITY_ABSTAIN)
                action = AssessmentAction.ABSTAIN
            elif context.quality_decision.action == DecisionAction.DEGRADE and not policy.allow_degraded_quality:
                reason_codes.append(AssessmentReasonCode.QUALITY_DEGRADED_NOT_ALLOWED)
                action = AssessmentAction.SUPPRESS

        if policy.required_capabilities:
            missing = set(policy.required_capabilities)
            if context.quality_decision is not None:
                satisfied = set(context.quality_decision.satisfied_requirements)
                missing -= satisfied
            if missing:
                reason_codes.append(AssessmentReasonCode.CAPABILITY_REQUIRED_MISSING)
                action = AssessmentAction.SUPPRESS

        probability: float | None = None
        try:
            probability = probability_for_view(forecast, policy.probability_view)
        except Exception:
            probability = None

        if probability is None:
            if policy.probability_view == ProbabilityView.CALIBRATED or policy.require_calibrated_probability:
                reason_codes.append(AssessmentReasonCode.CALIBRATED_PROBABILITY_UNAVAILABLE)
            else:
                reason_codes.append(AssessmentReasonCode.PROBABILITY_UNAVAILABLE)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action
        elif not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
            reason_codes.append(AssessmentReasonCode.INVALID_PROBABILITY)
            action = AssessmentAction.FAIL_CLOSED
            probability = None

        if policy.require_calibrated_probability and forecast.estimate.calibrated_probability is None:
            reason_codes.append(AssessmentReasonCode.CALIBRATED_PROBABILITY_UNAVAILABLE)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action

        side: OpportunitySide | None = None
        probability_edge: float | None = None
        if probability is not None and action == AssessmentAction.EMIT:
            side = side_from_probability(probability)
            if side == OpportunitySide.NEUTRAL:
                reason_codes.append(AssessmentReasonCode.FORECAST_ABSTAINED)
                action = AssessmentAction.SUPPRESS
            else:
                probability_edge = probability_edge_for_side(
                    probability,
                    side,
                    reference=policy.reference_probability,
                )
                if not meets_edge_threshold(
                    probability_edge,
                    minimum=policy.minimum_probability_edge,
                    strict=policy.minimum_probability_edge_strict,
                ):
                    reason_codes.append(AssessmentReasonCode.PROBABILITY_EDGE_TOO_SMALL)
                    action = AssessmentAction.SUPPRESS

        uncertainty_entropy = extract_predictive_entropy(forecast)
        if policy.require_uncertainty and uncertainty_entropy is None:
            reason_codes.append(AssessmentReasonCode.UNCERTAINTY_UNAVAILABLE)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action
        if uncertainty_entropy is not None and policy.max_predictive_entropy is not None:
            if uncertainty_entropy > policy.max_predictive_entropy:
                reason_codes.append(AssessmentReasonCode.UNCERTAINTY_TOO_HIGH)
                action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action
            elif (
                uncertainty_entropy == policy.max_predictive_entropy
                and action == AssessmentAction.EMIT
            ):
                reason_codes.append(AssessmentReasonCode.UNCERTAINTY_TOO_HIGH)
                action = AssessmentAction.SUPPRESS

        ood_reasons = extract_ood_reasons(forecast)
        if ood_reasons and not policy.allow_ood:
            reason_codes.append(AssessmentReasonCode.OOD_NOT_ALLOWED)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action

        spread_bps = context.spread_bps
        if spread_bps is not None:
            if not math.isfinite(spread_bps) or spread_bps < 0.0:
                reason_codes.append(AssessmentReasonCode.SPREAD_INVALID)
                action = AssessmentAction.FAIL_CLOSED
            elif policy.max_spread_bps is not None and spread_bps > policy.max_spread_bps:
                reason_codes.append(AssessmentReasonCode.SPREAD_TOO_WIDE)
                action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action
            elif spread_bps == policy.max_spread_bps and action == AssessmentAction.EMIT:
                reason_codes.append(AssessmentReasonCode.SPREAD_TOO_WIDE)
                action = AssessmentAction.SUPPRESS
        elif policy.require_spread_bps:
            reason_codes.append(AssessmentReasonCode.LIQUIDITY_CONTEXT_UNAVAILABLE)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action

        regime = context.regime
        if policy.require_regime and regime is None:
            reason_codes.append(AssessmentReasonCode.REGIME_CONTEXT_UNAVAILABLE)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action
        if regime is not None and policy.allowed_regimes and regime not in policy.allowed_regimes:
            reason_codes.append(AssessmentReasonCode.REGIME_NOT_ALLOWED)
            action = AssessmentAction.SUPPRESS if action == AssessmentAction.EMIT else action

        economic_status, gross_bps, friction_bps, net_bps = assess_economic_value(
            forecast,
            spread_bps=spread_bps,
        )
        if action == AssessmentAction.EMIT and economic_status == EconomicValueStatus.UNAVAILABLE_DIRECTION_ONLY:
            economic_status = EconomicValueStatus.UNAVAILABLE_DIRECTION_ONLY
        if policy.minimum_net_economic_edge_bps is not None and action == AssessmentAction.EMIT:
            if net_bps is None:
                reason_codes.append(AssessmentReasonCode.ECONOMIC_VALUE_UNAVAILABLE)
                action = AssessmentAction.SUPPRESS
            elif net_bps < policy.minimum_net_economic_edge_bps:
                reason_codes.append(AssessmentReasonCode.ECONOMIC_HURDLE_NOT_MET)
                action = AssessmentAction.SUPPRESS

        expires_at_ns = self._compute_expiry(
            forecast_expiry_ns=expiry_ns,
            opportunity_decision_time_ns=opportunity_decision_time_ns,
            policy=policy,
        )

        if action == AssessmentAction.EMIT:
            reason_codes.append(AssessmentReasonCode.OPPORTUNITY_EMITTED)

        return self._finalize(
            forecast=forecast,
            policy=policy,
            context=context,
            champion_assignment=champion_at_opportunity,
            opportunity_decision_time_ns=opportunity_decision_time_ns,
            action=action,
            reason_codes=reason_codes,
            probability=probability,
            probability_edge=probability_edge,
            side=side.value if side is not None else None,
            quality_action=quality_action,
            uncertainty_entropy=uncertainty_entropy,
            spread_bps=spread_bps,
            economic_status=economic_status,
            expected_gross_move_bps=gross_bps,
            estimated_friction_bps=friction_bps,
            expected_net_edge_bps=net_bps,
            regime=regime,
            expires_at_ns=expires_at_ns,
        )

    def _compute_expiry(
        self,
        *,
        forecast_expiry_ns: int,
        opportunity_decision_time_ns: int,
        policy: OpportunityPolicyV1,
    ) -> int:
        candidates = [forecast_expiry_ns]
        if policy.max_opportunity_lifetime_ns is not None:
            candidates.append(opportunity_decision_time_ns + policy.max_opportunity_lifetime_ns)
        return min(candidates)

    def _finalize(
        self,
        *,
        forecast: ForecastV1,
        policy: OpportunityPolicyV1,
        context: OpportunityContext,
        champion_assignment: ChampionAssignmentV1,
        opportunity_decision_time_ns: int,
        action: AssessmentAction,
        reason_codes: list[AssessmentReasonCode],
        probability: float | None,
        probability_edge: float | None,
        side: str | None,
        quality_action: str | None,
        uncertainty_entropy: float | None,
        spread_bps: float | None,
        economic_status: EconomicValueStatus,
        expires_at_ns: int | None,
        expected_gross_move_bps: float | None = None,
        estimated_friction_bps: float | None = None,
        expected_net_edge_bps: float | None = None,
        regime: str | None = None,
    ) -> OpportunityAssessmentResult:
        assessment_id = derive_opportunity_assessment_id(
            forecast_id=forecast.forecast_id,
            champion_assignment_id=champion_assignment.assignment_id,
            opportunity_policy_id=policy.opportunity_policy_id,
            opportunity_decision_time_ns=opportunity_decision_time_ns,
            context=context,
        )
        lineage_refs = (
            ContractReference(kind=ContractKind.FORECAST.value, id=forecast.forecast_id),
            ContractReference(
                kind="champion_assignment",
                id=champion_assignment.assignment_id,
            ),
            ContractReference(kind="opportunity_policy", id=policy.opportunity_policy_id),
        )
        opportunity: OpportunityV1 | None = None
        opportunity_id: str | None = None
        if action == AssessmentAction.EMIT and side is not None and expires_at_ns is not None:
            opportunity_id = derive_opportunity_id(
                assessment_id=assessment_id,
                forecast_id=forecast.forecast_id,
                opportunity_policy_id=policy.opportunity_policy_id,
                champion_assignment_id=champion_assignment.assignment_id,
            )
            opportunity = OpportunityV1(
                opportunity_id=opportunity_id,
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                scope=forecast.scope,
                created_at_ns=opportunity_decision_time_ns,
                quality=forecast.quality,
                side=OpportunitySide(side),
                valid_until_ns=expires_at_ns,
                source_forecast_refs=(
                    ContractReference(kind=ContractKind.FORECAST.value, id=forecast.forecast_id),
                ),
                expected_return=None,
                expected_net_edge=None,
                uncertainty=dict(forecast.uncertainty),
                reason_summary=AssessmentReasonCode.OPPORTUNITY_EMITTED.value,
                lineage_refs=lineage_refs + (
                    ContractReference(kind="opportunity_assessment", id=assessment_id),
                ),
                metadata={
                    "probability_view": policy.probability_view.value,
                    "probability": probability,
                    "reference_probability": policy.reference_probability,
                    "probability_edge": probability_edge,
                    "economic_value_status": economic_status.value,
                    "champion_assignment_id": champion_assignment.assignment_id,
                    "assessment_id": assessment_id,
                    "spread_bps": spread_bps,
                    "depth_imbalance": context.depth_imbalance,
                },
            )

        assessment = OpportunityAssessmentV1(
            assessment_id=assessment_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            forecast_id=forecast.forecast_id,
            champion_assignment_id=champion_assignment.assignment_id,
            opportunity_policy_id=policy.opportunity_policy_id,
            opportunity_decision_time_ns=opportunity_decision_time_ns,
            forecast_decision_time_ns=forecast.decision_time_ns,
            probability_view=policy.probability_view,
            probability=probability,
            reference_probability=policy.reference_probability,
            probability_edge=probability_edge,
            side=side,
            quality_action=quality_action,
            uncertainty_entropy=uncertainty_entropy,
            spread_bps=spread_bps,
            economic_value_status=economic_status,
            expected_gross_move_bps=expected_gross_move_bps,
            estimated_friction_bps=estimated_friction_bps,
            expected_net_edge_bps=expected_net_edge_bps,
            regime=regime,
            assessment_action=action,
            reason_codes=tuple(reason_codes),
            opportunity_id=opportunity_id,
            expires_at_ns=expires_at_ns,
            context_refs=context_refs(context),
            lineage_refs=lineage_refs,
            metadata={
                "mode": context.mode,
                "scenario_id": context.scenario_id,
                "depth_imbalance": context.depth_imbalance,
            },
        )
        return OpportunityAssessmentResult(assessment=assessment, opportunity=opportunity)


__all__ = [
    "OpportunityEngine",
    "forecast_expiry_ns",
    "forecast_matches_champion",
]
