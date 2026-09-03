"""TDD coverage for bounded account-scoped opportunity comparison/allocation."""

from __future__ import annotations

import unittest
from dataclasses import replace

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity import (
    AccountActionability,
    CapitalAllocationConstraintsV1,
    CapitalAllocator,
    ComparisonConstraintsV1,
    ComparisonReasonCode,
    EconomicAssumptionsV1,
    GlobalOpportunityComparator,
    LiquidityCapacityV1,
    LiquidityState,
    MoneyMinorUnits,
    OpportunityComparisonCandidateV1,
    OpportunityComparisonError,
    UniversalEconomicAssessmentV1,
)


DECISION_NS = 10_000
SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _candidate(
    *,
    opportunity_id: str,
    cluster_id: str,
    expected_net_pnl: int | None = 500,
    expected_return_bps: float | None = 100,
    maximum_loss: int | None = 100,
    capital_required: int | None = 1_000,
    buying_power_required: int | None = 1_000,
    expected_hold_ns: int | None = 100,
    maximum_hold_ns: int | None = 200,
    capital_lock_ns: int | None = 200,
    account_actionability: AccountActionability = AccountActionability.ACTIONABLE,
    liquidity_state: LiquidityState = LiquidityState.AVAILABLE,
    scope: IntelligenceScope = SCOPE,
    account_id: str = "acct-1",
    mode: str = "PAPER",
    assessed_at_ns: int = DECISION_NS - 1,
    expires_at_ns: int | None = DECISION_NS + 100,
) -> OpportunityComparisonCandidateV1:
    opportunity = OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=scope,
        created_at_ns=DECISION_NS - 10,
        quality=QUALITY,
        opportunity_type="event",
        side=OpportunitySide.LONG,
        valid_until_ns=DECISION_NS + 100,
        source_forecast_refs=(
            ContractReference(kind="forecast", id=f"forecast-{opportunity_id}"),
        ),
        lineage_refs=(
            ContractReference(kind="hypothesis", id=f"hypothesis-{opportunity_id}"),
        ),
        metadata={"account_id": account_id, "mode": mode},
    )
    sidecar = UniversalEconomicAssessmentV1.create(
        scope=scope,
        account_id=account_id,
        mode=mode,
        assessed_at_ns=assessed_at_ns,
        expires_at_ns=expires_at_ns,
        assumptions=EconomicAssumptionsV1(
            assumptions_id="economics-v1",
            version="1",
        ),
        expected_net_pnl=(
            MoneyMinorUnits(expected_net_pnl, "USD", 2)
            if expected_net_pnl is not None
            else None
        ),
        expected_return_bps=expected_return_bps,
        maximum_loss=(
            MoneyMinorUnits(maximum_loss, "USD", 2)
            if maximum_loss is not None
            else None
        ),
        capital_required=(
            MoneyMinorUnits(capital_required, "USD", 2)
            if capital_required is not None
            else None
        ),
        buying_power_required=(
            MoneyMinorUnits(buying_power_required, "USD", 2)
            if buying_power_required is not None
            else None
        ),
        expected_hold_ns=expected_hold_ns,
        maximum_hold_ns=maximum_hold_ns,
        capital_lock_ns=capital_lock_ns,
        fill_probability=0.8,
        liquidity=LiquidityCapacityV1(state=liquidity_state),
        account_actionability=account_actionability,
        source_refs=(
            ContractReference(kind="signal", id=f"signal-{opportunity_id}"),
        ),
    )
    return OpportunityComparisonCandidateV1(
        cluster_id=cluster_id,
        opportunity=opportunity,
        economic_assessment=sidecar,
    )


def _constraints(**overrides: object) -> ComparisonConstraintsV1:
    values: dict[str, object] = {
        "account_id": "acct-1",
        "mode": "PAPER",
        "decision_time_ns": DECISION_NS,
        "currency": "USD",
        "scale": 2,
    }
    values.update(overrides)
    return ComparisonConstraintsV1(**values)


