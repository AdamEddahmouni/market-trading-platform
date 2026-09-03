"""Focused tests for the bounded universal strategy scan."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    StrategyConditionResult,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality.models import (
    AvailabilityState,
    CapabilityAssessment,
    CapabilityDimensions,
    CompletenessState,
    ConflictState,
    FreshnessState,
    IntelligenceCapability,
    SupportState,
    ValidityState,
)
from market_platform_foundation.intelligence.quality.models import QualityAssessment
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.providers.planner import ProviderPolicy, QueryPlanner
from market_platform_foundation.providers.registry import (
    CapabilityDescriptor,
    ProviderDescriptor,
    ProviderRegistry,
)
from market_platform_foundation.strategy.scanning import (
    CapabilityContextSnapshot,
    CheapScreenResult,
    PointInTimeUniverse,
    ScanBudget,
    ScanRequest,
    ScanScope,
    ScanTrigger,
    ScanTriggerType,
    StrategyEvaluationContext,
    StrategyEvaluationResult,
    StrategyRegistration,
    UniversalStrategyScanner,
)
from market_platform_foundation.strategy.strategy_spec import StrategyDefinition


PIT_NS = 1_700_000_000_000_000_000


def _instrument(symbol: str, asset_class: str = "EQUITY") -> InstrumentIdentity:
    return InstrumentIdentity("canonical", symbol, asset_class, "XNYS", "USD")


def _provider_registry(*capabilities: str) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        ProviderDescriptor(
            provider_id="fixture",
            display_name="Fixture",
            capabilities=tuple(
                CapabilityDescriptor(
                    capability_id=capability,
                    asset_classes=("EQUITY",),
                    venues=("XNYS",),
                    interfaces=("fixture",),
                    supports_history=True,
                    supports_pit=True,
                    freshness_sla_ns=1_000_000,
                    license_class="RESEARCH_ONLY",
                    rate_policy_id="fixture/1",
                    normalizer_version="fixture/1",
                )
                for capability in capabilities
            ),
            health_state="HEALTHY",
            credential_refs=(),
            schema_versions=("1.0",),
            priority=1,
        )
    )
    return registry


def _capability_snapshot(*, good: bool = True) -> CapabilityContextSnapshot:
    assessments = ()
    if good:
        assessments = (
            CapabilityAssessment(
                provider_id="fixture",
                capability=IntelligenceCapability.QUOTES,
                instrument_id=None,
                dimensions=CapabilityDimensions(
                    support=SupportState.SUPPORTED,
                    availability=AvailabilityState.AVAILABLE,
                    freshness=FreshnessState.FRESH,
                    completeness=CompletenessState.COMPLETE,
                    validity=ValidityState.VALID,
                    conflict=ConflictState.NONE,
                    temporally_legal=True,
                ),
                quality_state=QualityState.GOOD,
            ),
        )
    return CapabilityContextSnapshot(
        snapshot_id="snapshot-1",
        as_of_time_ns=PIT_NS,
        quality_assessment=QualityAssessment(
            decision_time_ns=PIT_NS,
            capability_assessments=assessments,
        ),
        source_snapshot_ref=ContractReference(kind="snapshot", id="snapshot-1"),
        context={"session": "REGULAR", "regime": "RISK_ON"},
    )


def _strategy(strategy_id: str, *, asset_class: str = "EQUITY") -> StrategyDefinition:
    return StrategyDefinition(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis=strategy_id,
        evidence_requirements=("quotes",),
        instrument_id=strategy_id,
        family="TREND",
        style="MOMENTUM",
        asset_class=asset_class,
        timeframe="5M",
    )


class UniversalStrategyScannerTests(unittest.TestCase):
    def test_staged_scan_filters_before_evaluation_and_persists_deterministically(self) -> None:
        evaluator_calls: list[str] = []
        screen_calls: list[str] = []

        def screen(candidate: StrategyEvaluationContext) -> CheapScreenResult:
            screen_calls.append(candidate.instrument.instrument_id)
            return CheapScreenResult(
                eligible=candidate.instrument.instrument_id == "AAPL",
                reason="SYMBOL_NOT_IN_CHEAP_SET",
            )

        def evaluate(candidate: StrategyEvaluationContext) -> StrategyEvaluationResult:
            evaluator_calls.append(candidate.instrument.instrument_id)
            return StrategyEvaluationResult(
                disposition=StrategyMatchDisposition.MATCHED,
                condition_results=(
                    StrategyConditionResult(condition_id="trend", matched=True),
                ),
            )

        registration = StrategyRegistration(
            strategy_id="momentum-5m",
            definition=_strategy("momentum-5m"),
            required_capabilities=("QUOTES",),
            cheap_screen=screen,
            evaluator=evaluate,
        )
        rejected_registration = StrategyRegistration(
            strategy_id="crypto-only",
            definition=_strategy("crypto-only", asset_class="CRYPTO"),
            required_capabilities=("QUOTES",),
            cheap_screen=screen,
            evaluator=evaluate,
        )
        request = ScanRequest(
            universe=PointInTimeUniverse(
                as_of_time_ns=PIT_NS,
                instruments=(_instrument("MSFT"), _instrument("AAPL")),
            ),
            capability_snapshot=_capability_snapshot(),
            strategies=(rejected_registration, registration),
            scope=ScanScope(account_id="acct-1", mode="paper"),
            trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
            decision_time_ns=PIT_NS,
            expires_at_ns=PIT_NS + 60_000_000_000,
            budget=ScanBudget(max_evaluations=4, max_cost_units=4),
        )
        repository = InMemoryIntelligenceRepository()

        first = UniversalStrategyScanner(
            query_planner=QueryPlanner(
                _provider_registry("QUOTES"),
                {"fixture": ProviderPolicy(allowed_license_classes=("RESEARCH_ONLY",))},
            ),
            repository=repository,
        ).run(request)

        self.assertEqual(first.run_id, UniversalStrategyScanner.run_id_for(request))
        self.assertEqual(evaluator_calls, ["AAPL"])
        self.assertEqual(screen_calls, ["AAPL", "MSFT"])
        self.assertEqual(len(first.matches), 4)
        self.assertEqual(
            sum(match.disposition == StrategyMatchDisposition.MATCHED for match in first.matches),
            1,
        )
        self.assertEqual(
            sum(match.disposition == StrategyMatchDisposition.REJECTED for match in first.matches),
            3,
        )
        self.assertEqual(first.counters.stage_a_rejected, 2)
        self.assertEqual(first.counters.stage_b_screened, 2)
        self.assertEqual(first.counters.evaluated, 1)
        self.assertEqual(first.counters.matched, 1)
        self.assertEqual(first.counters.rejected, 3)
        self.assertEqual(first.matches[0].context["account_id"], "acct-1")
        self.assertEqual(first.matches[0].context["mode"], "paper")
        self.assertEqual(repository.get_strategy_match(first.matches[0].match_id), first.matches[0])

        second = UniversalStrategyScanner(
            query_planner=QueryPlanner(
                _provider_registry("QUOTES"),
                {"fixture": ProviderPolicy(allowed_license_classes=("RESEARCH_ONLY",))},
            ),
            repository=repository,
        ).run(request)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.matches, second.matches)

    def test_scan_records_unavailable_and_abstained_but_counts_evaluator_failures(self) -> None:
        calls: list[str] = []

        def evaluate(candidate: StrategyEvaluationContext) -> StrategyEvaluationResult:
            calls.append(candidate.registration.strategy_id)
            raise RuntimeError("coarse evaluator failure")

        unavailable = StrategyRegistration(
            strategy_id="depth",
            definition=_strategy("depth"),
            required_capabilities=("DEPTH",),
            evaluator=evaluate,
        )
        abstained = StrategyRegistration(
            strategy_id="quotes-unknown",
            definition=_strategy("quotes-unknown"),
            required_capabilities=("QUOTES",),
            failure_action="ABSTAIN",
            evaluator=evaluate,
        )
        request = ScanRequest(
            universe=PointInTimeUniverse(PIT_NS, (_instrument("AAPL"),)),
            capability_snapshot=_capability_snapshot(good=False),
            strategies=(unavailable, abstained),
            scope=ScanScope(account_id="acct-2", mode="demo"),
            trigger=ScanTrigger(ScanTriggerType.PERIODIC, {"interval_ns": 60_000_000_000}),
            decision_time_ns=PIT_NS,
            expires_at_ns=PIT_NS + 60_000_000_000,
            budget=ScanBudget(max_evaluations=2, max_cost_units=2),
        )

        result = UniversalStrategyScanner(
            query_planner=QueryPlanner(
                _provider_registry("QUOTES"),
                {"fixture": ProviderPolicy(allowed_license_classes=("RESEARCH_ONLY",))},
            ),
            repository=InMemoryIntelligenceRepository(),
        ).run(request)

        self.assertEqual(calls, [])
        self.assertEqual(
            {match.disposition for match in result.matches},
            {StrategyMatchDisposition.UNAVAILABLE, StrategyMatchDisposition.ABSTAINED},
        )
        self.assertEqual(result.counters.unavailable, 1)
        self.assertEqual(result.counters.abstained, 1)
        self.assertEqual(result.counters.evaluation_failures, 0)
        self.assertEqual(result.diagnostics, ())

        failing_registration = StrategyRegistration(
            strategy_id="failing",
            definition=_strategy("failing"),
            required_capabilities=(),
            evaluator=evaluate,
        )
        failing_request = request.__class__(
            universe=request.universe,
            capability_snapshot=request.capability_snapshot,
            strategies=(failing_registration,),
            scope=request.scope,
            trigger=ScanTrigger(ScanTriggerType.EVENT, {"event_id": "event-1"}),
            decision_time_ns=request.decision_time_ns,
            expires_at_ns=request.expires_at_ns,
            budget=request.budget,
        )
        failed = UniversalStrategyScanner(
            query_planner=None,
            repository=InMemoryIntelligenceRepository(),
        ).run(failing_request)
        self.assertEqual(failed.matches, ())
        self.assertEqual(failed.counters.evaluation_failures, 1)
        self.assertTrue(any(item.startswith("EVALUATOR_FAILURE:failing") for item in failed.diagnostics))

    def test_budget_expiry_and_scope_are_explicit(self) -> None:
        registration = StrategyRegistration(
            strategy_id="budgeted",
            definition=_strategy("budgeted"),
            evaluator=lambda _: StrategyEvaluationResult(
                disposition=StrategyMatchDisposition.MATCHED,
            ),
            cost_units=2,
        )
        request = ScanRequest(
            universe=PointInTimeUniverse(PIT_NS, (_instrument("AAPL"),)),
            capability_snapshot=_capability_snapshot(),
            strategies=(registration,),
            scope=ScanScope(account_id="acct-3", mode="live"),
            trigger=ScanTrigger(ScanTriggerType.SCHEDULED, {"schedule_id": "daily-open"}),
            decision_time_ns=PIT_NS,
            expires_at_ns=PIT_NS + 1,
            budget=ScanBudget(max_evaluations=0, max_cost_units=1),
        )
        result = UniversalStrategyScanner(
            query_planner=None,
            repository=InMemoryIntelligenceRepository(),
        ).run(request)

        self.assertEqual(result.counters.budget_exhausted, 1)
        self.assertEqual(result.matches[0].disposition, StrategyMatchDisposition.UNAVAILABLE)
        self.assertTrue(result.matches[0].is_valid_at(PIT_NS))
        self.assertEqual(result.matches[0].context["trigger_type"], "SCHEDULED")
        self.assertNotEqual(
            result.run_id,
            UniversalStrategyScanner.run_id_for(
                request.__class__(
                    universe=request.universe,
                    capability_snapshot=request.capability_snapshot,
                    strategies=request.strategies,
                    scope=ScanScope(account_id="other", mode="live"),
                    trigger=request.trigger,
                    decision_time_ns=request.decision_time_ns,
                    expires_at_ns=request.expires_at_ns,
                    budget=request.budget,
                )
            ),
        )

    def test_evaluator_dispositions_are_retained_as_persisted_matches(self) -> None:
        dispositions = (
            ("matched", StrategyMatchDisposition.MATCHED, {}),
            (
                "abstained",
                StrategyMatchDisposition.ABSTAINED,
                {"abstention_reasons": ("TEST_ABSTAINED",)},
            ),
            (
                "rejected",
                StrategyMatchDisposition.REJECTED,
                {"rejection_reasons": ("TEST_REJECTED",)},
            ),
            (
                "unavailable",
                StrategyMatchDisposition.UNAVAILABLE,
                {"unavailability_reasons": ("TEST_UNAVAILABLE",)},
            ),
        )
        registrations = tuple(
            StrategyRegistration(
                strategy_id=strategy_id,
                definition=_strategy(strategy_id),
                evaluator=lambda _, disposition=disposition, reasons=reasons: StrategyEvaluationResult(
                    disposition=disposition,
                    **reasons,
                ),
            )
            for strategy_id, disposition, reasons in dispositions
        )
        request = ScanRequest(
            universe=PointInTimeUniverse(PIT_NS, (_instrument("AAPL"),)),
            capability_snapshot=_capability_snapshot(),
            strategies=registrations,
            scope=ScanScope(account_id="acct-retained", mode="paper"),
            trigger=ScanTrigger(ScanTriggerType.EVENT, {"event_id": "retained"}),
            decision_time_ns=PIT_NS,
            expires_at_ns=PIT_NS + 60_000_000_000,
            budget=ScanBudget(max_evaluations=4, max_cost_units=4),
        )
        repository = InMemoryIntelligenceRepository()

        result = UniversalStrategyScanner(
            query_planner=None,
            repository=repository,
        ).run(request)

        by_strategy = {match.strategy_id: match for match in result.matches}
        self.assertEqual(
            {strategy_id: by_strategy[strategy_id].disposition for strategy_id, _, _ in dispositions},
            {strategy_id: disposition for strategy_id, disposition, _ in dispositions},
        )
        self.assertEqual(
            by_strategy["abstained"].abstention_reasons,
            ("TEST_ABSTAINED",),
        )
        self.assertEqual(
            by_strategy["rejected"].rejection_reasons,
            ("TEST_REJECTED",),
        )
        self.assertEqual(
            by_strategy["unavailable"].unavailability_reasons,
            ("TEST_UNAVAILABLE",),
        )
        for match in by_strategy.values():
            self.assertEqual(repository.get_strategy_match(match.match_id), match)


if __name__ == "__main__":
    unittest.main()
