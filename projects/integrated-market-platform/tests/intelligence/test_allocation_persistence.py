"""Focused TDD coverage for durable allocation decision sidecars."""

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
    EconomicAssumptionsV1,
    GlobalOpportunityComparator,
    LiquidityCapacityV1,
    LiquidityState,
    MoneyMinorUnits,
    OpportunityComparisonCandidateV1,
    UniversalEconomicAssessmentV1,
)
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)


DECISION_NS = 10_000
SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)
PORTFOLIO_REF = ContractReference(kind="paper_portfolio_snapshot", id="snapshot-1")


def _candidate(
    *,
    opportunity_id: str,
    cluster_id: str,
    expected_net_pnl: int = 500,
    capital_required: int = 1_000,
    account_id: str = "acct-1",
    mode: str = "PAPER",
    assessed_at_ns: int = DECISION_NS - 1,
) -> OpportunityComparisonCandidateV1:
    opportunity = OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=DECISION_NS - 10,
        quality=QUALITY,
        opportunity_type="event",
        side=OpportunitySide.LONG,
        valid_until_ns=DECISION_NS + 100,
        source_forecast_refs=(
            ContractReference(kind="forecast", id=f"forecast-{opportunity_id}"),
        ),
        lineage_refs=(
            ContractReference(kind="strategy_match", id=f"match-{opportunity_id}"),
        ),
        metadata={"account_id": account_id, "mode": mode},
    )
    sidecar = UniversalEconomicAssessmentV1.create(
        scope=SCOPE,
        account_id=account_id,
        mode=mode,
        assessed_at_ns=assessed_at_ns,
        expires_at_ns=DECISION_NS + 100,
        assumptions=EconomicAssumptionsV1(
            assumptions_id="economics-v1",
            version="1",
        ),
        expected_net_pnl=MoneyMinorUnits(expected_net_pnl, "USD", 2),
        maximum_loss=MoneyMinorUnits(100, "USD", 2),
        capital_required=MoneyMinorUnits(capital_required, "USD", 2),
        buying_power_required=MoneyMinorUnits(capital_required, "USD", 2),
        expected_hold_ns=100,
        maximum_hold_ns=200,
        capital_lock_ns=200,
        fill_probability=0.8,
        liquidity=LiquidityCapacityV1(state=LiquidityState.AVAILABLE),
        account_actionability=AccountActionability.ACTIONABLE,
        source_refs=(
            ContractReference(kind="signal", id=f"signal-{opportunity_id}"),
        ),
    )
    return OpportunityComparisonCandidateV1(
        cluster_id=cluster_id,
        opportunity=opportunity,
        economic_assessment=sidecar,
    )


def _comparison_constraints(**overrides: object) -> ComparisonConstraintsV1:
    values: dict[str, object] = {
        "account_id": "acct-1",
        "mode": "PAPER",
        "decision_time_ns": DECISION_NS,
        "currency": "USD",
        "scale": 2,
    }
    values.update(overrides)
    return ComparisonConstraintsV1(**values)


def _allocation_constraints(**overrides: object) -> CapitalAllocationConstraintsV1:
    values: dict[str, object] = {
        "account_id": "acct-1",
        "mode": "PAPER",
        "decision_time_ns": DECISION_NS,
        "currency": "USD",
        "scale": 2,
        "available_capital_minor": 1_000,
        "available_buying_power_minor": 1_000,
        "maximum_loss_budget_minor": 100,
    }
    values.update(overrides)
    return CapitalAllocationConstraintsV1(**values)


def _allocation_result(
    candidates: tuple[OpportunityComparisonCandidateV1, ...],
    *,
    allocation_constraints: CapitalAllocationConstraintsV1 | None = None,
):
    comparison = GlobalOpportunityComparator().compare(
        _comparison_constraints(),
        candidates,
    )
    constraints = allocation_constraints or _allocation_constraints()
    allocation = CapitalAllocator().allocate(comparison, constraints)
    return comparison, constraints, allocation