class GlobalOpportunityComparatorTests(unittest.TestCase):
    def test_preserves_heterogeneous_explicit_dimensions_without_universal_score(self) -> None:
        candidate = _candidate(
            opportunity_id="opp-a",
            cluster_id="cluster-a",
            expected_return_bps=None,
            liquidity_state=LiquidityState.CONSTRAINED,
        )
        result = GlobalOpportunityComparator().compare(_constraints(), (candidate,))

        self.assertEqual(len(result.eligible_candidates), 1)
        vector = result.evaluations[0].comparison_vector
        self.assertEqual(vector.expected_net_pnl_minor, 500)
        self.assertIsNone(vector.expected_return_bps)
        self.assertEqual(vector.maximum_loss_minor, 100)
        self.assertEqual(vector.capital_required_minor, 1_000)
        self.assertEqual(vector.buying_power_required_minor, 1_000)
        self.assertEqual(vector.liquidity_state, LiquidityState.CONSTRAINED)
        self.assertFalse(hasattr(vector, "score"))
        self.assertFalse(hasattr(result, "universal_score"))

    def test_orders_by_documented_lexicographic_dimensions_and_ids(self) -> None:
        higher_pnl = _candidate(
            opportunity_id="opp-b",
            cluster_id="cluster-b",
            expected_net_pnl=500,
            expected_return_bps=10,
        )
        lower_pnl = _candidate(
            opportunity_id="opp-a",
            cluster_id="cluster-a",
            expected_net_pnl=400,
            expected_return_bps=900,
        )
        first = GlobalOpportunityComparator().compare(
            _constraints(), (lower_pnl, higher_pnl)
        )
        second = GlobalOpportunityComparator().compare(
            _constraints(), (higher_pnl, lower_pnl)
        )

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.opportunity.opportunity_id for item in first.eligible_candidates),
            ("opp-b", "opp-a"),
        )

    def test_suppresses_only_one_expression_per_cluster_and_retains_reason(self) -> None:
        weaker = _candidate(
            opportunity_id="opp-a",
            cluster_id="same-thesis",
            expected_net_pnl=100,
        )
        stronger = _candidate(
            opportunity_id="opp-b",
            cluster_id="same-thesis",
            expected_net_pnl=200,
        )
        result = GlobalOpportunityComparator().compare(_constraints(), (weaker, stronger))

        self.assertEqual(
            tuple(item.opportunity.opportunity_id for item in result.eligible_candidates),
            ("opp-b",),
        )
        suppressed = next(
            item for item in result.evaluations
            if item.candidate.opportunity.opportunity_id == "opp-a"
        )
        self.assertIn(ComparisonReasonCode.DUPLICATE_THESIS_SUPPRESSED, suppressed.reasons)
        self.assertEqual(result.counters.duplicate_thesis_suppressed, 1)

    def test_missing_economics_is_excluded_with_clear_no_action_reason(self) -> None:
        candidate = _candidate(
            opportunity_id="opp-missing",
            cluster_id="cluster-missing",
            expected_net_pnl=None,
            maximum_loss=None,
        )
        result = GlobalOpportunityComparator().compare(_constraints(), (candidate,))

        self.assertEqual(result.eligible_candidates, ())
        self.assertIn(
            ComparisonReasonCode.INSUFFICIENT_ECONOMICS,
            result.evaluations[0].reasons,
        )
        self.assertIn(ComparisonReasonCode.NO_ACTION, result.no_action_reasons)
        self.assertEqual(result.counters.insufficient_economics, 1)

    def test_scope_currency_and_point_in_time_guards_fail_closed(self) -> None:
        cases = (
            _candidate(opportunity_id="wrong-account", cluster_id="a", account_id="other"),
            _candidate(opportunity_id="wrong-mode", cluster_id="b", mode="ACTUAL_LIVE"),
            _candidate(
                opportunity_id="future-sidecar",
                cluster_id="c",
                assessed_at_ns=DECISION_NS + 1,
            ),
            _candidate(
                opportunity_id="expired-sidecar",
                cluster_id="d",
                expires_at_ns=DECISION_NS,
            ),
        )
        for candidate in cases:
            with self.subTest(opportunity_id=candidate.opportunity.opportunity_id):
                with self.assertRaises(OpportunityComparisonError):
                    GlobalOpportunityComparator().compare(_constraints(), (candidate,))

        wrong_currency = replace(
            _candidate(opportunity_id="wrong-currency", cluster_id="f"),
            economic_assessment=replace(
                _candidate(opportunity_id="currency-source", cluster_id="g").economic_assessment,
                expected_net_pnl=MoneyMinorUnits(500, "EUR", 2),
                capital_required=MoneyMinorUnits(1_000, "EUR", 2),
                buying_power_required=MoneyMinorUnits(1_000, "EUR", 2),
                maximum_loss=MoneyMinorUnits(100, "EUR", 2),
            ),
        )
        with self.assertRaises(OpportunityComparisonError):
            GlobalOpportunityComparator().compare(_constraints(), (wrong_currency,))

        wrong_scope = _candidate(opportunity_id="wrong-scope", cluster_id="e")
        wrong_scope = replace(
            wrong_scope,
            economic_assessment=replace(
                wrong_scope.economic_assessment,
                scope=IntelligenceScope(instrument_ids=("MSFT",), context_id="regular"),
            ),
        )
        with self.assertRaises(OpportunityComparisonError):
            GlobalOpportunityComparator().compare(_constraints(), (wrong_scope,))


