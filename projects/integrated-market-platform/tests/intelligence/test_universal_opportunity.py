"""Focused tests for the universal economic sidecar and canonical bridge."""

from __future__ import annotations

import unittest
from dataclasses import replace

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
)
from market_platform_foundation.intelligence.opportunity import (
    EconomicAssumptionsV1,
    MoneyMinorUnits,
    OpportunityBridgeError,
    UniversalEconomicAssessmentV1,
    adapt_shared_p4_decomposition,
    bridge_strategy_match_to_opportunity,
    economic_assessment_v1_from_dict,
    economic_assessment_v1_to_dict,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.quality.models import AvailabilityState
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import bootstrap_control_champion


class UniversalEconomicAssessmentTests(unittest.TestCase):
    def _assessment(self) -> UniversalEconomicAssessmentV1:
        return UniversalEconomicAssessmentV1.create(
            scope=IntelligenceScope(instrument_ids=("NVDA",)),
            account_id="paper-account",
            mode="ACTUAL_LIVE",
            assessed_at_ns=T + 1_000_000_000,
            assumptions=EconomicAssumptionsV1(
                assumptions_id="assumptions-v1",
                version="1.0.0",
            ),
            expected_gross_pnl=MoneyMinorUnits(1250, "USD", 2),
            expected_net_pnl=MoneyMinorUnits(980, "USD", 2),
            capital_required=MoneyMinorUnits(10000, "USD", 2),
            buying_power_required=MoneyMinorUnits(10000, "USD", 2),
            maximum_loss=MoneyMinorUnits(3000, "USD", 2),
            expected_return_bps=98,
            loss_probability=0.20,
            expected_hold_ns=300_000_000_000,
            maximum_hold_ns=600_000_000_000,
            capital_lock_ns=600_000_000_000,
            expires_at_ns=T + 600_000_000_000,
            spread_bps=4,
            slippage_bps=3,
            fees_bps=1,
            borrow_bps=0,
            roll_bps=0,
            funding_bps=0,
            fill_probability=0.85,
            adverse_selection_probability=0.10,
            account_actionability="ACTIONABLE",
        )

    def test_round_trip_is_typed_and_deterministic(self) -> None:
        assessment = self._assessment()
        payload = economic_assessment_v1_to_dict(assessment)
        restored = economic_assessment_v1_from_dict(payload)
        self.assertEqual(assessment, restored)
        self.assertEqual(assessment.assessment_id, restored.assessment_id)
        self.assertIsInstance(payload["expected_gross_pnl"]["amount_minor"], int)
        self.assertEqual(payload["expected_gross_pnl"]["unit"], "minor_units")

    def test_money_rejects_non_integer_minor_units(self) -> None:
        with self.assertRaises(ValueError):
            MoneyMinorUnits(1.5, "USD", 2)  # type: ignore[arg-type]

    def test_p4_adapter_rejects_untyped_decomposition(self) -> None:
        with self.assertRaises(ValueError):
            adapt_shared_p4_decomposition(
                {
                    "payoff": {"expected_pnl": 100},
                    "costs": {"friction_cost": 2},
                },
                scope=IntelligenceScope(instrument_ids=("NVDA",)),
                account_id="paper-account",
                mode="ACTUAL_LIVE",
                assessed_at_ns=T,
                assumptions=self._assessment().assumptions,
            )

    def test_p4_adapter_accepts_explicit_minor_units(self) -> None:
        adapted = adapt_shared_p4_decomposition(
            {
                "units": {
                    "expected_gross_pnl": "USD:minor_units:2",
                    "expected_net_pnl": "USD:minor_units:2",
                    "capital_required": "USD:minor_units:2",
                    "expected_return_bps": "NONE:bps:0",
                },
                "expected_gross_pnl": 1000,
                "expected_net_pnl": 900,
                "capital_required": 5000,
                "expected_return_bps": 180,
            },
            scope=IntelligenceScope(instrument_ids=("NVDA",)),
            account_id="paper-account",
            mode="ACTUAL_LIVE",
            assessed_at_ns=T,
            assumptions=self._assessment().assumptions,
        )
        self.assertEqual(adapted.expected_net_pnl.amount_minor, 900)
        self.assertEqual(adapted.expected_return_bps, 180)


class UniversalOpportunityBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.promotion = __import__(
            "market_platform_foundation.intelligence.promotion",
            fromlist=["PromotionEngine"],
        ).PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = __import__(
            "tests.intelligence.promotion_fixtures",
            fromlist=["validated_candidate_bundle"],
        ).validated_candidate_bundle()
        self.champion = bootstrap_control_champion(self.promotion, candidate, effective_from_ns=T)
        self.forecast = champion_forecast(self.champion)
        self.policy = default_opportunity_policy()
        self.context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        self.sidecar = UniversalEconomicAssessmentTests()._assessment()
        self.match = StrategyMatch.create(
            strategy_id="strategy-1",
            strategy_identity_hash="strategy-hash",
            scope=self.forecast.scope,
            decision_time_ns=T,
            disposition=StrategyMatchDisposition.MATCHED,
            capability_state=AvailabilityState.AVAILABLE,
            quality=self.forecast.quality,
            source_forecast_refs=(
                ContractReference(kind="forecast", id=self.forecast.forecast_id),
            ),
            context={"account_id": "paper-account", "mode": "ACTUAL_LIVE"},
        )

    def test_bridge_calls_existing_engine_and_persists_lineage(self) -> None:
        repository = InMemoryIntelligenceRepository()
        result = bridge_strategy_match_to_opportunity(
            match=self.match,
            forecast=self.forecast,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            policy=self.policy,
            context=self.context,
            economic_assessment=self.sidecar,
            opportunity_decision_time_ns=T + 1_000_000_000,
            repository=repository,
        )
        self.assertIsNotNone(result.opportunity)
        assert result.opportunity is not None
        self.assertIn(result.economic_assessment_ref, result.assessment.lineage_refs)
        self.assertIn(result.economic_assessment_ref, result.opportunity.lineage_refs)
        self.assertEqual(
            repository.put_economic_assessment(self.sidecar),
            RepositoryPutResult.ALREADY_PRESENT,
        )
        self.assertEqual(
            repository.put_economic_assessment(self.sidecar),
            RepositoryPutResult.ALREADY_PRESENT,
        )
        self.assertIsNotNone(repository.get_economic_assessment(self.sidecar.assessment_id))

    def test_bridge_rejects_non_matched_and_mismatched_forecast(self) -> None:
        rejected = replace(
            self.match,
            disposition=StrategyMatchDisposition.REJECTED,
            rejection_reasons=("test",),
        )
        with self.assertRaises(OpportunityBridgeError):
            bridge_strategy_match_to_opportunity(
                match=rejected,
                forecast=self.forecast,
                champion_at_forecast=self.champion,
                champion_at_opportunity=self.champion,
                policy=self.policy,
                context=self.context,
                economic_assessment=self.sidecar,
                opportunity_decision_time_ns=T + 1,
            )

        mismatched = replace(
            self.match,
            source_forecast_refs=(
                ContractReference(kind="forecast", id="other-forecast"),
            ),
        )
        with self.assertRaises(OpportunityBridgeError):
            bridge_strategy_match_to_opportunity(
                match=mismatched,
                forecast=self.forecast,
                champion_at_forecast=self.champion,
                champion_at_opportunity=self.champion,
                policy=self.policy,
                context=self.context,
                economic_assessment=self.sidecar,
                opportunity_decision_time_ns=T + 1,
            )

    def test_bridge_rejects_account_mode_and_pit_mismatches(self) -> None:
        wrong_scope = replace(
            self.match,
            context={"account_id": "different-account", "mode": "ACTUAL_LIVE"},
        )
        with self.assertRaises(OpportunityBridgeError):
            bridge_strategy_match_to_opportunity(
                match=wrong_scope,
                forecast=self.forecast,
                champion_at_forecast=self.champion,
                champion_at_opportunity=self.champion,
                policy=self.policy,
                context=self.context,
                economic_assessment=self.sidecar,
                opportunity_decision_time_ns=T + 1,
            )

        with self.assertRaises(OpportunityBridgeError):
            bridge_strategy_match_to_opportunity(
                match=self.match,
                forecast=self.forecast,
                champion_at_forecast=self.champion,
                champion_at_opportunity=self.champion,
                policy=self.policy,
                context=self.context,
                economic_assessment=self.sidecar,
                opportunity_decision_time_ns=T - 1,
            )


if __name__ == "__main__":
    unittest.main()
