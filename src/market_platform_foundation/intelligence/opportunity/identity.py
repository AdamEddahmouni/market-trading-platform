"""Deterministic opportunity identities (BUILD 21)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.common import ContractReference, contract_reference_to_dict
from ..promotion.identity import champion_scope_identity_payload
from .types import OpportunityContext, OpportunityPolicyV1


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def _ref_identity_payload(ref: ContractReference) -> dict[str, Any]:
    return contract_reference_to_dict(ref)


def context_identity_payload(context: OpportunityContext) -> dict[str, Any]:
    signal_refs = sorted(
        [_ref_identity_payload(ref) for ref in context.signal_refs],
        key=lambda item: (item["kind"], item["id"]),
    )
    body: dict[str, Any] = {
        "snapshot_ref": _ref_identity_payload(context.snapshot_ref) if context.snapshot_ref else None,
        "snapshot_available_time_ns": context.snapshot_available_time_ns,
        "signal_refs": signal_refs,
        "spread_bps": context.spread_bps,
        "spread_available_time_ns": context.spread_available_time_ns,
        "depth_imbalance": context.depth_imbalance,
        "depth_available_time_ns": context.depth_available_time_ns,
        "quality_decision": context.quality_decision.to_dict() if context.quality_decision else None,
        "regime": context.regime,
        "regime_available_time_ns": context.regime_available_time_ns,
        "mode": context.mode,
        "scenario_id": context.scenario_id,
    }
    return body


def opportunity_policy_identity_payload(policy: OpportunityPolicyV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
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
    }


def derive_opportunity_policy_id(policy: OpportunityPolicyV1) -> str:
    return _sha256_prefix("OPPOL", opportunity_policy_identity_payload(policy))


def derive_opportunity_assessment_id(
    *,
    forecast_id: str,
    champion_assignment_id: str,
    opportunity_policy_id: str,
    opportunity_decision_time_ns: int,
    context: OpportunityContext,
) -> str:
    payload = {
        "forecast_id": forecast_id,
        "champion_assignment_id": champion_assignment_id,
        "opportunity_policy_id": opportunity_policy_id,
        "opportunity_decision_time_ns": opportunity_decision_time_ns,
        "context": context_identity_payload(context),
    }
    return _sha256_prefix("OPASS", payload)


def derive_opportunity_id(
    *,
    assessment_id: str,
    forecast_id: str,
    opportunity_policy_id: str,
    champion_assignment_id: str,
) -> str:
    payload = {
        "assessment_id": assessment_id,
        "forecast_id": forecast_id,
        "opportunity_policy_id": opportunity_policy_id,
        "champion_assignment_id": champion_assignment_id,
    }
    return _sha256_prefix("OPP", payload)


__all__ = [
    "context_identity_payload",
    "derive_opportunity_assessment_id",
    "derive_opportunity_id",
    "derive_opportunity_policy_id",
    "opportunity_policy_identity_payload",
]