class CapitalAllocatorTests(unittest.TestCase):
    def test_applies_capital_buying_power_and_loss_budgets(self) -> None:
        candidates = (
            _candidate(
                opportunity_id="selected",
                cluster_id="cluster-selected",
                expected_net_pnl=600,
                capital_required=600,
                buying_power_required=500,
                maximum_loss=200,
            ),
            _candidate(
                opportunity_id="capital-blocked",
                cluster_id="cluster-capital",
                capital_required=600,
                buying_power_required=50,
                maximum_loss=100,
            ),
            _candidate(
                opportunity_id="loss-blocked",
                cluster_id="cluster-loss",
                capital_required=100,
                buying_power_required=0,
                maximum_loss=400,
            ),
        )
        comparison = GlobalOpportunityComparator().compare(_constraints(), candidates)
        allocation = CapitalAllocator().allocate(
            comparison,
            CapitalAllocationConstraintsV1(
                account_id="acct-1",
                mode="PAPER",
                decision_time_ns=DECISION_NS,
                currency="USD",
                scale=2,
                available_capital_minor=700,
                available_buying_power_minor=550,
                maximum_loss_budget_minor=250,
            ),
        )

        self.assertEqual(
            tuple(intent.opportunity_ref.id for intent in allocation.allocations),
            ("selected",),
        )
        self.assertEqual(allocation.allocations[0].requested_capital_minor, 600)
        self.assertNotIn("order_id", allocation.allocations[0].__dataclass_fields__)
        self.assertFalse(hasattr(allocation, "risk_decision"))
        self.assertIn(
            ComparisonReasonCode.INSUFFICIENT_CAPITAL,
            allocation.reason_codes_for("capital-blocked"),
        )
        self.assertIn(
            ComparisonReasonCode.MAXIMUM_LOSS_BUDGET,
            allocation.reason_codes_for("loss-blocked"),
        )

    def test_applies_capital_time_limit_and_returns_no_action_when_blocked(self) -> None:
        candidate = _candidate(
            opportunity_id="long-lock",
            cluster_id="cluster-long-lock",
            capital_required=100,
            capital_lock_ns=20,
        )
        comparison = GlobalOpportunityComparator().compare(_constraints(), (candidate,))
        allocation = CapitalAllocator().allocate(
            comparison,
            CapitalAllocationConstraintsV1(
                account_id="acct-1",
                mode="PAPER",
                decision_time_ns=DECISION_NS,
                currency="USD",
                scale=2,
                available_capital_minor=1_000,
                available_buying_power_minor=1_000,
                maximum_loss_budget_minor=1_000,
                capital_time_budget_minor_ns=1_000,
            ),
        )

        self.assertEqual(allocation.allocations, ())
        self.assertIn(
            ComparisonReasonCode.CAPITAL_TIME_LIMIT,
            allocation.reason_codes_for("long-lock"),
        )
        self.assertIn(ComparisonReasonCode.NO_ACTION, allocation.no_action_reasons)

    def test_allocation_output_is_an_intent_not_proposal_order_or_risk_decision(self) -> None:
        candidate = _candidate(opportunity_id="intent-only", cluster_id="cluster-intent")
        comparison = GlobalOpportunityComparator().compare(_constraints(), (candidate,))
        allocation = CapitalAllocator().allocate(
            comparison,
            CapitalAllocationConstraintsV1(
                account_id="acct-1",
                mode="PAPER",
                decision_time_ns=DECISION_NS,
                currency="USD",
                scale=2,
                available_capital_minor=1_000,
                available_buying_power_minor=1_000,
                maximum_loss_budget_minor=1_000,
                capital_time_budget_minor_ns=1_000_000,
            ),
        )
        intent = allocation.allocations[0]

        self.assertEqual(intent.__class__.__name__, "CapitalAllocationIntentV1")
        for forbidden in (
            "proposal_id",
            "risk_decision_id",
            "order_id",
            "broker_order",
            "quantity",
        ):
            self.assertFalse(hasattr(intent, forbidden))


if __name__ == "__main__":
    unittest.main()
