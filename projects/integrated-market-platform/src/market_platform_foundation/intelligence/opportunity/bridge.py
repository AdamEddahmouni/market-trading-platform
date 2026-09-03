"""Canonical StrategyMatch → governed OpportunityEngine bridge."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..contracts.common import ContractKind, ContractReference
from ..contracts.forecast import ForecastV1
from ..contracts.strategy_match import StrategyMatch, StrategyMatchDisposition
from ..promotion.types import ChampionAssignmentV1
from ..persistence.repository import IntelligenceRepository
from .engine import OpportunityEngine
from .types import (
    OpportunityAssessmentResult,
    OpportunityAssessmentV1,
    OpportunityContext,
    OpportunityPolicyV1,
)
from .economic_assessment import UniversalEconomicAssessmentV1


class OpportunityBridgeError(ValueError):
    """A canonical bridge precondition failed."""


@dataclass(frozen=True, slots=True)
class OpportunityBridgeResult:
    """Existing governed outputs enriched with optional economic lineage."""

    assessment: OpportunityAssessmentV1
    opportunity: Any
    economic_assessment: UniversalEconomicAssessmentV1 | None
    economic_assessment_ref: ContractReference | None

    @property
    def sidecar_ref(self) -> ContractReference | None:
        return self.economic_assessment_ref


def _mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE", "PAPER": "PAPER"}.get(normalized, normalized)


def _scope_matches(left: Any, right: Any) -> bool:
    return (
        left.component == right.component
        and left.target_kind == right.target_kind
        and left.horizon_ns == right.horizon_ns
        and _mode(left.mode) == _mode(right.mode)
        and left.scenario_id == right.scenario_id
    )


def _context_account(context: OpportunityContext) -> str | None:
    if getattr(context, "account_id", None):
        return str(context.account_id)
    value = context.metadata.get("account_id") if hasattr(context.metadata, "get") else None
    return str(value) if value is not None else None


def _context_mode(context: OpportunityContext) -> str:
    return _mode(context.mode)


def _validate_inputs(
    *,
    match: StrategyMatch,
    forecast: ForecastV1,
    champion_at_forecast: ChampionAssignmentV1,
    champion_at_opportunity: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
    context: OpportunityContext,
    economic_assessment: UniversalEconomicAssessmentV1 | None,
    opportunity_decision_time_ns: int,
) -> None:
    if match.disposition != StrategyMatchDisposition.MATCHED:
        raise OpportunityBridgeError("STRATEGY_MATCH_NOT_MATCHED")
    forecast_refs = tuple(
        ref for ref in match.source_forecast_refs if ref.kind == ContractKind.FORECAST.value
    )
    if len(forecast_refs) != 1 or forecast_refs[0].id != forecast.forecast_id:
        raise OpportunityBridgeError("FORECAST_REFERENCE_MISMATCH")
    if match.scope.instrument_ids != forecast.scope.instrument_ids:
        raise OpportunityBridgeError("MATCH_FORECAST_SCOPE_MISMATCH")
    if (
        match.scope.context_id is not None
        and forecast.scope.context_id is not None
        and match.scope.context_id != forecast.scope.context_id
    ):
        raise OpportunityBridgeError("MATCH_FORECAST_CONTEXT_SCOPE_MISMATCH")
    if not _scope_matches(policy.champion_scope, champion_at_forecast.champion_scope):
        raise OpportunityBridgeError("POLICY_CHAMPION_SCOPE_MISMATCH")
    if not _scope_matches(champion_at_forecast.champion_scope, champion_at_opportunity.champion_scope):
        raise OpportunityBridgeError("CHAMPION_SCOPE_MISMATCH")
    if _mode(policy.champion_scope.mode) != _context_mode(context):
        raise OpportunityBridgeError("CONTEXT_MODE_SCOPE_MISMATCH")
    if opportunity_decision_time_ns < match.decision_time_ns:
        raise OpportunityBridgeError("OPPORTUNITY_TIME_BEFORE_MATCH")
    if opportunity_decision_time_ns < forecast.decision_time_ns:
        raise OpportunityBridgeError("OPPORTUNITY_TIME_BEFORE_FORECAST")
    match_mode = match.context.get("mode") if hasattr(match.context, "get") else None
    if match_mode is None or _mode(str(match_mode)) != _context_mode(context):
        raise OpportunityBridgeError("MATCH_MODE_SCOPE_MISMATCH")
    match_account = match.context.get("account_id") if hasattr(match.context, "get") else None
    context_account = _context_account(context)
    if match_account is None or context_account is None or str(match_account) != context_account:
        if economic_assessment is None or match_account is None:
            raise OpportunityBridgeError("ACCOUNT_SCOPE_MISMATCH")
        context_account = economic_assessment.account_id
        if str(match_account) != context_account:
            raise OpportunityBridgeError("ACCOUNT_SCOPE_MISMATCH")
    if economic_assessment is not None:
        if economic_assessment.scope != forecast.scope:
            raise OpportunityBridgeError("ECONOMIC_SCOPE_MISMATCH")
        if str(economic_assessment.account_id) != str(match_account):
            raise OpportunityBridgeError("ECONOMIC_ACCOUNT_SCOPE_MISMATCH")
        if _mode(economic_assessment.mode) != _context_mode(context):
            raise OpportunityBridgeError("ECONOMIC_MODE_SCOPE_MISMATCH")
        if economic_assessment.assessed_at_ns > opportunity_decision_time_ns:
            raise OpportunityBridgeError("ECONOMIC_ASSESSMENT_AFTER_DECISION")
        if (
            economic_assessment.expires_at_ns is not None
            and opportunity_decision_time_ns >= economic_assessment.expires_at_ns
        ):
            raise OpportunityBridgeError("ECONOMIC_ASSESSMENT_EXPIRED")


def _append_ref(refs: tuple[ContractReference, ...], ref: ContractReference) -> tuple[ContractReference, ...]:
    if ref in refs:
        return refs
    return refs + (ref,)


def bridge_strategy_match_to_opportunity(
    *,
    match: StrategyMatch,
    forecast: ForecastV1,
    champion_at_forecast: ChampionAssignmentV1,
    champion_at_opportunity: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
    context: OpportunityContext,
    opportunity_decision_time_ns: int,
    economic_assessment: UniversalEconomicAssessmentV1 | None = None,
    repository: IntelligenceRepository | None = None,
    engine: OpportunityEngine | None = None,
) -> OpportunityBridgeResult:
    """Validate lineage/scope, call OpportunityEngine once, and persist outputs."""
    _validate_inputs(
        match=match,
        forecast=forecast,
        champion_at_forecast=champion_at_forecast,
        champion_at_opportunity=champion_at_opportunity,
        policy=policy,
        context=context,
        economic_assessment=economic_assessment,
        opportunity_decision_time_ns=opportunity_decision_time_ns,
    )
    result = (engine or OpportunityEngine()).assess(
        forecast=forecast,
        policy=policy,
        context=context,
        champion_at_forecast=champion_at_forecast,
        champion_at_opportunity=champion_at_opportunity,
        opportunity_decision_time_ns=opportunity_decision_time_ns,
    )
    sidecar_ref = None
    assessment = result.assessment
    opportunity = result.opportunity
    match_ref = ContractReference(kind="strategy_match", id=match.match_id)
    assessment = replace(
        assessment,
        lineage_refs=_append_ref(assessment.lineage_refs, match_ref),
        metadata={**assessment.metadata, "strategy_match_ref": match.match_id},
    )
    if opportunity is not None:
        opportunity = replace(
            opportunity,
            lineage_refs=_append_ref(opportunity.lineage_refs, match_ref),
            metadata={**opportunity.metadata, "strategy_match_ref": match.match_id},
        )
    if economic_assessment is not None:
        sidecar_ref = ContractReference(
            kind="universal_economic_assessment",
            id=economic_assessment.assessment_id,
        )
        assessment = replace(
            assessment,
            lineage_refs=_append_ref(assessment.lineage_refs, sidecar_ref),
            metadata={**assessment.metadata, "economic_assessment_ref": sidecar_ref.id},
        )
        if opportunity is not None:
            opportunity = replace(
                opportunity,
                lineage_refs=_append_ref(opportunity.lineage_refs, sidecar_ref),
                metadata={**opportunity.metadata, "economic_assessment_ref": sidecar_ref.id},
            )
    if repository is not None:
        if economic_assessment is not None:
            repository.put_economic_assessment(economic_assessment)
        repository.put_opportunity_assessment(assessment)
        if opportunity is not None:
            repository.put_opportunity(opportunity)
    return OpportunityBridgeResult(
        assessment=assessment,
        opportunity=opportunity,
        economic_assessment=economic_assessment,
        economic_assessment_ref=sidecar_ref,
    )


canonical_strategy_match_opportunity_bridge = bridge_strategy_match_to_opportunity

__all__ = [
    "OpportunityBridgeError",
    "OpportunityBridgeResult",
    "bridge_strategy_match_to_opportunity",
    "canonical_strategy_match_opportunity_bridge",
]
