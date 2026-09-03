"""Golden BUILD 01–24 lifecycle runner (BUILD 25)."""

from __future__ import annotations

import os
from typing import Any

from ..adaptation import AdaptationAction, AdaptationService
from ..governance import ActivationEngine, FailSafeEngine, resolve_governance_state
from ..opportunity import AssessmentAction, OpportunityEngine
from ..promotion import PromotionEngine, StatisticalRequirementKind, build_promotion_policy
from ..research_experiments.types import ResearchFindingType
from ..validation import ValidationDisposition, ValidationEngine, ValidationRunContext, build_validation_plan, statistical_candidate_profile
from .types import GoldenLifecycleArtifacts
from tests.intelligence.adaptation_fixtures import default_adaptation_policy, default_context, recurrence_bundle
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_quote
from tests.intelligence.governance_fixtures import default_activation_policy, default_fail_safe_policy
from tests.intelligence.opportunity_fixtures import champion_forecast, default_opportunity_context, default_opportunity_policy
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE
from tests.intelligence.test_validation_temporal_firewall import _holdout_examples, _manifest_with_holdout, _trained_candidate
from market_platform_foundation.intelligence.execution import PreTradeRiskEngine, RiskDecisionKind
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository


def run_golden_lifecycle(*, paper_execution: bool = False) -> tuple[GoldenLifecycleArtifacts, dict[str, Any]]:
    """Execute canonical BUILD 15–24 governed path using deterministic fixtures."""
    if paper_execution:
        os.environ["IMP_PAPER_EXECUTION"] = "1"

    repo = InMemoryIntelligenceRepository()
    promotion_engine = PromotionEngine()

    manifest = _manifest_with_holdout(T + 8)
    candidate, dataset_manifest, artifact_bytes = _trained_candidate(repo, manifest)
    plan = build_validation_plan(
        manifest,
        (candidate,),
        control_ref="baseline_control",
        fold_boundaries_ns=(T, T + 4, T + 8),
        minimum_paired_sample=3,
    )
    report = ValidationEngine(repo).validate(
        ValidationRunContext(
            plan=plan,
            experiment=manifest,
            candidates=(candidate,),
            training_dataset=dataset_manifest,
            holdout_examples=_holdout_examples(candidate_better=True),
            fold_examples={},
            knowledge_profiles={candidate.candidate_id: statistical_candidate_profile(candidate.candidate_id)},
            artifact_bytes_by_candidate={candidate.candidate_id: artifact_bytes},
            guardrail_thresholds={},
        )
    )
    if report.final_disposition != ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA:
        raise RuntimeError("golden lifecycle validation inconclusive in fixture environment")

    promotion_policy = build_promotion_policy(
        champion_scope=DEFAULT_SCOPE,
        required_improvement=0.001,
        minimum_holdout_samples=4,
        statistical_requirement=StatisticalRequirementKind.NONE,
    )
    repo.put_promotion_policy(promotion_policy)
    champion = promotion_engine.bootstrap_champion(
        champion_scope=DEFAULT_SCOPE,
        candidate=candidate,
        effective_from_ns=T,
    )
    repo.put_champion_assignment(champion)

    activation_policy = default_activation_policy()
    repo.put_runtime_activation_policy(activation_policy)
    activation = ActivationEngine().create_activation(
        policy=activation_policy,
        champion_assignment=champion,
        effective_from_ns=T,
        artifact_bytes=artifact_bytes,
    )
    repo.put_runtime_activation(activation)

    fail_safe = FailSafeEngine().evaluate(
        policy=default_fail_safe_policy(),
        decision_time_ns=T + 1,
        activation=activation,
        runtime_consistent=True,
        runtime_reasons=(),
    )
    repo.put_fail_safe_decision(fail_safe)
    governance_state = resolve_governance_state(
        activation=activation,
        fail_safe_decision=fail_safe,
        latest_champion_assignment_id=champion.assignment_id,
    )
    if not governance_state.opportunities_allowed:
        raise RuntimeError("governance state blocked opportunities in golden lifecycle")

    forecast = champion_forecast(champion)
    repo.put_forecast(forecast)
    opp_time = T + 2_000_000_000
    opp_result = OpportunityEngine().assess(
        forecast=forecast,
        policy=default_opportunity_policy(),
        context=default_opportunity_context(decision_time_ns=opp_time),
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_decision_time_ns=opp_time,
        runtime_governance=governance_state,
    )
    if opp_result.assessment.assessment_action != AssessmentAction.EMIT or opp_result.opportunity is None:
        raise RuntimeError("golden lifecycle did not emit governed opportunity")

    risk_engine = PreTradeRiskEngine()
    proposal = risk_engine.build_proposal(
        opportunity=opp_result.opportunity,
        policy=default_execution_policy(),
        portfolio=flat_portfolio(captured_at_ns=opp_time),
        quote=sample_quote(available_time_ns=opp_time),
        proposal_time_ns=opp_time,
        instrument_id="inst-biya",
        symbol="BIYA",
    )
    risk = risk_engine.assess(
        proposal=proposal,
        opportunity=opp_result.opportunity,
        policy=default_execution_policy(),
        portfolio=flat_portfolio(captured_at_ns=opp_time),
        decision_time_ns=opp_time,
        symbol="BIYA",
    )
    if risk.decision not in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE}:
        raise RuntimeError(f"golden lifecycle risk rejected: {risk.reason_codes}")

    adaptation_service = AdaptationService(repository=repo)
    adaptation_results = adaptation_service.assess_and_persist(
        policy=default_adaptation_policy(),
        bundle=recurrence_bundle(),
        context=default_context(
            champion_assignment_ref=champion.assignment_id,
            runtime_activation_ref=activation.activation_id,
        ),
    )
    if adaptation_results[0].assessment.action != AdaptationAction.TRIGGER_RESEARCH:
        raise RuntimeError("golden lifecycle adaptation did not trigger research")
    trigger = adaptation_results[0].trigger
    if trigger is None:
        raise RuntimeError("golden lifecycle missing research trigger")

    finding = adaptation_service.register_finding_from_trigger(
        trigger,
        mode="PAPER",
        recorded_at_ns=T + 4,
    )
    if finding.finding_type != ResearchFindingType.MONITORING_OBSERVATION:
        raise RuntimeError("golden lifecycle finding type incorrect")

    artifacts = GoldenLifecycleArtifacts(
        champion_assignment_id=champion.assignment_id,
        runtime_activation_id=activation.activation_id,
        forecast_id=forecast.forecast_id,
        opportunity_id=opp_result.opportunity.opportunity_id,
        trade_proposal_id=proposal.proposal_id,
        risk_decision_id=risk.risk_decision_id,
        research_trigger_id=trigger.research_trigger_id,
        research_finding_id=finding.finding_id,
        candidate_id=candidate.candidate_id,
        validation_report_id=report.validation_report_id,
    )
    metadata = {
        "governance_opportunities_allowed": governance_state.opportunities_allowed,
        "validation_disposition": report.final_disposition.value,
        "risk_decision": risk.decision.value,
        "paper_execution_requested": paper_execution,
    }
    return artifacts, metadata
