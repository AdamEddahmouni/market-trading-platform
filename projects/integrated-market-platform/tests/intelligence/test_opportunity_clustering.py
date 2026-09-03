"""TDD coverage for bounded opportunity thesis clustering."""

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
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.opportunity import (
    EconomicAssumptionsV1,
    MoneyMinorUnits,
    OpportunityClusterCandidate,
    OpportunityClusteringRequest,
    OpportunityClusteringError,
    UniversalEconomicAssessmentV1,
    build_opportunity_clusters,
    derive_thesis_identity,
    duplicate_exposure_view,
)
from market_platform_foundation.intelligence.quality.models import AvailabilityState


PIT_NS = 1_000_000
SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _candidate(
    *,
    strategy_id: str,
    opportunity_id: str,
    thesis_id: str | None = None,
    side: OpportunitySide = OpportunitySide.LONG,
    expression_id: str | None = None,
    scope: IntelligenceScope = SCOPE,
    expires_at_ns: int | None = PIT_NS + 100,
    match_expires_at_ns: int | None = PIT_NS + 100,
    sidecar_account_id: str = "acct-1",
    sidecar_mode: str = "PAPER",
    sidecar_assessed_at_ns: int = PIT_NS - 10,
    sidecar_expires_at_ns: int | None = PIT_NS + 100,
    sidecar_scope: IntelligenceScope | None = None,
) -> OpportunityClusterCandidate:
    forecast_ref = ContractReference(kind="forecast", id=f"forecast-{strategy_id}")
    hypothesis_ref = ContractReference(kind="hypothesis", id=f"hypothesis-{strategy_id}")
    metadata = {}
    if thesis_id is not None:
        metadata["underlying_thesis_id"] = thesis_id
    if expression_id is not None:
        metadata["expression_ref"] = expression_id
    opportunity = OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=scope,
        created_at_ns=PIT_NS - 100,
        quality=QUALITY,
        opportunity_type="event",
        side=side,
        valid_until_ns=expires_at_ns,
        source_forecast_refs=(forecast_ref,),
        source_hypothesis_refs=(hypothesis_ref,),
        lineage_refs=(ContractReference(kind="evidence", id=f"evidence-{strategy_id}"),),
        metadata=metadata,
    )
    match = StrategyMatch.create(
        strategy_id=strategy_id,
        strategy_identity_hash=f"hash-{strategy_id}",
        scope=scope,
        decision_time_ns=PIT_NS - 200,
        disposition=StrategyMatchDisposition.MATCHED,
        capability_state=AvailabilityState.AVAILABLE,
        quality=QUALITY,
        source_forecast_refs=(forecast_ref,),
        valid_from_ns=PIT_NS - 300,
        expires_at_ns=match_expires_at_ns,
        context={"account_id": "acct-1", "mode": "PAPER"},
        lineage_refs=(ContractReference(kind="signal", id=f"signal-{strategy_id}"),),
    )
    sidecar = None
    if sidecar_account_id:
        sidecar = UniversalEconomicAssessmentV1.create(
            scope=sidecar_scope or scope,
            account_id=sidecar_account_id,
            mode=sidecar_mode,
            assessed_at_ns=sidecar_assessed_at_ns,
            expires_at_ns=sidecar_expires_at_ns,
            assumptions=EconomicAssumptionsV1(
                assumptions_id="assumptions-v1",
                version="1",
            ),
            expected_net_pnl=MoneyMinorUnits(100, "USD", 2),
        )
    return OpportunityClusterCandidate(
        opportunity=opportunity,
        strategy_match=match,
        economic_assessment=sidecar,
    )


