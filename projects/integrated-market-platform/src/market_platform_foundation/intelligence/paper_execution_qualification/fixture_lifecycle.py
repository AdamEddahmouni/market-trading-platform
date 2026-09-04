"""Deterministic prospective paper execution fixture lifecycle (BUILD 27)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from market_platform_foundation.intelligence.execution import PaperExecutionOrchestrator, build_execution_policy
from market_platform_foundation.intelligence.execution.snapshot import snapshot_from_paper_ledger
from market_platform_foundation.intelligence.forward_qualification import (
    build_forward_prediction_receipt,
    build_forward_qualification_run,
    build_forward_qualification_spec,
)
from market_platform_foundation.intelligence.opportunity import OpportunityEngine
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.outcomes.service import PredictionLedgerService
from market_platform_foundation.intelligence.outcomes.types import SettlementMode
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import PromotionEngine
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.opportunity_fixtures import champion_forecast, default_opportunity_context, default_opportunity_policy
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.outcome_fixtures import seed_anchor_trade
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE, validated_candidate_bundle
from tests.intelligence.test_baseline_fixtures import sample_snapshot

from .fill_realism import bar_conservative_limitations, execution_shortfall_bps, validate_quote_fill_realism
from .funnel import empty_funnel
from .initial_portfolio import build_initial_paper_portfolio_state
from .receipt import build_paper_execution_receipt
from .report import build_paper_execution_qualification_report
from .run import build_paper_execution_qualification_run
from .spec import build_paper_execution_qualification_spec
from .fixtures import sample_bars_for_execution
from .types import ExecutionFunnelCountsV1, ExecutionIntegrityStatus, PaperEvidenceClass


@dataclass(frozen=True)
class PaperFixtureLifecycleResult:
    spec_id: str
    run_id: str
    report_id: str
    forecast_id: str
    opportunity_id: str | None
    forward_receipt_ref: str | None
    trade_proposal_id: str | None
    risk_decision_id: str | None
    paper_order_id: str | None
    fill_id: str | None
    integrity_status: ExecutionIntegrityStatus
    funnel: ExecutionFunnelCountsV1
    metadata: dict[str, Any]


def run_prospective_paper_fixture_lifecycle(
    *,
    source_build26_ref: str,
    source_release_candidate_ref: str,
    source_head: str,
    qualification_start_ns: int = T,
) -> PaperFixtureLifecycleResult:
    os.environ["IMP_PAPER_EXECUTION"] = "1"
    repo = InMemoryIntelligenceRepository()
    bundle_repo, _, candidate, _, _, _ = validated_candidate_bundle()
    promotion_engine = PromotionEngine()
    champion = promotion_engine.bootstrap_champion(
        champion_scope=DEFAULT_SCOPE,
        candidate=candidate,
        effective_from_ns=qualification_start_ns,
    )
    repo.put_champion_assignment(champion)

    forward_spec = build_forward_qualification_spec(
        release_candidate_ref=source_release_candidate_ref,
        source_head=source_build26_ref,
        qualification_start_ns=qualification_start_ns,
        minimum_prediction_count=1,
        minimum_labelable_count=1,
        minimum_duration_ns=1,
    )
    forward_run = build_forward_qualification_run(
        spec=forward_spec,
        source_head=source_build26_ref,
        run_start_ns=qualification_start_ns,
        data_mode="FIXTURE_REPLAY",
    )

    snapshot = sample_snapshot()
    seed_anchor_trade(repo, event_time_ns=qualification_start_ns)
    repo.put_snapshot(snapshot)
    forecast = champion_forecast(
        champion,
        decision_time_ns=qualification_start_ns,
        snapshot=snapshot,
    )
    repo.put_forecast(forecast)
    ledger_service = PredictionLedgerService(repo)
    register_result = ledger_service.register_forecast(
        forecast,
        now_ns=forecast.decision_time_ns,
        mode=SettlementMode.ACTUAL_LIVE,
        scenario_id="BUILD27_PAPER_FIXTURE",
    )
    ledger_entry = register_result
    forward_receipt = build_forward_prediction_receipt(
        forecast=forecast,
        ledger_entry=ledger_entry,
        qualification_run_ref=forward_run.qualification_run_id,
        recorded_at_ns=forecast.decision_time_ns,
    )

    opp_policy = default_opportunity_policy()
    repo.put_opportunity_policy(opp_policy)
    exec_policy = build_execution_policy(trade_fraction_nav=0.01, max_trade_notional_minor=5_000_00)
    portfolio_state = build_initial_paper_portfolio_state()

    peq_spec = build_paper_execution_qualification_spec(
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
        qualification_start_ns=qualification_start_ns,
        minimum_opportunities=1,
        minimum_risk_decisions=1,
        minimum_orders=1,
        minimum_fills=1,
        minimum_duration_ns=1,
        opportunity_policy=opp_policy,
        execution_policy=exec_policy,
        initial_portfolio=portfolio_state,
        allowed_forward_qualification_runs=(forward_run.qualification_run_id,),
    )
    peq_run = build_paper_execution_qualification_run(
        spec=peq_spec,
        source_head=source_head,
        run_start_ns=qualification_start_ns,
        data_mode="FIXTURE_REPLAY",
        execution_mode="PAPER",
        execution_authority="AUTHORIZED",
        forward_qualification_run_ref=forward_run.qualification_run_id,
        champion_assignment_ref=champion.assignment_id,
    )

    funnel = empty_funnel()
    funnel = ExecutionFunnelCountsV1(
        forecasts_evaluated=1,
        attrition_reasons=dict(funnel.attrition_reasons),
    )

    opp_time = qualification_start_ns + 1_000_000_000
    context = default_opportunity_context(decision_time_ns=opp_time)
    opp_engine = OpportunityEngine()
    opp_result = opp_engine.assess(
        forecast=forecast,
        policy=opp_policy,
        context=context,
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_decision_time_ns=opp_time,
    )
    repo.put_opportunity_assessment(opp_result.assessment)
    funnel = ExecutionFunnelCountsV1(
        forecasts_evaluated=funnel.forecasts_evaluated,
        opportunity_assessments=funnel.opportunity_assessments + 1,
        attrition_reasons=dict(funnel.attrition_reasons),
    )

    opportunity = None
    trade_proposal_id = None
    risk_decision_id = None
    paper_order_id = None
    fill_id = None
    integrity_status = ExecutionIntegrityStatus.VALID

    if opp_result.assessment.assessment_action == AssessmentAction.EMIT and opp_result.opportunity is not None:
        opportunity = opp_result.opportunity
        repo.put_opportunity(opportunity)
        funnel = ExecutionFunnelCountsV1(
            forecasts_evaluated=funnel.forecasts_evaluated,
            opportunity_assessments=funnel.opportunity_assessments,
            opportunities_emitted=1,
            attrition_reasons=dict(funnel.attrition_reasons),
        )

        from market_platform_foundation.intelligence.execution import MarketQuoteV1

        quote = MarketQuoteV1(
            instrument_id="inst-biya",
            bid_minor=9900,
            ask_minor=10100,
            available_time_ns=opp_time,
        )
        bars = sample_bars_for_execution(created_time_ns=opp_time)
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="build27-fixture",
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        from market_platform_foundation.intelligence.execution import build_portfolio_snapshot

        portfolio = build_portfolio_snapshot(
            captured_at_ns=opp_time,
            cash_minor=portfolio_state.initial_cash_minor,
            equity_minor=portfolio_state.initial_equity_minor,
        )
        orchestrator = PaperExecutionOrchestrator()
        result = orchestrator.execute_paper(
            opportunity=opportunity,
            policy=exec_policy,
            portfolio=portfolio,
            quote=quote,
            ledger=ledger,
            bars=bars,
            decision_time_ns=opp_time,
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_authority="AUTHORIZED",
        )
        trade_proposal_id = result.proposal.proposal_id
        risk_decision_id = result.risk_decision.risk_decision_id
        funnel = ExecutionFunnelCountsV1(
            forecasts_evaluated=funnel.forecasts_evaluated,
            opportunity_assessments=funnel.opportunity_assessments,
            opportunities_emitted=funnel.opportunities_emitted,
            trade_proposals=1,
            risk_approvals=1 if result.risk_decision.decision.value in {"APPROVE", "REDUCE"} else 0,
            risk_rejections=0 if result.risk_decision.decision.value in {"APPROVE", "REDUCE"} else 1,
            attrition_reasons=dict(funnel.attrition_reasons),
        )
        if result.paper_submit:
            funnel = ExecutionFunnelCountsV1(
                forecasts_evaluated=funnel.forecasts_evaluated,
                opportunity_assessments=funnel.opportunity_assessments,
                opportunities_emitted=funnel.opportunities_emitted,
                trade_proposals=funnel.trade_proposals,
                risk_approvals=funnel.risk_approvals,
                risk_rejections=funnel.risk_rejections,
                orders_submitted=1,
                orders_filled=1 if result.paper_submit.get("fill") else 0,
                no_fill_count=0 if result.paper_submit.get("fill") else 1,
                attrition_reasons=dict(funnel.attrition_reasons),
            )
            paper_order_id = result.paper_submit.get("order_id")
            fill = result.paper_submit.get("fill")
            if fill:
                fill_id = fill.get("fill_id")
                fill_price = int(fill["fill_price_minor"])
                ok, codes = validate_quote_fill_realism(
                    side="BUY",
                    fill_price_minor=fill_price,
                    bid_minor=quote.bid_minor,
                    ask_minor=quote.ask_minor,
                )
                if not ok:
                    integrity_status = ExecutionIntegrityStatus.INVALID
                shortfall = execution_shortfall_bps(
                    side="BUY",
                    fill_price_minor=fill_price,
                    reference_price_minor=result.proposal.reference_price_minor,
                )
            else:
                integrity_status = ExecutionIntegrityStatus.VALID
                shortfall = None
        else:
            shortfall = None
    else:
        reasons = dict(funnel.attrition_reasons)
        reasons["OPPORTUNITY_NOT_EMITTED"] = 1
        funnel = ExecutionFunnelCountsV1(
            forecasts_evaluated=funnel.forecasts_evaluated,
            opportunity_assessments=funnel.opportunity_assessments,
            attrition_reasons=reasons,
        )
        shortfall = None

    receipt = None
    if opportunity and trade_proposal_id and risk_decision_id:
        receipt = build_paper_execution_receipt(
            opportunity_id=opportunity.opportunity_id,
            forecast_id=forecast.forecast_id,
            forward_receipt_ref=forward_receipt.receipt_id,
            trade_proposal_id=trade_proposal_id,
            risk_decision_id=risk_decision_id,
            paper_order_id=paper_order_id,
            fill_id=fill_id,
            decision_time_ns=opp_time,
            fill_time_ns=opp_time + 60_000_000_000 if fill_id else None,
            qualification_run_ref=peq_run.qualification_run_id,
            evidence_class=PaperEvidenceClass.FORWARD_PAPER,
        )
        integrity_status = receipt.execution_integrity_status

    receipts = (receipt,) if receipt else ()
    ending_portfolio = None
    if paper_order_id:
        ending_portfolio = snapshot_from_paper_ledger(
            ledger,
            captured_at_ns=qualification_start_ns + 2_000_000_000,
        )

    report = build_paper_execution_qualification_report(
        spec=peq_spec,
        run=peq_run,
        receipts=receipts,
        funnel_counts=funnel,
        evaluation_as_of_ns=qualification_start_ns + 3_000_000_000,
        forward_qualification_refs=(forward_run.qualification_run_id,),
        fill_realism_notes={
            "limitations": list(bar_conservative_limitations()),
            "shortfall_bps": shortfall,
        },
        ending_portfolio=ending_portfolio,
    )

    return PaperFixtureLifecycleResult(
        spec_id=peq_spec.qualification_spec_id,
        run_id=peq_run.qualification_run_id,
        report_id=report.qualification_report_id,
        forecast_id=forecast.forecast_id,
        opportunity_id=opportunity.opportunity_id if opportunity else None,
        forward_receipt_ref=forward_receipt.receipt_id,
        trade_proposal_id=trade_proposal_id,
        risk_decision_id=risk_decision_id,
        paper_order_id=paper_order_id,
        fill_id=fill_id,
        integrity_status=integrity_status,
        funnel=funnel,
        metadata={
            "disposition": report.qualification_disposition.value,
            "forward_receipt_ref": forward_receipt.receipt_id,
        },
    )