class AllocationPersistenceTests(unittest.TestCase):
    def test_selected_decision_freezes_decision_set_and_lineage(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            AllocationDecisionStatus,
            build_allocation_decisions,
        )

        candidate = _candidate(opportunity_id="selected", cluster_id="cluster-selected")
        comparison, allocation_constraints, allocation = _allocation_result((candidate,))
        decisions = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )

        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision.status, AllocationDecisionStatus.SELECTED)
        self.assertEqual(decision.account_id, "acct-1")
        self.assertEqual(decision.mode, "PAPER")
        self.assertEqual(decision.comparison_id, comparison.comparison_id)
        self.assertEqual(decision.rank, 1)
        self.assertEqual(decision.cluster_ref.id, "cluster-selected")
        self.assertEqual(decision.strategy_match_ref.id, "match-selected")
        self.assertEqual(decision.forecast_refs[0].id, "forecast-selected")
        self.assertEqual(decision.portfolio_snapshot_ref, PORTFOLIO_REF)
        self.assertEqual(decision.comparison_constraints, _comparison_constraints())
        self.assertEqual(decision.allocation_constraints, allocation_constraints)
        self.assertEqual(decision.comparison_vector, comparison.evaluations[0].comparison_vector)
        self.assertEqual(
            decision.allocation_intent_ref.id,
            allocation.allocations[0].allocation_id,
        )

    def test_not_selected_decision_retains_budget_reason_and_order_context(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            AllocationDecisionStatus,
            build_allocation_decisions,
        )

        selected = _candidate(
            opportunity_id="selected",
            cluster_id="cluster-selected",
            expected_net_pnl=600,
            capital_required=600,
        )
        not_selected = _candidate(
            opportunity_id="not-selected",
            cluster_id="cluster-not-selected",
            expected_net_pnl=500,
            capital_required=600,
        )
        comparison, allocation_constraints, allocation = _allocation_result(
            (selected, not_selected),
            allocation_constraints=_allocation_constraints(
                available_capital_minor=600,
                available_buying_power_minor=600,
            ),
        )
        decisions = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )

        by_id = {decision.opportunity_ref.id: decision for decision in decisions}
        self.assertEqual(by_id["selected"].status, AllocationDecisionStatus.SELECTED)
        self.assertEqual(
            by_id["not-selected"].status,
            AllocationDecisionStatus.NOT_SELECTED,
        )
        self.assertEqual(by_id["not-selected"].rank, 2)
        self.assertEqual(
            tuple(ref.id for ref in by_id["not-selected"].competing_opportunity_refs),
            ("selected", "not-selected"),
        )
        self.assertEqual(by_id["not-selected"].allocated_capital_minor, 0)
        self.assertTrue(by_id["not-selected"].reason_codes)

    def test_no_allocation_records_share_set_context(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            AllocationDecisionStatus,
            build_allocation_decisions,
        )

        candidates = (
            _candidate(opportunity_id="blocked-a", cluster_id="cluster-a"),
            _candidate(opportunity_id="blocked-b", cluster_id="cluster-b"),
        )
        comparison, allocation_constraints, allocation = _allocation_result(
            candidates,
            allocation_constraints=_allocation_constraints(
                available_capital_minor=0,
                available_buying_power_minor=0,
            ),
        )
        decisions = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )

        self.assertEqual(len(decisions), 2)
        self.assertEqual(
            {decision.status for decision in decisions},
            {AllocationDecisionStatus.NO_ALLOCATION},
        )
        self.assertEqual(len({decision.decision_set_id for decision in decisions}), 1)
        self.assertEqual(
            {decision.allocated_capital_minor for decision in decisions},
            {0},
        )

    def test_comparator_excluded_candidates_are_not_materialized(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            build_allocation_decisions,
        )

        comparison, allocation_constraints, allocation = _allocation_result(
            (
                _candidate(
                    opportunity_id="winner",
                    cluster_id="same-thesis",
                    expected_net_pnl=600,
                ),
                _candidate(
                    opportunity_id="suppressed",
                    cluster_id="same-thesis",
                    expected_net_pnl=500,
                ),
            )
        )
        decisions = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )

        self.assertEqual(
            tuple(decision.opportunity_ref.id for decision in decisions),
            ("winner",),
        )

    def test_decision_set_and_ids_are_order_independent(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            build_allocation_decisions,
        )

        first = _allocation_result(
            (
                _candidate(opportunity_id="a", cluster_id="cluster-a"),
                _candidate(opportunity_id="b", cluster_id="cluster-b"),
            )
        )
        second = _allocation_result(
            (
                _candidate(opportunity_id="b", cluster_id="cluster-b"),
                _candidate(opportunity_id="a", cluster_id="cluster-a"),
            )
        )
        first_decisions = build_allocation_decisions(
            first[0],
            first[2],
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=first[1],
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )
        second_decisions = build_allocation_decisions(
            second[0],
            second[2],
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=second[1],
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )

        self.assertEqual(first_decisions, second_decisions)
        self.assertEqual(
            {decision.allocation_decision_id for decision in first_decisions},
            {decision.allocation_decision_id for decision in second_decisions},
        )

    def test_serialization_round_trip_preserves_frozen_record(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            allocation_decision_v1_from_dict,
            allocation_decision_v1_to_dict,
            build_allocation_decisions,
        )

        comparison, allocation_constraints, allocation = _allocation_result(
            (_candidate(opportunity_id="round-trip", cluster_id="cluster-round-trip"),)
        )
        decision = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )[0]

        payload = allocation_decision_v1_to_dict(decision)
        self.assertEqual(allocation_decision_v1_from_dict(payload), decision)

    def test_scope_and_point_in_time_validation_fails_closed(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            AllocationPersistenceError,
            build_allocation_decisions,
        )

        comparison, allocation_constraints, allocation = _allocation_result(
            (_candidate(opportunity_id="guarded", cluster_id="cluster-guarded"),)
        )
        with self.assertRaises(AllocationPersistenceError):
            build_allocation_decisions(
                comparison,
                replace(allocation, account_id="other"),
                comparison_constraints=_comparison_constraints(),
                allocation_constraints=allocation_constraints,
                portfolio_snapshot_ref=PORTFOLIO_REF,
            )
        with self.assertRaises(AllocationPersistenceError):
            build_allocation_decisions(
                comparison,
                allocation,
                comparison_constraints=_comparison_constraints(
                    decision_time_ns=DECISION_NS + 1
                ),
                allocation_constraints=allocation_constraints,
                portfolio_snapshot_ref=PORTFOLIO_REF,
            )

    def test_repository_is_idempotent_and_conflicts_on_changed_content(self) -> None:
        from market_platform_foundation.intelligence.opportunity.allocation_persistence import (
            build_allocation_decisions,
        )

        comparison, allocation_constraints, allocation = _allocation_result(
            (_candidate(opportunity_id="persisted", cluster_id="cluster-persisted"),)
        )
        decision = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=_comparison_constraints(),
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=PORTFOLIO_REF,
        )[0]
        repository = InMemoryIntelligenceRepository()

        self.assertEqual(
            repository.put_allocation_decision(decision),
            RepositoryPutResult.INSERTED,
        )
        self.assertEqual(
            repository.put_allocation_decision(decision),
            RepositoryPutResult.ALREADY_PRESENT,
        )
        self.assertEqual(
            repository.get_allocation_decision(decision.allocation_decision_id),
            decision,
        )
        with self.assertRaises(RepositoryConflictError):
            repository.put_allocation_decision(
                replace(decision, portfolio_snapshot_ref=ContractReference(
                    kind="paper_portfolio_snapshot",
                    id="different-snapshot",
                ))
            )

        by_set = repository.get_allocation_decisions_by_set(decision.decision_set_id)
        self.assertEqual(by_set, (decision,))


if __name__ == "__main__":
    unittest.main()