class OpportunityClusteringTests(unittest.TestCase):
    def _request(
        self,
        *candidates: OpportunityClusterCandidate,
    ) -> OpportunityClusteringRequest:
        return OpportunityClusteringRequest(
            account_id="acct-1",
            mode="PAPER",
            decision_time_ns=PIT_NS,
            candidates=candidates,
        )

    def test_same_thesis_across_strategies_groups_and_marks_only_extra_exposure(self) -> None:
        result = build_opportunity_clusters(
            self._request(
                _candidate(
                    strategy_id="strategy-b",
                    opportunity_id="opp-b",
                    thesis_id="earnings-aapl",
                    expression_id="expr-b",
                ),
                _candidate(
                    strategy_id="strategy-a",
                    opportunity_id="opp-a",
                    thesis_id="earnings-aapl",
                    expression_id="expr-a",
                ),
            )
        )

        self.assertEqual(len(result.clusters), 1)
        cluster = result.clusters[0]
        self.assertEqual(cluster.member_strategy_ids, ("strategy-a", "strategy-b"))
        self.assertEqual(cluster.expression_refs[0].id, "expr-a")
        self.assertEqual(cluster.duplicate_count, 1)
        self.assertEqual(len(cluster.members), 2)
        self.assertFalse(cluster.members[0].is_duplicate)
        self.assertTrue(cluster.members[1].is_duplicate)
        self.assertTrue(cluster.reasons)

    def test_distinct_theses_remain_distinct_clusters(self) -> None:
        result = build_opportunity_clusters(
            self._request(
                _candidate(
                    strategy_id="strategy-a",
                    opportunity_id="opp-a",
                    thesis_id="thesis-a",
                ),
                _candidate(
                    strategy_id="strategy-b",
                    opportunity_id="opp-b",
                    thesis_id="thesis-b",
                ),
            )
        )

        self.assertEqual(len(result.clusters), 2)
        self.assertEqual(
            {cluster.thesis_id for cluster in result.clusters},
            {"underlying:thesis-a", "underlying:thesis-b"},
        )

    def test_fallback_identity_uses_opportunity_identity_not_strategy_id(self) -> None:
        left = _candidate(strategy_id="strategy-a", opportunity_id="opp-a")
        right = _candidate(strategy_id="strategy-b", opportunity_id="opp-b")
        right_opportunity = replace(
            right.opportunity,
            source_forecast_refs=left.opportunity.source_forecast_refs,
            source_hypothesis_refs=left.opportunity.source_hypothesis_refs,
        )

        self.assertEqual(
            derive_thesis_identity(left.opportunity),
            derive_thesis_identity(right_opportunity),
        )

    def test_cluster_retains_opportunity_match_forecast_sidecar_and_lineage_refs(self) -> None:
        candidate = _candidate(
            strategy_id="strategy-a",
            opportunity_id="opp-a",
            thesis_id="thesis-a",
            expression_id="expr-a",
        )
        result = build_opportunity_clusters(self._request(candidate))
        member = result.clusters[0].members[0]
        ref_keys = {(ref.kind, ref.id) for ref in member.lineage_refs}

        self.assertEqual(member.economic_assessment_ref.id, candidate.economic_assessment.assessment_id)
        self.assertIn(("opportunity", "opp-a"), ref_keys)
        self.assertIn(("strategy_match", candidate.strategy_match.match_id), ref_keys)
        self.assertIn(("forecast", "forecast-strategy-a"), ref_keys)
        self.assertIn(("hypothesis", "hypothesis-strategy-a"), ref_keys)
        self.assertIn(("universal_economic_assessment", candidate.economic_assessment.assessment_id), ref_keys)
        self.assertIn(("trade_expression", "expr-a"), ref_keys)

    def test_request_resolves_strategy_match_reference_from_supplied_record(self) -> None:
        candidate = _candidate(strategy_id="strategy-a", opportunity_id="opp-a")
        request = OpportunityClusteringRequest(
            account_id="acct-1",
            mode="PAPER",
            decision_time_ns=PIT_NS,
            candidates=(
                OpportunityClusterCandidate(
                    opportunity=candidate.opportunity,
                    strategy_match=ContractReference(
                        kind="strategy_match",
                        id=candidate.strategy_match.match_id,
                    ),
                    economic_assessment=candidate.economic_assessment,
                ),
            ),
            strategy_match_records=(candidate.strategy_match,),
        )

        result = build_opportunity_clusters(request)

        self.assertEqual(
            result.clusters[0].members[0].strategy_match_ref.id,
            candidate.strategy_match.match_id,
        )

    def test_ordering_and_ids_are_deterministic_for_reordered_input(self) -> None:
        left = build_opportunity_clusters(
            self._request(
                _candidate(strategy_id="strategy-b", opportunity_id="opp-b", thesis_id="thesis-b"),
                _candidate(strategy_id="strategy-a", opportunity_id="opp-a", thesis_id="thesis-a"),
            )
        )
        right = build_opportunity_clusters(
            self._request(
                _candidate(strategy_id="strategy-a", opportunity_id="opp-a", thesis_id="thesis-a"),
                _candidate(strategy_id="strategy-b", opportunity_id="opp-b", thesis_id="thesis-b"),
            )
        )

        self.assertEqual(left, right)

    def test_duplicate_view_does_not_rank_allocate_or_collapse_opportunities(self) -> None:
        request = self._request(
            _candidate(strategy_id="strategy-a", opportunity_id="opp-a", thesis_id="thesis-a"),
            _candidate(strategy_id="strategy-b", opportunity_id="opp-b", thesis_id="thesis-a"),
        )
        result = build_opportunity_clusters(request)
        view = duplicate_exposure_view(result)

        self.assertEqual(len(view.members), 2)
        self.assertEqual(
            {entry.opportunity_ref.id for entry in view.members},
            {"opp-a", "opp-b"},
        )
        self.assertFalse(hasattr(view, "allocation"))
        self.assertFalse(hasattr(view, "rank"))
        self.assertFalse(hasattr(view, "score"))
        with self.assertRaises(AttributeError):
            result.clusters[0].duplicate_count = 99  # type: ignore[misc]

    def test_sidecar_account_mode_pit_expiry_and_scope_guards_fail_closed(self) -> None:
        cases = (
            _candidate(
                strategy_id="bad-account",
                opportunity_id="bad-account",
                sidecar_account_id="other-account",
            ),
            _candidate(
                strategy_id="bad-mode",
                opportunity_id="bad-mode",
                sidecar_mode="ACTUAL_LIVE",
            ),
            _candidate(
                strategy_id="bad-pit",
                opportunity_id="bad-pit",
                sidecar_assessed_at_ns=PIT_NS + 1,
            ),
            _candidate(
                strategy_id="bad-expiry",
                opportunity_id="bad-expiry",
                sidecar_expires_at_ns=PIT_NS,
            ),
            _candidate(
                strategy_id="bad-scope",
                opportunity_id="bad-scope",
                sidecar_scope=IntelligenceScope(
                    instrument_ids=("MSFT",), context_id="regular"
                ),
            ),
        )
        for candidate in cases:
            with self.subTest(strategy_id=candidate.strategy_match.strategy_id):
                with self.assertRaises(OpportunityClusteringError):
                    build_opportunity_clusters(self._request(candidate))


if __name__ == "__main__":
    unittest.main()
