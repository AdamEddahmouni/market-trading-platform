"""Orchestration for one deterministic strategy-to-Paper round trip."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from ..intelligence.contracts import (
    ContractReference,
    ForecastV1,
    OpportunitySide,
    OpportunityV1,
)
from ..intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from ..intelligence.execution import (
    ExecutionPolicyV1,
    MarketQuoteV1,
    PaperExecutionOrchestrator,
    PaperExecutionResult,
    PaperPortfolioSnapshotV1,
    RiskDecisionKind,
)
from ..intelligence.opportunity import (
    CapitalAllocationConstraintsV1,
    CapitalAllocationDecisionV1,
    ComparisonConstraintsV1,
    GlobalOpportunityComparator,
    OpportunityClusterCandidate,
    OpportunityClusteringRequest,
    OpportunityComparisonCandidateV1,
    allocate_capital,
    bridge_strategy_match_to_opportunity,
    build_allocation_decisions,
    build_opportunity_clusters,
)
from ..intelligence.outcomes import (
    OutcomeSettlementService,
    PredictionLedgerService,
    SettlementMode,
    SettlementResult,
    SettlementStatus,
)
from ..intelligence.persistence.repository import IntelligenceRepository
from ..portfolio.attribution import StrategyAttributionV1
from ..portfolio.attribution_materializer import (
    get_latest_complete_strategy_attribution,
    materialize_strategy_attribution,
)
from ..paper.ledger import PaperExecutionLedger
from .learning import (
    LearningEligibility,
    LearningJoinV1,
    LearningLabelState,
    LearningObservationV1,
    LearningSettlementState,
    ResearchHandoffV1,
    emit_research_handoff,
    evaluate_learning_join,
)
from .scanning import ScanRequest, ScanResult, UniversalStrategyScanner


class StrategyRuntimeError(ValueError):
    """A runtime request crossed a governed stage boundary."""


@dataclass(frozen=True, slots=True)
class RuntimeStageDiagnostic:
    """Bounded, structured diagnostic for one runtime stage."""

    stage: str
    status: str
    reason_codes: tuple[str, ...] = ()
    ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reason_codes",
            tuple(sorted({str(value) for value in self.reason_codes if str(value)})),
        )
        object.__setattr__(
            self,
            "ids",
            {str(key): str(value) for key, value in sorted(self.ids.items()) if value is not None},
        )


@dataclass(frozen=True, slots=True)
class StrategyRuntimeResult:
    """Ephemeral runtime receipt; persisted records remain authoritative."""

    status: str
    scan_id: str | None = None
    strategy_id: str | None = None
    strategy_identity_hash: str | None = None
    stage_ids: Mapping[str, str] = field(default_factory=dict)
    quantities: Mapping[str, int] = field(default_factory=dict)
    fill_ids: tuple[str, ...] = ()
    attribution_id: str | None = None
    diagnostics: tuple[RuntimeStageDiagnostic, ...] = ()
    ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stage_ids",
            {str(key): str(value) for key, value in sorted(self.stage_ids.items()) if value is not None},
        )
        object.__setattr__(
            self,
            "quantities",
            {str(key): int(value) for key, value in sorted(self.quantities.items())},
        )
        object.__setattr__(self, "fill_ids", tuple(sorted({str(value) for value in self.fill_ids})))
        object.__setattr__(
            self,
            "ids",
            {str(key): str(value) for key, value in sorted(self.ids.items()) if value is not None},
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(self.diagnostics),
        )


@dataclass(frozen=True, slots=True)
class StrategyRuntimeReconstruction:
    """Authoritative records and projections joined by persisted references."""

    allocation_decision: CapitalAllocationDecisionV1
    strategy_match: StrategyMatch | None
    forecast: ForecastV1 | None
    economic_assessment: Any | None
    opportunity: OpportunityV1 | None
    proposal: Any | None
    risk_decision: Any | None
    orders: tuple[Mapping[str, Any], ...]
    fills: tuple[Mapping[str, Any], ...]
    account: Mapping[str, Any]
    attribution: StrategyAttributionV1 | None
    prediction_ledger_entry: Any | None = None
    prediction_outcome: Any | None = None
    learning_evaluation: Any | None = None


@dataclass(frozen=True, slots=True)
class StrategyLearningResult:
    """Ephemeral outcome/learning receipt; canonical records remain authoritative."""

    settlement_results: tuple[SettlementResult, ...] = ()
    observation: LearningObservationV1 | None = None
    join: LearningJoinV1 | None = None
    learning_evaluation: Any | None = None
    handoff: ResearchHandoffV1 | None = None
    eligibility: LearningEligibility = LearningEligibility.INCONCLUSIVE
    prediction_quality: Any | None = None
    trading_quality: Any | None = None
    prediction_outcome: Any | None = None
    trading_attribution: StrategyAttributionV1 | None = None
    diagnostics: tuple[str, ...] = ()

    @property
    def evaluation(self) -> Any | None:
        """Compatibility alias for consumers that call this an evaluation."""
        return self.learning_evaluation

    @property
    def research_handoff(self) -> ResearchHandoffV1 | None:
        return self.handoff


class StrategyPaperRuntime:
    """Coordinate existing strategy, intelligence, risk, Paper, and P&L authorities."""

    def __init__(
        self,
        *,
        repository: IntelligenceRepository,
        scanner: UniversalStrategyScanner,
        forecast_resolver: Callable[[StrategyMatch], ForecastV1],
        champion_at_forecast: Any,
        champion_at_opportunity: Any,
        opportunity_policy: Any,
        opportunity_context: Any,
        economic_assessment: Any,
        comparison_constraints: ComparisonConstraintsV1 | Mapping[str, Any],
        allocation_constraints: CapitalAllocationConstraintsV1 | Mapping[str, Any],
        execution_policy: ExecutionPolicyV1,
        portfolio: PaperPortfolioSnapshotV1,
        quote: MarketQuoteV1,
        ledger: PaperExecutionLedger,
        bars: list[dict[str, Any]],
        execution_authority: str,
        paper_orchestrator: PaperExecutionOrchestrator | None = None,
        comparator: GlobalOpportunityComparator | None = None,
        allocator: Any | None = None,
        prediction_ledger_service: PredictionLedgerService | None = None,
        outcome_settlement_service: OutcomeSettlementService | None = None,
        learning_policy: Any | None = None,
    ) -> None:
        self.repository = repository
        self.scanner = scanner
        self.forecast_resolver = forecast_resolver
        self.champion_at_forecast = champion_at_forecast
        self.champion_at_opportunity = champion_at_opportunity
        self.opportunity_policy = opportunity_policy
        self.opportunity_context = opportunity_context
        self.economic_assessment = economic_assessment
        self.comparison_constraints = comparison_constraints
        self.allocation_constraints = allocation_constraints
        self.execution_policy = execution_policy
        self.portfolio = portfolio
        self.quote = quote
        self.ledger = ledger
        self.bars = list(bars)
        self.execution_authority = execution_authority
        self.paper_orchestrator = paper_orchestrator or PaperExecutionOrchestrator()
        self.comparator = comparator or GlobalOpportunityComparator()
        self.allocator = allocator
        self.prediction_ledger_service = prediction_ledger_service or PredictionLedgerService(repository)
        self.outcome_settlement_service = outcome_settlement_service or OutcomeSettlementService(repository)
        self.learning_policy = learning_policy
        self._entry: dict[str, Any] = {}

    def run_entry(
        self,
        request: ScanRequest,
        *,
        strategy_id: str | None = None,
        portfolio: PaperPortfolioSnapshotV1 | None = None,
        quote: MarketQuoteV1 | None = None,
        bars: list[dict[str, Any]] | None = None,
    ) -> StrategyRuntimeResult:
        """Run one bounded scan-to-fill entry through existing authorities."""
        scan = self.scanner.run(request)
        diagnostics: list[RuntimeStageDiagnostic] = [
            RuntimeStageDiagnostic("scan", "SCANNED", ids={"scan_id": scan.scan_id, "run_id": scan.run_id})
        ]
        match = self._select_match(scan, strategy_id)
        if match is None:
            status = self._scan_stop_status(scan)
            diagnostics.append(
                RuntimeStageDiagnostic(
                    "strategy",
                    status,
                    reason_codes=self._scan_reasons(scan),
                    ids={"scan_id": scan.scan_id},
                )
            )
            return StrategyRuntimeResult(
                status=status,
                scan_id=scan.scan_id,
                diagnostics=tuple(diagnostics),
            )

        forecast = self._resolve_forecast(match, request)
        if forecast is None:
            diagnostics.append(
                RuntimeStageDiagnostic(
                    "forecast",
                    "FORECAST_UNAVAILABLE",
                    reason_codes=("FORECAST_RESOLUTION_FAILED",),
                    ids={"strategy_match_id": match.match_id},
                )
            )
            return StrategyRuntimeResult(
                status="FORECAST_UNAVAILABLE",
                scan_id=scan.scan_id,
                strategy_id=match.strategy_id,
                strategy_identity_hash=match.strategy_identity_hash,
                diagnostics=tuple(diagnostics),
            )

        match = self._attach_forecast_reference(match, forecast)
        self.repository.put_strategy_match(match)
        self.repository.put_forecast(forecast)
        forecast_registration = self.prediction_ledger_service.register_forecast(
            forecast,
            now_ns=request.decision_time_ns,
            mode=SettlementMode.COUNTERFACTUAL,
            scenario_id=self._scenario_id(),
        )
        if not hasattr(forecast_registration, "ledger_entry_id"):
            diagnostics.append(
                RuntimeStageDiagnostic(
                    "forecast",
                    "FORECAST_UNAVAILABLE",
                    reason_codes=("FORECAST_REGISTRATION_FAILED",),
                    ids={"forecast_id": forecast.forecast_id},
                )
            )
            return self._result(
                "FORECAST_UNAVAILABLE",
                scan=scan,
                match=match,
                forecast=forecast,
                diagnostics=diagnostics,
            )

        diagnostics.append(
            RuntimeStageDiagnostic(
                "forecast",
                "REGISTERED",
                ids={
                    "strategy_match_id": match.match_id,
                    "forecast_id": forecast.forecast_id,
                    "prediction_ledger_entry_id": forecast_registration.ledger_entry_id,
                },
            )
        )
        self._entry.update(
            {
                "match": match,
                "forecast": forecast,
                "prediction_ledger_entry": forecast_registration,
            }
        )
        bridge = bridge_strategy_match_to_opportunity(
            match=match,
            forecast=forecast,
            champion_at_forecast=self.champion_at_forecast,
            champion_at_opportunity=self.champion_at_opportunity,
            policy=self.opportunity_policy,
            context=self.opportunity_context,
            opportunity_decision_time_ns=request.decision_time_ns,
            economic_assessment=self._resolve_economics(match, forecast),
            repository=self.repository,
        )
        if bridge.opportunity is None:
            diagnostics.append(
                RuntimeStageDiagnostic(
                    "opportunity",
                    "OPPORTUNITY_SUPPRESSED",
                    reason_codes=tuple(
                        getattr(reason, "value", str(reason))
                        for reason in bridge.assessment.reason_codes
                    ),
                    ids={
                        "strategy_match_id": match.match_id,
                        "forecast_id": forecast.forecast_id,
                        "economic_assessment_id": (
                            bridge.economic_assessment.assessment_id
                            if bridge.economic_assessment is not None
                            else None
                        ),
                    },
                )
            )
            return self._result(
                "OPPORTUNITY_SUPPRESSED",
                scan=scan,
                match=match,
                forecast=forecast,
                diagnostics=diagnostics,
            )

        opportunity = bridge.opportunity
        sidecar = bridge.economic_assessment
        if sidecar is None:
            return self._result(
                "NOT_ACTIONABLE",
                scan=scan,
                match=match,
                forecast=forecast,
                opportunity=opportunity,
                diagnostics=diagnostics
                + [
                    RuntimeStageDiagnostic(
                        "economics",
                        "NOT_ACTIONABLE",
                        reason_codes=("ECONOMIC_ASSESSMENT_REQUIRED",),
                    )
                ],
            )
        cluster = build_opportunity_clusters(
            OpportunityClusteringRequest(
                account_id=request.scope.account_id,
                mode=request.scope.mode,
                decision_time_ns=request.decision_time_ns,
                candidates=(
                    OpportunityClusterCandidate(
                        opportunity=opportunity,
                        strategy_match=match,
                        economic_assessment=sidecar,
                    ),
                ),
            )
        ).clusters[0]
        comparison_constraints = self._comparison_constraints(request)
        allocation_constraints = self._allocation_constraints(request)
        comparison = self.comparator.compare(
            comparison_constraints,
            (
                OpportunityComparisonCandidateV1(
                    cluster_id=cluster.cluster_id,
                    opportunity=opportunity,
                    economic_assessment=sidecar,
                ),
            ),
        )
        allocation = (
            self.allocator.allocate(comparison, allocation_constraints)
            if self.allocator is not None
            else allocate_capital(
                comparison=comparison,
                constraints=allocation_constraints,
            )
        )
        portfolio = portfolio or self.portfolio
        self.repository.put_paper_portfolio_snapshot(portfolio)
        decisions = build_allocation_decisions(
            comparison,
            allocation,
            comparison_constraints=comparison_constraints,
            allocation_constraints=allocation_constraints,
            portfolio_snapshot_ref=ContractReference(
                kind="paper_portfolio_snapshot",
                id=portfolio.snapshot_id,
            ),
            strategy_match_refs={opportunity.opportunity_id: ContractReference(
                kind="strategy_match", id=match.match_id
            )},
            forecast_refs={opportunity.opportunity_id: (
                ContractReference(kind="forecast", id=forecast.forecast_id),
            )},
        )
        for decision in decisions:
            self.repository.put_allocation_decision(decision)
        if not decisions:
            return self._result(
                "NOT_ALLOCATED",
                scan=scan,
                match=match,
                forecast=forecast,
                opportunity=opportunity,
                diagnostics=diagnostics
                + [
                    RuntimeStageDiagnostic(
                        "allocation",
                        "NOT_ALLOCATED",
                        reason_codes=("NO_ALLOCATION",),
                    )
                ],
            )
        allocation_decision = next(
            (item for item in decisions if item.status.value == "SELECTED"),
            None,
        )
        if allocation_decision is None:
            return self._result(
                "NOT_ALLOCATED",
                scan=scan,
                match=match,
                forecast=forecast,
                opportunity=opportunity,
                allocation_decision=decisions[0],
                diagnostics=diagnostics
                + [
                    RuntimeStageDiagnostic(
                        "allocation",
                        "NOT_ALLOCATED",
                        reason_codes=tuple(
                            code.value for code in decisions[0].reason_codes
                        ),
                        ids={"decision_set_id": decisions[0].decision_set_id},
                    )
                ],
            )
        lineage = self._entry_lineage(
            allocation_decision=allocation_decision,
            match=match,
            forecast=forecast,
            opportunity=opportunity,
            cluster_id=cluster.cluster_id,
            sidecar=sidecar,
            portfolio=portfolio,
        )
        execution = self.paper_orchestrator.prepare_paper(
            opportunity=opportunity,
            policy=self.execution_policy,
            portfolio=portfolio,
            quote=quote or self.quote,
            ledger=self.ledger,
            decision_time_ns=request.decision_time_ns,
            instrument_id=self._instrument_id(opportunity),
            symbol=self._symbol(opportunity),
            execution_authority=self.execution_authority,
            lineage_refs=lineage,
            allocation_decision=allocation_decision,
        )
        self.repository.put_trade_proposal(execution.proposal)
        self.repository.put_risk_decision(execution.risk_decision)
        if execution.risk_decision.decision in {
            RiskDecisionKind.REJECT,
            RiskDecisionKind.FAIL_CLOSED,
        }:
            return self._result(
                "RISK_REJECTED",
                scan=scan,
                match=match,
                forecast=forecast,
                opportunity=opportunity,
                allocation_decision=allocation_decision,
                proposal=execution.proposal,
                risk_decision=execution.risk_decision,
                diagnostics=diagnostics
                + [
                    RuntimeStageDiagnostic(
                        "risk",
                        "RISK_REJECTED",
                        reason_codes=tuple(
                            code.value for code in execution.risk_decision.reason_codes
                        ),
                        ids={"risk_decision_id": execution.risk_decision.risk_decision_id},
                    )
                ],
            )
        result = self.paper_orchestrator.submit_prepared(
            prepared=execution,
            ledger=self.ledger,
            bars=list(bars if bars is not None else self.bars),
        )
        fill_ids = self._result_fill_ids(result)
        attribution = (
            self._attribution_for_fill_ids(allocation_decision, fill_ids)
            if result.paper_submit and result.paper_submit.get("duplicate")
            else None
        ) or self._materialize(
            allocation_decision,
            proposal=execution.proposal,
            risk_decision=execution.risk_decision,
        )
        status = "FILLED" if fill_ids else "EXECUTION_FAILED"
        self._entry = {
            "allocation_decision": allocation_decision,
            "match": match,
            "forecast": forecast,
            "opportunity": opportunity,
            "proposal": execution.proposal,
            "risk_decision": execution.risk_decision,
            "attribution": attribution,
            "prediction_ledger_entry": forecast_registration,
            "paper_result": result,
        }
        return self._result(
            status,
            scan=scan,
            match=match,
            forecast=forecast,
            opportunity=opportunity,
            allocation_decision=allocation_decision,
            proposal=execution.proposal,
            risk_decision=execution.risk_decision,
            attribution=attribution,
            fill_ids=fill_ids,
            paper_result=result,
            diagnostics=diagnostics
            + [
                RuntimeStageDiagnostic(
                    "execution",
                    status,
                    ids={
                        "allocation_decision_id": allocation_decision.allocation_decision_id,
                        "trade_proposal_id": execution.proposal.proposal_id,
                        "risk_decision_id": execution.risk_decision.risk_decision_id,
                        "order_id": self._order_id(result),
                        "attribution_id": attribution.attribution_id if attribution else None,
                    },
                )
            ],
        )

    def close(
        self,
        *,
        opportunity: OpportunityV1,
        decision_time_ns: int,
        allocation_decision_id: str | None = None,
        portfolio: PaperPortfolioSnapshotV1 | None = None,
        quote: MarketQuoteV1 | None = None,
        bars: list[dict[str, Any]] | None = None,
    ) -> StrategyRuntimeResult:
        """Submit one supplied canonical SELL opportunity as a bounded close."""
        allocation = self._resolve_entry_allocation(allocation_decision_id)
        if allocation is None:
            return StrategyRuntimeResult(
                status="NOT_ALLOCATED",
                diagnostics=(
                    RuntimeStageDiagnostic(
                        "close",
                        "NOT_ALLOCATED",
                        reason_codes=("ENTRY_ALLOCATION_NOT_FOUND",),
                    ),
                ),
            )
        if opportunity.side != OpportunitySide.SHORT:
            return self._result(
                "OPPORTUNITY_SUPPRESSED",
                allocation_decision=allocation,
                diagnostics=[
                    RuntimeStageDiagnostic(
                        "close",
                        "OPPORTUNITY_SUPPRESSED",
                        reason_codes=("CLOSE_SELL_OPPORTUNITY_REQUIRED",),
                    )
                ],
            )
        entry = self._entry
        match = entry.get("match") or self.repository.get_strategy_match(
            allocation.strategy_match_ref.id if allocation.strategy_match_ref else ""
        )
        forecast = self._get_forecast(allocation)
        self._validate_close_scope(opportunity, allocation, match, decision_time_ns)
        self.repository.put_opportunity(opportunity)
        active_portfolio = portfolio or self.portfolio
        close_quantity = self._filled_quantity(entry.get("paper_result"))
        if close_quantity <= 0:
            close_quantity = sum(
                int(fill.get("fill_quantity", 0))
                for fill in self.ledger.project_fills()
                if _contains_reference(
                    fill,
                    "allocation_decision",
                    allocation.allocation_decision_id,
                )
            )
        current_position = sum(
            int(position.get("quantity", 0))
            for position in self.ledger.project_positions()
            if str(position.get("instrument_id", "")).upper()
            == self._instrument_id(opportunity).upper()
            and int(position.get("quantity", 0)) > 0
        )
        close_quantity = min(close_quantity, current_position)
        if close_quantity <= 0:
            return self._result(
                "NOT_ALLOCATED",
                allocation_decision=allocation,
                match=match,
                forecast=forecast,
                opportunity=opportunity,
                diagnostics=[
                    RuntimeStageDiagnostic(
                        "close",
                        "NOT_ALLOCATED",
                        reason_codes=("ENTRY_FILL_NOT_FOUND",),
                    )
                ],
            )
        entry_lineage = self._entry_lineage_from_allocation(
            allocation,
            match=match,
            forecast=forecast,
            opportunity=entry.get("opportunity"),
            portfolio=active_portfolio,
        )
        execution = self.paper_orchestrator.close_paper(
            opportunity=opportunity,
            policy=self.execution_policy,
            portfolio=active_portfolio,
            quote=quote or self.quote,
            ledger=self.ledger,
            bars=list(bars if bars is not None else self.bars),
            decision_time_ns=decision_time_ns,
            instrument_id=self._instrument_id(opportunity),
            symbol=self._symbol(opportunity),
            execution_authority=self.execution_authority,
            close_quantity=close_quantity,
            entry_lineage_refs=entry_lineage,
        )
        if execution.proposal is not None:
            self.repository.put_trade_proposal(execution.proposal)
        if execution.risk_decision is not None:
            self.repository.put_risk_decision(execution.risk_decision)
        fill_ids = self._result_fill_ids(execution)
        attribution = (
            self._attribution_for_fill_ids(allocation, fill_ids)
            if execution.paper_submit and execution.paper_submit.get("duplicate")
            else None
        ) or self._materialize(
            allocation,
            proposal=execution.proposal,
            risk_decision=execution.risk_decision,
        )
        status = "CLOSED" if fill_ids else (
            "RISK_REJECTED"
            if execution.risk_decision
            and execution.risk_decision.decision in {
                RiskDecisionKind.REJECT,
                RiskDecisionKind.FAIL_CLOSED,
            }
            else "EXECUTION_FAILED"
        )
        return self._result(
            status,
            allocation_decision=allocation,
            match=match,
            forecast=forecast,
            opportunity=opportunity,
            proposal=execution.proposal,
            risk_decision=execution.risk_decision,
            attribution=attribution,
            fill_ids=fill_ids,
            paper_result=execution,
            diagnostics=[
                RuntimeStageDiagnostic(
                    "close",
                    status,
                    ids={
                        "allocation_decision_id": allocation.allocation_decision_id,
                        "trade_proposal_id": (
                            execution.proposal.proposal_id if execution.proposal else None
                        ),
                        "risk_decision_id": (
                            execution.risk_decision.risk_decision_id
                            if execution.risk_decision
                            else None
                        ),
                        "attribution_id": attribution.attribution_id if attribution else None,
                    },
                )
            ],
        )

    def settle_due_and_evaluate(
        self,
        *,
        now_ns: int,
        policy: Any | None = None,
        allocation_decision_id: str | None = None,
    ) -> StrategyLearningResult:
        """Settle due forecasts, then apply the existing learning gates."""
        entries: list[Any] = []
        allocation = self._resolve_entry_allocation(allocation_decision_id)
        forecast = (
            self._get_forecast(allocation)
            if allocation_decision_id is not None and allocation is not None
            else self._entry.get("forecast")
        )
        if forecast is not None:
            entries.extend(
                self.repository.get_prediction_ledger_entries_by_forecast(
                    forecast.forecast_id
                )
            )
        if not entries:
            return StrategyLearningResult(
                diagnostics=("PREDICTION_LEDGER_ENTRY_NOT_FOUND",),
            )

        ordered_entries = sorted(entries, key=lambda item: item.ledger_entry_id)
        scheduler = self.outcome_settlement_service.scheduler
        due_entries = (
            scheduler.list_due_entries(ordered_entries, now_ns=now_ns)
            if scheduler is not None
            else tuple(ordered_entries)
        )
        due_ids = {entry.ledger_entry_id for entry in due_entries}
        settlement_results: list[SettlementResult] = [
            SettlementResult(
                status=SettlementStatus.NOT_DUE,
                ledger_entry_id=entry.ledger_entry_id,
                forecast_id=entry.forecast_id,
                mode=entry.mode,
                scenario_id=entry.scenario_id,
                ledger_entry=entry,
            )
            for entry in ordered_entries
            if entry.ledger_entry_id not in due_ids
        ]
        if due_entries:
            settlement_results.extend(
                self.outcome_settlement_service.settle_due(
                    due_entries,
                    now_ns=now_ns,
                )
            )
        settlement_results.sort(key=lambda item: item.ledger_entry_id)

        entry = ordered_entries[0]
        outcome = self._settled_prediction_outcome(entry, settlement_results)
        if allocation is None:
            allocation = self._entry.get("allocation_decision")
        match = (
            self.repository.get_strategy_match(allocation.strategy_match_ref.id)
            if allocation_decision_id is not None
            and allocation is not None
            and allocation.strategy_match_ref is not None
            else self._entry.get("match")
        )
        if match is None and allocation is not None and allocation.strategy_match_ref is not None:
            match = self.repository.get_strategy_match(allocation.strategy_match_ref.id)
        if forecast is None or match is None or allocation is None:
            return StrategyLearningResult(
                settlement_results=tuple(settlement_results),
                prediction_outcome=outcome,
                eligibility=LearningEligibility.INCONCLUSIVE,
                diagnostics=("LEARNING_LINEAGE_INCOMPLETE",),
            )

        attribution = self._latest_entry_attribution(allocation)
        observation = self._build_learning_observation(
            allocation=allocation,
            match=match,
            forecast=forecast,
            outcome=outcome,
            attribution=attribution,
        )
        if outcome is None and any(
            result.status == SettlementStatus.NOT_DUE for result in settlement_results
        ):
            return StrategyLearningResult(
                settlement_results=tuple(settlement_results),
                observation=observation,
                eligibility=LearningEligibility.INCONCLUSIVE,
                prediction_quality=forecast.quality.state,
                trading_quality=None,
                diagnostics=("PREDICTION_NOT_DUE",),
            )

        join = LearningJoinV1(
            observation=observation,
            strategy_match=match,
            forecast=forecast,
            prediction_outcome=outcome,
            trading_attribution=attribution,
        )
        active_policy = policy or self.learning_policy
        if active_policy is None:
            return StrategyLearningResult(
                settlement_results=tuple(settlement_results),
                observation=observation,
                join=join,
                prediction_outcome=outcome,
                trading_attribution=attribution,
                prediction_quality=forecast.quality.state,
                trading_quality=None,
                diagnostics=("LEARNING_POLICY_NOT_CONFIGURED",),
            )
        evaluation = evaluate_learning_join(join, active_policy, sample_count=1)
        handoff = None
        if evaluation.eligibility == LearningEligibility.ELIGIBLE:
            handoff = emit_research_handoff(
                (evaluation,),
                seed={
                    "source": "strategy_paper_runtime",
                    "observation_id": observation.observation_id,
                },
            )
        result = StrategyLearningResult(
            settlement_results=tuple(settlement_results),
            observation=observation,
            join=join,
            learning_evaluation=evaluation,
            handoff=handoff,
            eligibility=evaluation.eligibility,
            prediction_quality=evaluation.prediction_quality,
            trading_quality=evaluation.trading_quality,
            prediction_outcome=outcome,
            trading_attribution=attribution,
            diagnostics=tuple(evaluation.reasons),
        )
        self._entry["learning_result"] = result
        return result

    def reconstruct(
        self,
        allocation_decision_id: str,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        as_of_ns: int | None = None,
    ) -> StrategyRuntimeReconstruction:
        allocation = self.repository.get_allocation_decision(allocation_decision_id)
        if allocation is None:
            raise StrategyRuntimeError("ALLOCATION_DECISION_NOT_FOUND")
        expected_account = account_id or allocation.account_id
        expected_mode = mode or allocation.mode
        if allocation.account_id != expected_account or allocation.mode != _mode(expected_mode):
            raise StrategyRuntimeError("RECONSTRUCTION_SCOPE_MISMATCH")
        match = (
            self.repository.get_strategy_match(allocation.strategy_match_ref.id)
            if allocation.strategy_match_ref is not None
            else None
        )
        forecast = self._get_forecast(allocation)
        economics = self.repository.get_economic_assessment(
            allocation.economic_assessment_ref.id
        )
        opportunity = self.repository.get_opportunity(allocation.opportunity_ref.id)
        orders = tuple(
            order
            for order in self.ledger.project_orders()
            if _contains_reference(
                order,
                "allocation_decision",
                allocation.allocation_decision_id,
            )
        )
        order_ids = {str(order.get("order_id")) for order in orders}
        fills = tuple(
            fill
            for fill in self.ledger.project_fills()
            if str(fill.get("order_id")) in order_ids
        )
        proposal, risk = self._records_from_orders(orders)
        attribution = get_latest_complete_strategy_attribution(
            self.repository,
            allocation.allocation_decision_id,
            account_id=expected_account,
            mode=expected_mode,
            as_of_ns=as_of_ns,
        )
        ledger_entries = (
            self.repository.get_prediction_ledger_entries_by_forecast(forecast.forecast_id)
            if forecast is not None
            else ()
        )
        prediction_entry = ledger_entries[0] if ledger_entries else None
        prediction_outcome = None
        if prediction_entry is not None:
            outcomes = self.repository.get_outcomes_by_forecast(prediction_entry.forecast_id)
            prediction_outcome = next(
                (
                    item
                    for item in outcomes
                    if item.metadata.get("ledger_entry_id") == prediction_entry.ledger_entry_id
                ),
                None,
            )
        learning_result = self._entry.get("learning_result")
        learning_evaluation = (
            learning_result.learning_evaluation
            if learning_result is not None
            and getattr(self._entry.get("allocation_decision"), "allocation_decision_id", None)
            == allocation_decision_id
            else None
        )
        return StrategyRuntimeReconstruction(
            allocation_decision=allocation,
            strategy_match=match,
            forecast=forecast,
            economic_assessment=economics,
            opportunity=opportunity,
            proposal=proposal,
            risk_decision=risk,
            orders=orders,
            fills=fills,
            account=self.ledger.project_account(),
            attribution=attribution,
            prediction_ledger_entry=prediction_entry,
            prediction_outcome=prediction_outcome,
            learning_evaluation=learning_evaluation,
        )

    def _settled_prediction_outcome(
        self,
        entry: Any,
        settlement_results: list[SettlementResult],
    ) -> Any | None:
        for result in settlement_results:
            if result.ledger_entry_id == entry.ledger_entry_id and result.outcome is not None:
                return result.outcome
        for outcome in self.repository.get_outcomes_by_forecast(entry.forecast_id):
            if outcome.metadata.get("ledger_entry_id") != entry.ledger_entry_id:
                continue
            if outcome.metadata.get("mode") != entry.mode:
                continue
            if entry.scenario_id is not None and (
                outcome.metadata.get("scenario_id") != entry.scenario_id
            ):
                continue
            return outcome
        return None

    def _latest_entry_attribution(
        self,
        allocation: Any,
    ) -> StrategyAttributionV1 | None:
        allocation_id = getattr(allocation, "allocation_decision_id", None)
        if not allocation_id:
            return self._entry.get("attribution")
        records = self.repository.get_strategy_attributions_by_allocation(
            allocation_id,
            account_id=allocation.account_id,
            mode=allocation.mode,
        )
        latest = get_latest_complete_strategy_attribution(
            self.repository,
            allocation_id,
            account_id=allocation.account_id,
            mode=allocation.mode,
        )
        return latest or (self._entry.get("attribution") if not records else None)

    def _build_learning_observation(
        self,
        *,
        allocation: Any,
        match: StrategyMatch,
        forecast: ForecastV1,
        outcome: Any | None,
        attribution: StrategyAttributionV1 | None,
    ) -> LearningObservationV1:
        metadata = dict(forecast.metadata)
        outcome_settled = outcome is not None
        outcome_labelable = (
            outcome_settled and outcome.resolution_status.value == "SETTLED"
        )
        mode = str(getattr(allocation, "mode", metadata.get("mode", "PAPER")))
        return LearningObservationV1.create(
            account_id=str(allocation.account_id),
            mode=mode,
            strategy_id=match.strategy_id,
            strategy_identity_hash=match.strategy_identity_hash,
            strategy_match_ref=ContractReference(kind="strategy_match", id=match.match_id),
            forecast_ref=ContractReference(kind="forecast", id=forecast.forecast_id),
            prediction_outcome_ref=(
                ContractReference(kind="outcome", id=outcome.outcome_id)
                if outcome is not None
                else None
            ),
            trading_attribution_ref=(
                ContractReference(
                    kind="strategy_attribution",
                    id=attribution.attribution_id,
                )
                if attribution is not None
                else None
            ),
            opportunity_ref=getattr(allocation, "opportunity_ref", None),
            cluster_ref=getattr(allocation, "cluster_ref", None),
            evidence_tier=metadata.get("evidence_tier", "OBSERVED_REPLAY"),
            evidence_mode=str(metadata.get("evidence_mode", "PAPER")),
            decision_time_ns=forecast.decision_time_ns,
            settlement_time_ns=(
                outcome.adjudicated_at_ns if outcome_settled else None
            ),
            settlement_state=(
                LearningSettlementState.SETTLED
                if outcome_settled
                else LearningSettlementState.UNSETTLED
            ),
            label_state=(
                LearningLabelState.LABELABLE
                if outcome_labelable
                else (
                    LearningLabelState.UNLABELABLE
                    if outcome_settled
                    else LearningLabelState.PENDING
                )
            ),
        )

    def _select_match(
        self,
        scan: ScanResult,
        strategy_id: str | None,
    ) -> StrategyMatch | None:
        matches = tuple(
            match
            for match in scan.matches
            if match.disposition == StrategyMatchDisposition.MATCHED
            and (strategy_id is None or match.strategy_id == strategy_id)
        )
        return matches[0] if matches else None

    def _resolve_forecast(
        self,
        match: StrategyMatch,
        request: ScanRequest,
    ) -> ForecastV1 | None:
        try:
            forecast = self.forecast_resolver(match)
        except Exception:
            return None
        if not isinstance(forecast, ForecastV1):
            return None
        if forecast.scope != match.scope:
            return None
        if forecast.decision_time_ns > request.decision_time_ns:
            return None
        if forecast.horizon.duration_ns != self.champion_at_forecast.champion_scope.horizon_ns:
            return None
        if forecast.resolve_time_ns is not None and forecast.resolve_time_ns <= forecast.decision_time_ns:
            return None
        metadata = forecast.metadata
        if metadata.get("account_id") not in {None, request.scope.account_id}:
            return None
        if metadata.get("mode") not in {None, request.scope.mode, _mode(request.scope.mode)}:
            return None
        return forecast

    def _attach_forecast_reference(
        self,
        match: StrategyMatch,
        forecast: ForecastV1,
    ) -> StrategyMatch:
        ref = ContractReference(kind="forecast", id=forecast.forecast_id)
        if ref in match.source_forecast_refs:
            return match
        enriched = replace(
            match,
            source_forecast_refs=(ref,),
            lineage_refs=(*match.lineage_refs, ref),
        )
        object.__setattr__(enriched, "match_id", f"SM-{enriched.match_identity_hash}")
        return enriched

    def _resolve_economics(self, match: StrategyMatch, forecast: ForecastV1) -> Any:
        if callable(self.economic_assessment):
            return self.economic_assessment(match, forecast)
        return self.economic_assessment

    def _comparison_constraints(self, request: ScanRequest) -> ComparisonConstraintsV1:
        values = dict(self.comparison_constraints)
        return ComparisonConstraintsV1(
            account_id=request.scope.account_id,
            mode=request.scope.mode,
            decision_time_ns=request.decision_time_ns,
            currency=str(values.get("currency", self.execution_policy.currency)),
            scale=int(values.get("scale", self.execution_policy.price_scale)),
        ) if isinstance(self.comparison_constraints, Mapping) else self.comparison_constraints

    def _allocation_constraints(self, request: ScanRequest) -> CapitalAllocationConstraintsV1:
        if not isinstance(self.allocation_constraints, Mapping):
            return self.allocation_constraints
        values = dict(self.allocation_constraints)
        return CapitalAllocationConstraintsV1(
            account_id=request.scope.account_id,
            mode=request.scope.mode,
            decision_time_ns=request.decision_time_ns,
            currency=str(values.get("currency", self.execution_policy.currency)),
            scale=int(values.get("scale", self.execution_policy.price_scale)),
            available_capital_minor=int(values["available_capital_minor"]),
            available_buying_power_minor=int(values["available_buying_power_minor"]),
            maximum_loss_budget_minor=int(values["maximum_loss_budget_minor"]),
            capital_time_budget_minor_ns=values.get("capital_time_budget_minor_ns"),
            max_capital_per_candidate_minor=values.get("max_capital_per_candidate_minor"),
            max_loss_per_candidate_minor=values.get("max_loss_per_candidate_minor"),
        )

    def _entry_lineage(
        self,
        *,
        allocation_decision: CapitalAllocationDecisionV1,
        match: StrategyMatch,
        forecast: ForecastV1,
        opportunity: OpportunityV1,
        cluster_id: str,
        sidecar: Any,
        portfolio: PaperPortfolioSnapshotV1,
    ) -> tuple[ContractReference, ...]:
        return _unique_refs(
            (
                ContractReference(kind="allocation_decision", id=allocation_decision.allocation_decision_id),
                ContractReference(kind="strategy_match", id=match.match_id),
                ContractReference(kind="forecast", id=forecast.forecast_id),
                ContractReference(kind="opportunity", id=opportunity.opportunity_id),
                ContractReference(kind="cluster", id=cluster_id),
                ContractReference(kind="universal_economic_assessment", id=sidecar.assessment_id),
                ContractReference(kind="paper_portfolio_snapshot", id=portfolio.snapshot_id),
            )
        )

    def _entry_lineage_from_allocation(
        self,
        allocation: CapitalAllocationDecisionV1,
        *,
        match: StrategyMatch | None,
        forecast: ForecastV1 | None,
        opportunity: OpportunityV1 | None,
        portfolio: PaperPortfolioSnapshotV1,
    ) -> tuple[ContractReference, ...]:
        refs = [
            ContractReference(kind="allocation_decision", id=allocation.allocation_decision_id),
            allocation.cluster_ref,
            allocation.opportunity_ref,
            allocation.economic_assessment_ref,
            allocation.portfolio_snapshot_ref,
        ]
        if match is not None:
            refs.append(ContractReference(kind="strategy_match", id=match.match_id))
        if forecast is not None:
            refs.append(ContractReference(kind="forecast", id=forecast.forecast_id))
        if opportunity is not None:
            refs.append(ContractReference(kind="opportunity", id=opportunity.opportunity_id))
        refs.append(ContractReference(kind="paper_portfolio_snapshot", id=portfolio.snapshot_id))
        return _unique_refs(tuple(refs))

    def _materialize(
        self,
        allocation: CapitalAllocationDecisionV1,
        *,
        proposal: Any | None,
        risk_decision: Any | None,
    ) -> StrategyAttributionV1 | None:
        return materialize_strategy_attribution(
            repository=self.repository,
            ledger=self.ledger,
            allocation_decision=allocation,
            proposal=proposal,
            risk_decision=risk_decision,
            account_id=allocation.account_id,
            mode=allocation.mode,
        )

    def _attribution_for_fill_ids(
        self,
        allocation: CapitalAllocationDecisionV1,
        fill_ids: tuple[str, ...],
    ) -> StrategyAttributionV1 | None:
        expected = tuple(sorted(fill_ids))
        for record in self.repository.get_strategy_attributions_by_allocation(
            allocation.allocation_decision_id,
            account_id=allocation.account_id,
            mode=allocation.mode,
        ):
            actual = tuple(sorted(ref.id for ref in record.fill_refs))
            if actual == expected:
                return record
        return None

    def _resolve_entry_allocation(self, allocation_decision_id: str | None) -> Any | None:
        if allocation_decision_id:
            return self.repository.get_allocation_decision(allocation_decision_id)
        return self._entry.get("allocation_decision")

    def _get_forecast(self, allocation: Any) -> ForecastV1 | None:
        for ref in allocation.forecast_refs:
            if ref.kind == "forecast":
                return self.repository.get_forecast(ref.id)
        return None

    def _validate_close_scope(
        self,
        opportunity: OpportunityV1,
        allocation: Any,
        match: StrategyMatch | None,
        decision_time_ns: int,
    ) -> None:
        if opportunity.created_at_ns > decision_time_ns:
            raise StrategyRuntimeError("CLOSE_OPPORTUNITY_AFTER_DECISION")
        if opportunity.valid_until_ns is not None and decision_time_ns >= opportunity.valid_until_ns:
            raise StrategyRuntimeError("CLOSE_OPPORTUNITY_EXPIRED")
        if opportunity.scope.instrument_ids != (self._instrument_id(opportunity),):
            raise StrategyRuntimeError("CLOSE_SCOPE_INVALID")
        if match is not None and match.scope.instrument_ids != opportunity.scope.instrument_ids:
            raise StrategyRuntimeError("CLOSE_MATCH_SCOPE_MISMATCH")
        account = opportunity.metadata.get("account_id")
        mode = opportunity.metadata.get("mode")
        if account is not None and str(account) != allocation.account_id:
            raise StrategyRuntimeError("CLOSE_ACCOUNT_SCOPE_MISMATCH")
        if mode is not None and _mode(mode) != allocation.mode:
            raise StrategyRuntimeError("CLOSE_MODE_SCOPE_MISMATCH")

    def _records_from_orders(self, orders: tuple[Mapping[str, Any], ...]) -> tuple[Any | None, Any | None]:
        risk = None
        for order in orders:
            risk_id = order.get("risk_decision_id")
            if risk_id:
                risk = self.repository.get_risk_decision(str(risk_id))
                if risk is not None:
                    break
        proposal = (
            self.repository.get_trade_proposal(risk.trade_proposal_id)
            if risk is not None
            else None
        )
        return proposal, risk

    def _result(self, status: str, **kwargs: Any) -> StrategyRuntimeResult:
        scan = kwargs.get("scan")
        match = kwargs.get("match")
        forecast = kwargs.get("forecast")
        opportunity = kwargs.get("opportunity")
        allocation = kwargs.get("allocation_decision")
        proposal = kwargs.get("proposal")
        risk = kwargs.get("risk_decision")
        prediction_ledger_entry = (
            kwargs.get("prediction_ledger_entry")
            or self._entry.get("prediction_ledger_entry")
        )
        attribution = kwargs.get("attribution")
        paper_result = kwargs.get("paper_result")
        fills = kwargs.get("fill_ids") or self._fill_ids(paper_result)
        ids = {
            "scan_id": scan.scan_id if scan else None,
            "strategy_match_id": match.match_id if match else None,
            "forecast_id": forecast.forecast_id if forecast else None,
            "prediction_ledger_entry_id": (
                prediction_ledger_entry.ledger_entry_id
                if prediction_ledger_entry is not None
                and hasattr(prediction_ledger_entry, "ledger_entry_id")
                else None
            ),
            "opportunity_id": opportunity.opportunity_id if opportunity else None,
            "economic_assessment_id": (
                allocation.economic_assessment_ref.id if allocation else None
            ),
            "cluster_id": allocation.cluster_ref.id if allocation else None,
            "decision_set_id": allocation.decision_set_id if allocation else None,
            "comparison_id": allocation.comparison_id if allocation else None,
            "allocation_decision_id": allocation.allocation_decision_id if allocation else None,
            "trade_proposal_id": proposal.proposal_id if proposal else None,
            "risk_decision_id": risk.risk_decision_id if risk else None,
            "order_id": self._order_id(paper_result),
            "attribution_id": attribution.attribution_id if attribution else None,
        }
        stage_ids = {key: value for key, value in ids.items() if value is not None}
        quantities = {}
        if paper_result is not None and paper_result.prepared is not None:
            quantities.update(paper_result.prepared.quantity_facts)
        if paper_result is not None and paper_result.paper_submit:
            fill = paper_result.paper_submit.get("fill")
            if isinstance(fill, Mapping):
                quantities["filled_quantity"] = int(fill.get("fill_quantity", 0))
            else:
                order = paper_result.paper_submit.get("order")
                if isinstance(order, Mapping) and order.get("filled_quantity") is not None:
                    quantities["filled_quantity"] = int(order["filled_quantity"])
        return StrategyRuntimeResult(
            status=status,
            scan_id=scan.scan_id if scan else None,
            strategy_id=match.strategy_id if match else None,
            strategy_identity_hash=match.strategy_identity_hash if match else None,
            stage_ids=stage_ids,
            quantities=quantities,
            fill_ids=tuple(fills),
            attribution_id=attribution.attribution_id if attribution else None,
            diagnostics=tuple(kwargs.get("diagnostics", ())),
            ids=stage_ids,
        )

    @staticmethod
    def _fill_ids(result: PaperExecutionResult | None) -> tuple[str, ...]:
        if result is None or not result.paper_submit:
            return ()
        fill = result.paper_submit.get("fill")
        return (str(fill["fill_id"]),) if isinstance(fill, Mapping) and fill.get("fill_id") else ()

    def _result_fill_ids(self, result: PaperExecutionResult | None) -> tuple[str, ...]:
        fill_ids = self._fill_ids(result)
        if fill_ids or result is None:
            return fill_ids
        order_id = self._order_id(result)
        if order_id is None:
            return ()
        return tuple(
            sorted(
                str(fill["fill_id"])
                for fill in self.ledger.project_fills()
                if str(fill.get("order_id")) == order_id and fill.get("fill_id")
            )
        )

    @staticmethod
    def _filled_quantity(result: PaperExecutionResult | None) -> int:
        if result is None or not result.paper_submit:
            return 0
        fill = result.paper_submit.get("fill")
        if isinstance(fill, Mapping):
            return int(fill.get("fill_quantity", 0))
        order = result.paper_submit.get("order")
        return int(order.get("filled_quantity", 0)) if isinstance(order, Mapping) else 0

    @staticmethod
    def _order_id(result: PaperExecutionResult | None) -> str | None:
        if result is None or not result.paper_submit:
            return None
        value = result.paper_submit.get("order_id")
        return str(value) if value else None

    def _scenario_id(self) -> str | None:
        return getattr(self.opportunity_context, "scenario_id", None)

    @staticmethod
    def _instrument_id(opportunity: OpportunityV1) -> str:
        instruments = opportunity.scope.instrument_ids
        if len(instruments) != 1:
            raise StrategyRuntimeError("INSTRUMENT_SCOPE_INVALID")
        return instruments[0]

    @staticmethod
    def _symbol(opportunity: OpportunityV1) -> str:
        return str(opportunity.metadata.get("symbol", opportunity.scope.instrument_ids[0].split(":")[-1]))

    @staticmethod
    def _scan_stop_status(scan: ScanResult) -> str:
        dispositions = {match.disposition for match in scan.matches}
        if dispositions and dispositions <= {StrategyMatchDisposition.REJECTED}:
            return "SCREENED_OUT"
        if StrategyMatchDisposition.REJECTED in dispositions:
            return "STRATEGY_REJECTED"
        return "FORECAST_UNAVAILABLE"

    @staticmethod
    def _scan_reasons(scan: ScanResult) -> tuple[str, ...]:
        reasons: list[str] = []
        for match in scan.matches:
            reasons.extend(match.rejection_reasons)
            reasons.extend(match.abstention_reasons)
            reasons.extend(match.unavailability_reasons)
        return tuple(sorted(set(reasons)))


def _mode(value: Any) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE"}.get(normalized, normalized)


def _unique_refs(refs: tuple[ContractReference, ...]) -> tuple[ContractReference, ...]:
    return tuple(
        sorted(
            {(ref.kind, ref.id, ref.schema_version): ref for ref in refs}.values(),
            key=lambda ref: (ref.kind, ref.id, ref.schema_version),
        )
    )


def _contains_reference(order: Mapping[str, Any], kind: str, identifier: str) -> bool:
    def visit(value: Any) -> bool:
        if isinstance(value, Mapping):
            if value.get("kind") == kind and str(value.get("id")) == identifier:
                return True
            return any(visit(item) for item in value.values())
        if isinstance(value, (tuple, list, set)):
            return any(visit(item) for item in value)
        return False

    return visit(order)


__all__ = [
    "RuntimeStageDiagnostic",
    "StrategyLearningResult",
    "StrategyPaperRuntime",
    "StrategyRuntimeError",
    "StrategyRuntimeReconstruction",
    "StrategyRuntimeResult",
]
