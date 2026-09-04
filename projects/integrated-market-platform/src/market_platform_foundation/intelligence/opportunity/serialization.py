"""Serialization for BUILD 21 opportunity artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, contract_reference_from_dict, contract_reference_to_dict
from ..evaluation.types import ProbabilityView
from ..promotion.serialization import _scope_from_dict, _scope_to_dict
from ..quality.models import IntelligenceCapability
from .types import (
    OPPORTUNITY_IMPLEMENTATION_VERSION,
    AssessmentAction,
    AssessmentReasonCode,
    EconomicValueStatus,
    OpportunityAssessmentV1,
    OpportunityContext,
    OpportunityPolicyV1,
)


def opportunity_policy_v1_to_dict(policy: OpportunityPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "opportunity_policy_id": policy.opportunity_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
        "allowed_forecast_stages": list(policy.allowed_forecast_stages),
        "allowed_contributor_roles": list(policy.allowed_contributor_roles),
        "probability_view": policy.probability_view.value,
        "reference_probability": policy.reference_probability,
        "minimum_probability_edge": policy.minimum_probability_edge,
        "minimum_probability_edge_strict": policy.minimum_probability_edge_strict,
        "require_calibrated_probability": policy.require_calibrated_probability,
        "max_forecast_age_ns": policy.max_forecast_age_ns,
        "max_opportunity_lifetime_ns": policy.max_opportunity_lifetime_ns,
        "max_spread_bps": policy.max_spread_bps,
        "require_spread_bps": policy.require_spread_bps,
        "max_predictive_entropy": policy.max_predictive_entropy,
        "require_uncertainty": policy.require_uncertainty,
        "allow_ood": policy.allow_ood,
        "allow_degraded_quality": policy.allow_degraded_quality,
        "required_capabilities": [cap.value for cap in policy.required_capabilities],
        "allowed_regimes": list(policy.allowed_regimes),
        "require_regime": policy.require_regime,
        "minimum_net_economic_edge_bps": policy.minimum_net_economic_edge_bps,
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def opportunity_policy_v1_from_dict(payload: dict[str, Any]) -> OpportunityPolicyV1:
    return OpportunityPolicyV1(
        opportunity_policy_id=str(payload["opportunity_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        allowed_forecast_stages=tuple(str(v) for v in payload.get("allowed_forecast_stages", ())),
        allowed_contributor_roles=tuple(str(v) for v in payload.get("allowed_contributor_roles", ())),
        probability_view=ProbabilityView(str(payload.get("probability_view", ProbabilityView.OPERATIONAL.value))),
        reference_probability=float(payload.get("reference_probability", 0.5)),
        minimum_probability_edge=float(payload.get("minimum_probability_edge", 0.0)),
        minimum_probability_edge_strict=bool(payload.get("minimum_probability_edge_strict", False)),
        require_calibrated_probability=bool(payload.get("require_calibrated_probability", False)),
        max_forecast_age_ns=payload.get("max_forecast_age_ns"),
        max_opportunity_lifetime_ns=payload.get("max_opportunity_lifetime_ns"),
        max_spread_bps=payload.get("max_spread_bps"),
        require_spread_bps=bool(payload.get("require_spread_bps", False)),
        max_predictive_entropy=payload.get("max_predictive_entropy"),
        require_uncertainty=bool(payload.get("require_uncertainty", False)),
        allow_ood=bool(payload.get("allow_ood", False)),
        allow_degraded_quality=bool(payload.get("allow_degraded_quality", False)),
        required_capabilities=tuple(
            IntelligenceCapability(str(v)) for v in payload.get("required_capabilities", ())
        ),
        allowed_regimes=tuple(str(v) for v in payload.get("allowed_regimes", ())),
        require_regime=bool(payload.get("require_regime", False)),
        minimum_net_economic_edge_bps=payload.get("minimum_net_economic_edge_bps"),
        implementation_version=str(
            payload.get("implementation_version", OPPORTUNITY_IMPLEMENTATION_VERSION)
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def opportunity_context_to_dict(context: OpportunityContext) -> dict[str, Any]:
    body: dict[str, Any] = {
        "mode": context.mode,
        "scenario_id": context.scenario_id,
        "metadata": dict(context.metadata),
    }
    if context.account_id is not None:
        body["account_id"] = context.account_id
    if context.snapshot_ref is not None:
        body["snapshot_ref"] = contract_reference_to_dict(context.snapshot_ref)
    if context.snapshot_available_time_ns is not None:
        body["snapshot_available_time_ns"] = context.snapshot_available_time_ns
    if context.signal_refs:
        body["signal_refs"] = [contract_reference_to_dict(ref) for ref in context.signal_refs]
    if context.spread_bps is not None:
        body["spread_bps"] = context.spread_bps
    if context.spread_available_time_ns is not None:
        body["spread_available_time_ns"] = context.spread_available_time_ns
    if context.depth_imbalance is not None:
        body["depth_imbalance"] = context.depth_imbalance
    if context.depth_available_time_ns is not None:
        body["depth_available_time_ns"] = context.depth_available_time_ns
    if context.quality_decision is not None:
        body["quality_decision"] = context.quality_decision.to_dict()
    if context.regime is not None:
        body["regime"] = context.regime
    if context.regime_available_time_ns is not None:
        body["regime_available_time_ns"] = context.regime_available_time_ns
    return body


def opportunity_context_from_dict(payload: dict[str, Any]) -> OpportunityContext:
    from ..contracts.common import QualityState
    from ..quality.models import DecisionAction, QualityAssessment, QualityDecision

    quality_decision = None
    if payload.get("quality_decision") is not None:
        qd = payload["quality_decision"]
        quality_decision = QualityDecision(
            action=DecisionAction(str(qd["action"])),
            quality_state=QualityState(str(qd["quality_state"])),
            assessment=QualityAssessment(
                policy_id=qd.get("policy_id", ""),
                policy_version=qd.get("policy_version", ""),
                decision_time_ns=int(qd.get("decision_time_ns", 0)),
            ),
            reasons=tuple(qd.get("reasons", ())),
        )
    snapshot_ref = (
        contract_reference_from_dict(payload["snapshot_ref"]) if payload.get("snapshot_ref") else None
    )
    return OpportunityContext(
        snapshot_ref=snapshot_ref,
        snapshot_available_time_ns=payload.get("snapshot_available_time_ns"),
        signal_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("signal_refs") or [])
        ),
        spread_bps=payload.get("spread_bps"),
        spread_available_time_ns=payload.get("spread_available_time_ns"),
        depth_imbalance=payload.get("depth_imbalance"),
        depth_available_time_ns=payload.get("depth_available_time_ns"),
        quality_decision=quality_decision,
        regime=payload.get("regime"),
        regime_available_time_ns=payload.get("regime_available_time_ns"),
        mode=str(payload.get("mode", "ACTUAL_LIVE")),
        scenario_id=payload.get("scenario_id"),
        account_id=payload.get("account_id"),
        metadata=dict(payload.get("metadata") or {}),
    )


def opportunity_assessment_v1_to_dict(assessment: OpportunityAssessmentV1) -> dict[str, Any]:
    return {
        "schema_version": assessment.schema_version,
        "assessment_id": assessment.assessment_id,
        "forecast_id": assessment.forecast_id,
        "champion_assignment_id": assessment.champion_assignment_id,
        "opportunity_policy_id": assessment.opportunity_policy_id,
        "opportunity_decision_time_ns": assessment.opportunity_decision_time_ns,
        "forecast_decision_time_ns": assessment.forecast_decision_time_ns,
        "probability_view": assessment.probability_view.value,
        "probability": assessment.probability,
        "reference_probability": assessment.reference_probability,
        "probability_edge": assessment.probability_edge,
        "side": assessment.side,
        "quality_action": assessment.quality_action,
        "uncertainty_entropy": assessment.uncertainty_entropy,
        "spread_bps": assessment.spread_bps,
        "economic_value_status": assessment.economic_value_status.value,
        "expected_gross_move_bps": assessment.expected_gross_move_bps,
        "estimated_friction_bps": assessment.estimated_friction_bps,
        "expected_net_edge_bps": assessment.expected_net_edge_bps,
        "regime": assessment.regime,
        "assessment_action": assessment.assessment_action.value,
        "reason_codes": [code.value for code in assessment.reason_codes],
        "opportunity_id": assessment.opportunity_id,
        "expires_at_ns": assessment.expires_at_ns,
        "context_refs": [contract_reference_to_dict(ref) for ref in assessment.context_refs],
        "lineage_refs": [contract_reference_to_dict(ref) for ref in assessment.lineage_refs],
        "implementation_version": assessment.implementation_version,
        "metadata": dict(assessment.metadata),
    }


def opportunity_assessment_v1_from_dict(payload: dict[str, Any]) -> OpportunityAssessmentV1:
    return OpportunityAssessmentV1(
        assessment_id=str(payload["assessment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        forecast_id=str(payload["forecast_id"]),
        champion_assignment_id=str(payload["champion_assignment_id"]),
        opportunity_policy_id=str(payload["opportunity_policy_id"]),
        opportunity_decision_time_ns=int(payload["opportunity_decision_time_ns"]),
        forecast_decision_time_ns=int(payload["forecast_decision_time_ns"]),
        probability_view=ProbabilityView(str(payload["probability_view"])),
        probability=payload.get("probability"),
        reference_probability=float(payload.get("reference_probability", 0.5)),
        probability_edge=payload.get("probability_edge"),
        side=payload.get("side"),
        quality_action=payload.get("quality_action"),
        uncertainty_entropy=payload.get("uncertainty_entropy"),
        spread_bps=payload.get("spread_bps"),
        economic_value_status=EconomicValueStatus(
            str(payload.get("economic_value_status", EconomicValueStatus.UNAVAILABLE.value))
        ),
        expected_gross_move_bps=payload.get("expected_gross_move_bps"),
        estimated_friction_bps=payload.get("estimated_friction_bps"),
        expected_net_edge_bps=payload.get("expected_net_edge_bps"),
        regime=payload.get("regime"),
        assessment_action=AssessmentAction(str(payload["assessment_action"])),
        reason_codes=tuple(
            AssessmentReasonCode(str(v)) for v in payload.get("reason_codes", ())
        ),
        opportunity_id=payload.get("opportunity_id"),
        expires_at_ns=payload.get("expires_at_ns"),
        context_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("context_refs") or [])
        ),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "opportunity_assessment_v1_from_dict",
    "opportunity_assessment_v1_to_dict",
    "opportunity_context_from_dict",
    "opportunity_context_to_dict",
    "opportunity_policy_v1_from_dict",
    "opportunity_policy_v1_to_dict",
]
