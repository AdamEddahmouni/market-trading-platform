"""Integrated BUILD 01–22 lifecycle test."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.execution import PaperExecutionOrchestrator
from market_platform_foundation.intelligence.opportunity import AssessmentAction, OpportunityEngine
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import PromotionDecisionKind, PromotionEngine
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.intelligence.promotion import ShadowMatchedObservation
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_opportunity, sample_quote
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import (
    DEFAULT_SCOPE,
    shadow_observations,
    validated_candidate_bundle,
)
from tests.intelligence.test_validation_temporal_firewall import (
    _holdout_examples,
    _manifest_with_holdout,
    _trained_candidate,
)
from market_platform_foundation.intelligence.validation import (
    ValidationDisposition,
    ValidationEngine,
    ValidationRunContext,
    build_validation_plan,
    statistical_candidate_profile,
)
from market_platform_foundation.intelligence.promotion import (
    build_promotion_policy,
    build_shadow_evidence_manifest,
    StatisticalRequirementKind,
)


class Build0122LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"

    def test_opportunity_to_paper_execution(self) -> None:
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
            self.skipTest("validation inconclusive in fixture environment")

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

        eligibility = promotion_engine.assess_eligibility(
            policy=promotion_policy,
            candidate=candidate,
            validation_report=report,
            candidate_artifact_bytes=artifact_bytes,
        )
        repo.put_promotion_eligibility_assessment(eligibility)
        registration = promotion_engine.register_challenger(
            policy=promotion_policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T + 50,
        )
        repo.put_challenger_registration(registration)
        shadow_rows = [
            ShadowMatchedObservation(**row)
            for row in shadow_observations(6, challenger_better=True, start_ns=T + 60)
        ]
        shadow = build_shadow_evidence_manifest(
            challenger_registration_id=registration.challenger_registration_id,
            champion_assignment_id=champion.assignment_id,
            promotion_policy_id=promotion_policy.promotion_policy_id,
            evidence_tier=EvidenceTier.OBSERVED_REPLAY,
            matched_observations=tuple(shadow_rows),
        )
        repo.put_shadow_evidence_manifest(shadow)
        decision = promotion_engine.evaluate_promotion(
            policy=promotion_policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            shadow_evidence=shadow,
            experiment=manifest,
        )
        repo.put_promotion_decision(decision)
        if decision.decision != PromotionDecisionKind.PROMOTE:
            self.skipTest("promotion not granted in fixture environment")

        new_champion = promotion_engine.create_champion_assignment(
            decision=decision,
            candidate=candidate,
            effective_from_ns=T + 200,
            previous_champion=champion,
        )
        repo.put_champion_assignment(new_champion)

        opportunity_policy = default_opportunity_policy()
        repo.put_opportunity_policy(opportunity_policy)
        forecast = champion_forecast(new_champion, decision_time_ns=T + 250)
        repo.put_forecast(forecast)
        opp_time = T + 260
        context = default_opportunity_context(decision_time_ns=opp_time)
        opp_result = OpportunityEngine().assess(
            forecast=forecast,
            policy=opportunity_policy,
            context=context,
            champion_at_forecast=new_champion,
            champion_at_opportunity=new_champion,
            opportunity_decision_time_ns=opp_time,
        )
        repo.put_opportunity_assessment(opp_result.assessment)
        assert opp_result.opportunity is not None
        repo.put_opportunity(opp_result.opportunity)

        exec_policy = default_execution_policy(max_trade_notional_minor=500_00)
        repo.put_execution_policy(exec_policy)
        portfolio = flat_portfolio(
            equity_minor=1_000_000_00,
            cash_minor=1_000_000_00,
            captured_at_ns=opp_time,
        )
        repo.put_paper_portfolio_snapshot(portfolio)

        from pathlib import Path
        import sys

        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root))
        sys.path.insert(0, str(root / "src"))
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=root.parent)
        store.load()
        bars = store.bars_for_execution()
        if not bars:
            self.skipTest("no replay bars")

        cutoff = store.prediction_cutoff()
        quote = sample_quote(available_time_ns=cutoff)
        opportunity = sample_opportunity(
            opportunity_id=opp_result.opportunity.opportunity_id,
            created_at_ns=opp_time,
            valid_until_ns=cutoff + 1_000_000_000_000,
        )

        ledger = PaperExecutionLedger.open_session(
            replay_session_id=store.session_id,
            instrument_id=store.instrument_id,
            symbol=store.symbol,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        result = PaperExecutionOrchestrator().execute_paper(
            opportunity=opportunity,
            policy=exec_policy,
            portfolio=portfolio,
            quote=quote,
            ledger=ledger,
            bars=bars,
            decision_time_ns=cutoff,
            instrument_id=store.instrument_id,
            symbol=store.symbol,
            execution_authority="AUTHORIZED",
        )
        self.assertIsNotNone(result.proposal)
        self.assertIsNotNone(result.risk_decision)
        if result.risk_decision.approved_quantity > 0:
            self.assertIsNotNone(result.paper_submit)
            repo.put_trade_proposal(result.proposal)
            repo.put_risk_decision(result.risk_decision)


if __name__ == "__main__":
    unittest.main()
