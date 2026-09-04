"""BUILD 21 governed opportunity engine tests."""

from __future__ import annotations

import copy
import inspect
import unittest

from market_platform_foundation.intelligence.contracts.common import OpportunitySide
from market_platform_foundation.intelligence.fusion.types import ForecastContributorRole
from market_platform_foundation.intelligence.opportunity import (
    AssessmentAction,
    AssessmentReasonCode,
    EconomicValueStatus,
    OpportunityEngine,
    build_opportunity_policy,
    opportunity_assessment_v1_from_dict,
    opportunity_assessment_v1_to_dict,
    opportunity_policy_v1_from_dict,
    opportunity_policy_v1_to_dict,
)
from market_platform_foundation.intelligence.opportunity.economics import (
    assert_no_probability_bps_subtraction,
    probability_edge_for_side,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.promotion import PromotionEngine
from market_platform_foundation.intelligence.quality.models import DecisionAction
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.promotion_fixtures import bootstrap_control_champion, DEFAULT_SCOPE
from tests.intelligence.routing_fixtures import quality_decision


class OpportunityPolicyTests(unittest.TestCase):
    def test_policy_round_trip(self) -> None:
        policy = default_opportunity_policy()
        restored = opportunity_policy_v1_from_dict(opportunity_policy_v1_to_dict(policy))
        self.assertEqual(policy.opportunity_policy_id, restored.opportunity_policy_id)

    def test_policy_id_deterministic(self) -> None:
        a = default_opportunity_policy()
        b = default_opportunity_policy()
        self.assertEqual(a.opportunity_policy_id, b.opportunity_policy_id)

    def test_semantic_change_changes_policy_id(self) -> None:
        base = default_opportunity_policy(minimum_probability_edge=0.05)
        changed = default_opportunity_policy(minimum_probability_edge=0.10)
        self.assertNotEqual(base.opportunity_policy_id, changed.opportunity_policy_id)


class ProbabilityEdgeTests(unittest.TestCase):
    def test_long_edge(self) -> None:
        edge = probability_edge_for_side(0.70, OpportunitySide.LONG)
        self.assertAlmostEqual(edge, 0.20)

    def test_short_edge(self) -> None:
        edge = probability_edge_for_side(0.25, OpportunitySide.SHORT)
        self.assertEqual(edge, 0.25)

    def test_p_half_zero_edge(self) -> None:
        edge = probability_edge_for_side(0.50, OpportunitySide.LONG)
        self.assertEqual(edge, 0.0)


class DimensionalIntegrityTests(unittest.TestCase):
    def test_no_probability_bps_subtraction_in_module(self) -> None:
        from market_platform_foundation.intelligence.opportunity import engine as engine_mod
        from market_platform_foundation.intelligence.opportunity import economics as economics_mod

        for module in (engine_mod, economics_mod):
            source = inspect.getsource(module)
            self.assertNotIn("probability - spread", source.replace("_", ""))
            self.assertNotIn("probability_edge - spread", source)

    def test_guard_marker_raises(self) -> None:
        with self.assertRaises(AssertionError):
            assert_no_probability_bps_subtraction()


class ChampionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = OpportunityEngine()
        self.promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        self.champion = bootstrap_control_champion(self.promotion, candidate, effective_from_ns=T)
        self.policy = default_opportunity_policy()

    def test_governed_champion_forecast_emits(self) -> None:
        forecast = champion_forecast(self.champion)
        context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1_000_000_000,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.EMIT)
        self.assertIsNotNone(result.opportunity)

    def test_non_champion_forecast_suppressed(self) -> None:
        forecast = champion_forecast(self.champion)
        mutated = copy.deepcopy(forecast)
        object.__setattr__(
            mutated,
            "metadata",
            {**forecast.metadata, "champion_candidate_id": "other-candidate"},
        )
        context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        result = self.engine.assess(
            forecast=mutated,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1_000_000_000,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.SUPPRESS)
        self.assertIn(
            AssessmentReasonCode.FORECAST_NOT_FROM_GOVERNED_CHAMPION,
            result.assessment.reason_codes,
        )

    def test_control_forecast_suppressed(self) -> None:
        forecast = champion_forecast(
            self.champion,
            contributor_role=ForecastContributorRole.CONTROL.value,
            forecast_stage="CONTROL_RAW",
        )
        context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1_000_000_000,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.SUPPRESS)
        self.assertIn(AssessmentReasonCode.FORECAST_ROLE_NOT_ALLOWED, result.assessment.reason_codes)

    def test_champion_changed_suppressed(self) -> None:
        forecast = champion_forecast(self.champion)
        other = copy.deepcopy(self.champion)
        object.__setattr__(other, "assignment_id", "CHAMP-other")
        context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=other,
            opportunity_decision_time_ns=T + 1_000_000_000,
        )
        self.assertIn(AssessmentReasonCode.CHAMPION_CHANGED_SINCE_FORECAST, result.assessment.reason_codes)


class TemporalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = OpportunityEngine()
        self.promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        self.champion = bootstrap_control_champion(self.promotion, candidate, effective_from_ns=T)
        self.policy = default_opportunity_policy()

    def test_opportunity_before_forecast_fail_closed(self) -> None:
        forecast = champion_forecast(self.champion, decision_time_ns=T + 1000)
        context = default_opportunity_context(decision_time_ns=T)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.FAIL_CLOSED)

    def test_forecast_expired_suppressed(self) -> None:
        forecast = champion_forecast(self.champion, decision_time_ns=T)
        expiry = T + HORIZON_5M
        context = default_opportunity_context(decision_time_ns=expiry)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=expiry,
        )
        self.assertIn(AssessmentReasonCode.FORECAST_EXPIRED, result.assessment.reason_codes)

    def test_forecast_too_old(self) -> None:
        policy = default_opportunity_policy(max_forecast_age_ns=1000)
        forecast = champion_forecast(self.champion, decision_time_ns=T)
        context = default_opportunity_context(decision_time_ns=T + 2000)
        result = self.engine.assess(
            forecast=forecast,
            policy=policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 2000,
        )
        self.assertIn(AssessmentReasonCode.FORECAST_TOO_OLD, result.assessment.reason_codes)


class ProbabilityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = OpportunityEngine()
        self.promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        self.champion = bootstrap_control_champion(self.promotion, candidate, effective_from_ns=T)
        self.policy = default_opportunity_policy(minimum_probability_edge=0.10)

    def test_below_threshold_suppressed(self) -> None:
        forecast = champion_forecast(self.champion, probability=0.55, calibrated_probability=0.55)
        context = default_opportunity_context(decision_time_ns=T + 1)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertIn(AssessmentReasonCode.PROBABILITY_EDGE_TOO_SMALL, result.assessment.reason_codes)

    def test_exact_threshold_passes(self) -> None:
        forecast = champion_forecast(self.champion, probability=0.60)
        context = default_opportunity_context(decision_time_ns=T + 1)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.EMIT)

    def test_calibrated_required_missing(self) -> None:
        policy = build_opportunity_policy(
            champion_scope=DEFAULT_SCOPE,
            require_calibrated_probability=True,
            minimum_probability_edge=0.05,
        )
        forecast = champion_forecast(self.champion, calibrated_probability=None)
        context = default_opportunity_context(decision_time_ns=T + 1)
        result = self.engine.assess(
            forecast=forecast,
            policy=policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertIn(AssessmentReasonCode.CALIBRATED_PROBABILITY_UNAVAILABLE, result.assessment.reason_codes)


class QualityLiquidityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = OpportunityEngine()
        self.promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        self.champion = bootstrap_control_champion(self.promotion, candidate, effective_from_ns=T)
        self.policy = default_opportunity_policy()

    def test_quality_fail_closed(self) -> None:
        forecast = champion_forecast(self.champion)
        context = default_opportunity_context(decision_time_ns=T + 1)
        object.__setattr__(
            context,
            "quality_decision",
            quality_decision(action=DecisionAction.FAIL_CLOSED),
        )
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.FAIL_CLOSED)

    def test_wide_spread_suppressed(self) -> None:
        forecast = champion_forecast(self.champion)
        context = default_opportunity_context(decision_time_ns=T + 1, spread_bps=100.0)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertIn(AssessmentReasonCode.SPREAD_TOO_WIDE, result.assessment.reason_codes)

    def test_invalid_spread_fail_closed(self) -> None:
        forecast = champion_forecast(self.champion)
        context = default_opportunity_context(decision_time_ns=T + 1, spread_bps=-1.0)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.FAIL_CLOSED)

    def test_depth_imbalance_not_liquidity_gate(self) -> None:
        forecast = champion_forecast(self.champion)
        context = default_opportunity_context(decision_time_ns=T + 1, depth_imbalance=5.0, spread_bps=10.0)
        result = self.engine.assess(
            forecast=forecast,
            policy=self.policy,
            context=context,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.EMIT)


class IdentityPersistenceTests(unittest.TestCase):
    def test_assessment_id_deterministic(self) -> None:
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        policy = default_opportunity_policy()
        forecast = champion_forecast(champion)
        context = default_opportunity_context(decision_time_ns=T + 1)
        engine = OpportunityEngine()
        left = engine.assess(
            forecast=forecast,
            policy=policy,
            context=context,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        right = engine.assess(
            forecast=forecast,
            policy=policy,
            context=context,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(left.assessment.assessment_id, right.assessment.assessment_id)
        self.assertEqual(left.opportunity.opportunity_id, right.opportunity.opportunity_id)

    def test_assessment_round_trip(self) -> None:
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        result = OpportunityEngine().assess(
            forecast=champion_forecast(champion),
            policy=default_opportunity_policy(),
            context=default_opportunity_context(decision_time_ns=T + 1),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        restored = opportunity_assessment_v1_from_dict(
            opportunity_assessment_v1_to_dict(result.assessment)
        )
        self.assertEqual(result.assessment.assessment_id, restored.assessment_id)

    def test_persistence_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        policy = default_opportunity_policy()
        repo.put_opportunity_policy(policy)
        result = OpportunityEngine().assess(
            forecast=champion_forecast(champion),
            policy=policy,
            context=default_opportunity_context(decision_time_ns=T + 1),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(repo.put_opportunity_assessment(result.assessment), RepositoryPutResult.INSERTED)
        self.assertEqual(
            repo.put_opportunity_assessment(result.assessment),
            RepositoryPutResult.ALREADY_PRESENT,
        )
        assert result.opportunity is not None
        repo.put_opportunity(result.opportunity)
        self.assertEqual(repo.put_opportunity(result.opportunity), RepositoryPutResult.ALREADY_PRESENT)

    def test_persistence_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        policy = default_opportunity_policy()
        result = OpportunityEngine().assess(
            forecast=champion_forecast(champion),
            policy=policy,
            context=default_opportunity_context(decision_time_ns=T + 1),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        mutated = copy.deepcopy(result.assessment)
        object.__setattr__(mutated, "probability_edge", 0.99)
        repo.put_opportunity_assessment(result.assessment)
        with self.assertRaises(RepositoryConflictError):
            repo.put_opportunity_assessment(mutated)


class LeakageTests(unittest.TestCase):
    def test_future_context_fail_closed(self) -> None:
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        forecast = champion_forecast(champion)
        context = default_opportunity_context(decision_time_ns=T + 1)
        object.__setattr__(context, "spread_available_time_ns", T + 10_000_000_000)
        result = OpportunityEngine().assess(
            forecast=forecast,
            policy=default_opportunity_policy(),
            context=context,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.FAIL_CLOSED)

    def test_outcome_independence(self) -> None:
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        forecast = champion_forecast(champion)
        context = default_opportunity_context(decision_time_ns=T + 1)
        engine = OpportunityEngine()
        base = engine.assess(
            forecast=forecast,
            policy=default_opportunity_policy(),
            context=context,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        mutated_forecast = copy.deepcopy(forecast)
        object.__setattr__(
            mutated_forecast,
            "metadata",
            {**forecast.metadata, "realized_return": 999.0, "outcome_id": "out-1"},
        )
        other = engine.assess(
            forecast=mutated_forecast,
            policy=default_opportunity_policy(),
            context=context,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(base.assessment.assessment_id, other.assessment.assessment_id)


class EconomicValueTests(unittest.TestCase):
    def test_direction_only_unavailable(self) -> None:
        promotion = PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures", fromlist=["validated_candidate_bundle"]
        ).validated_candidate_bundle()
        champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        result = OpportunityEngine().assess(
            forecast=champion_forecast(champion),
            policy=default_opportunity_policy(),
            context=default_opportunity_context(decision_time_ns=T + 1),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
        )
        self.assertEqual(
            result.assessment.economic_value_status,
            EconomicValueStatus.UNAVAILABLE_DIRECTION_ONLY,
        )
        assert result.opportunity is not None
        self.assertIsNone(result.opportunity.expected_return)
        self.assertIsNone(result.opportunity.expected_net_edge)


if __name__ == "__main__":
    unittest.main()
