"""Paper execution adversarial scenarios (BUILD 27)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from market_platform_foundation.intelligence.execution import (
    PaperExecutionOrchestrator,
    PreTradeRiskEngine,
    RiskDecisionKind,
)
from market_platform_foundation.intelligence.execution.snapshot import snapshot_from_paper_ledger
from market_platform_foundation.intelligence.governance.types import RuntimeGovernanceState
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_opportunity, sample_quote
from tests.intelligence.outcome_fixtures import T

from .fill_realism import validate_no_future_quote, validate_quote_fill_realism
from .fixtures import sample_bars_for_execution
from .integrity import validate_forward_lineage, validate_opportunity_not_expired
from .types import ExecutionIntegrityFailureCode, PaperEvidenceClass


class ScenarioStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ScenarioResultV1:
    scenario_id: str
    status: ScenarioStatus
    expected: str
    observed: str
    details: dict[str, Any]


REQUIRED_SCENARIOS: tuple[str, ...] = (
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
)


def _scenario_p01_replay_masquerading() -> ScenarioResultV1:
    status, codes = validate_forward_lineage(
        evidence_class=PaperEvidenceClass.REPLAY_PAPER,
        forward_receipt_ref="FQPRCPT-test",
        forecast_id="fc-test",
    )
    ok = status.value == "INVALID" and ExecutionIntegrityFailureCode.REPLAY_MASQUERADING_AS_FORWARD.value in codes
    return ScenarioResultV1("P01", ScenarioStatus.PASS if ok else ScenarioStatus.FAIL, "INVALID", status.value, {"codes": codes})


def _scenario_p02_expired_opportunity() -> ScenarioResultV1:
    ok, codes = validate_opportunity_not_expired(decision_time_ns=T + 5_000_000_000, valid_until_ns=T + 5_000_000_000)
    engine = PreTradeRiskEngine()
    rejected = False
    try:
        engine.build_proposal(
            opportunity=sample_opportunity(valid_until_ns=T + 5_000_000_000),
            policy=default_execution_policy(),
            portfolio=flat_portfolio(captured_at_ns=T + 4_000_000_000),
            quote=sample_quote(available_time_ns=T + 4_000_000_000),
            proposal_time_ns=T + 5_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
    except Exception:
        rejected = True
    ok = not ok and rejected
    return ScenarioResultV1("P02", ScenarioStatus.PASS if ok else ScenarioStatus.FAIL, "NO_ORDER", "rejected" if rejected else "allowed", {"codes": codes})


def _scenario_p03_wide_spread_no_mid_fill() -> ScenarioResultV1:
    os.environ["IMP_PAPER_EXECUTION"] = "1"
    quote = sample_quote(bid_minor=9900, ask_minor=10100, available_time_ns=T)
    bars = sample_bars_for_execution(created_time_ns=T, high="102.00", low="99.00")
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p03",
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="AUTHORIZED",
    )
    orchestrator = PaperExecutionOrchestrator()
    result = orchestrator.execute_paper(
        opportunity=sample_opportunity(created_at_ns=T, valid_until_ns=T + 600_000_000_000),
        policy=default_execution_policy(max_trade_notional_minor=500_00),
        portfolio=flat_portfolio(equity_minor=1_000_000_00, cash_minor=1_000_000_00, captured_at_ns=T),
        quote=quote,
        ledger=ledger,
        bars=bars,
        decision_time_ns=T,
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_authority="AUTHORIZED",
    )
    fill = None
    if result.paper_submit and result.paper_submit.get("fill"):
        fill = result.paper_submit["fill"]
    if fill is None:
        return ScenarioResultV1("P03", ScenarioStatus.FAIL, "FILL", "none", {})
    fill_price = int(fill["fill_price_minor"])
    mid = (quote.bid_minor + quote.ask_minor) // 2
    ok = fill_price != mid and fill_price >= quote.ask_minor
    return ScenarioResultV1(
        "P03",
        ScenarioStatus.PASS if ok else ScenarioStatus.FAIL,
        "fill>=ask_not_mid",
        str(fill_price),
        {"ask": quote.ask_minor, "mid": mid},
    )


def _scenario_p04_future_quote_forbidden() -> ScenarioResultV1:
    ok, codes = validate_no_future_quote(fill_time_ns=T, quote_available_time_ns=T + 1)
    return ScenarioResultV1(
        "P04",
        ScenarioStatus.PASS if not ok else ScenarioStatus.FAIL,
        "FUTURE_QUOTE_FILL",
        codes[0] if codes else "none",
        {},
    )


def _scenario_p05_duplicate_order() -> ScenarioResultV1:
    os.environ["IMP_PAPER_EXECUTION"] = "1"
    bars = sample_bars_for_execution(created_time_ns=T)
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p05",
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="AUTHORIZED",
    )
    kwargs = {
        "opportunity": sample_opportunity(created_at_ns=T, valid_until_ns=T + 600_000_000_000),
        "policy": default_execution_policy(max_trade_notional_minor=500_00),
        "portfolio": flat_portfolio(equity_minor=1_000_000_00, captured_at_ns=T),
        "quote": sample_quote(available_time_ns=T),
        "ledger": ledger,
        "bars": bars,
        "decision_time_ns": T,
        "instrument_id": "inst-biya",
        "symbol": "BIYA",
        "execution_authority": "AUTHORIZED",
    }
    orchestrator = PaperExecutionOrchestrator()
    first = orchestrator.execute_paper(**kwargs)
    second = orchestrator.execute_paper(**kwargs)
    duplicate = bool(second.paper_submit and second.paper_submit.get("duplicate"))
    ok = duplicate or (first.paper_submit is None and second.paper_submit is None)
    if first.risk_decision and first.risk_decision.approved_quantity > 0:
        ok = duplicate
    return ScenarioResultV1("P05", ScenarioStatus.PASS if ok else ScenarioStatus.FAIL, "duplicate", str(duplicate), {})


def _scenario_p06_concurrent_risk() -> ScenarioResultV1:
    policy = default_execution_policy(
        max_gross_exposure_fraction=0.10,
        max_trade_notional_minor=50_000_00,
        trade_fraction_nav=0.05,
    )
    portfolio = flat_portfolio(equity_minor=100_000_00, captured_at_ns=T)
    engine = PreTradeRiskEngine()
    opp1 = sample_opportunity(opportunity_id="opp-a", created_at_ns=T)
    opp2 = sample_opportunity(opportunity_id="opp-b", created_at_ns=T)
    quote = sample_quote(available_time_ns=T)
    p1 = engine.build_proposal(
        opportunity=opp1,
        policy=policy,
        portfolio=portfolio,
        quote=quote,
        proposal_time_ns=T,
        instrument_id="inst-biya",
        symbol="BIYA",
    )
    r1 = engine.assess(
        proposal=p1,
        opportunity=opp1,
        policy=policy,
        portfolio=portfolio,
        decision_time_ns=T,
        symbol="BIYA",
    )
    portfolio2 = flat_portfolio(equity_minor=100_000_00, captured_at_ns=T)
    if r1.decision in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE} and r1.approved_quantity > 0:
        from market_platform_foundation.intelligence.execution.types import PaperPositionSnapshot

        pos = PaperPositionSnapshot(
            instrument_id="inst-biya",
            symbol="BIYA",
            quantity=r1.approved_quantity,
            market_value_minor=r1.approved_notional_minor,
        )
        portfolio2 = flat_portfolio(
            equity_minor=100_000_00,
            cash_minor=100_000_00 - r1.approved_notional_minor,
            captured_at_ns=T,
        )
        portfolio2 = type(portfolio2)(
            snapshot_id=portfolio2.snapshot_id,
            schema_version=portfolio2.schema_version,
            captured_at_ns=portfolio2.captured_at_ns,
            cash_minor=portfolio2.cash_minor,
            equity_minor=portfolio2.equity_minor,
            currency=portfolio2.currency,
            price_scale=portfolio2.price_scale,
            positions=(pos,),
            open_orders=portfolio2.open_orders,
            reserved_cash_minor=portfolio2.reserved_cash_minor,
            exposure=portfolio2.exposure,
            realized_pnl_minor=portfolio2.realized_pnl_minor,
            unrealized_pnl_minor=portfolio2.unrealized_pnl_minor,
            start_of_day_equity_minor=portfolio2.start_of_day_equity_minor,
            peak_equity_minor=portfolio2.peak_equity_minor,
            scenario_id=portfolio2.scenario_id,
            mode=portfolio2.mode,
            metadata=portfolio2.metadata,
        )
    p2 = engine.build_proposal(
        opportunity=opp2,
        policy=policy,
        portfolio=portfolio2,
        quote=quote,
        proposal_time_ns=T,
        instrument_id="inst-biya",
        symbol="BIYA",
    )
    r2 = engine.assess(
        proposal=p2,
        opportunity=opp2,
        policy=policy,
        portfolio=portfolio2,
        decision_time_ns=T,
        symbol="BIYA",
        submitted_opportunity_ids=frozenset({opp1.opportunity_id}),
    )
    both_approved = (
        r1.decision in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE}
        and r2.decision in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE}
        and r1.approved_quantity > 0
        and r2.approved_quantity > 0
    )
    ok = not both_approved or (r1.approved_notional_minor + r2.approved_notional_minor) <= int(100_000_00 * 0.10) + 50_000_00
    return ScenarioResultV1("P06", ScenarioStatus.PASS if ok else ScenarioStatus.FAIL, "bounded_exposure", str(both_approved), {})


def _scenario_p07_governance_disabled() -> ScenarioResultV1:
    engine = PreTradeRiskEngine()
    governance = RuntimeGovernanceState(
        activation=None,
        fail_safe_decision=None,
        opportunities_allowed=True,
        paper_execution_allowed=False,
        scope_disabled=False,
    )
    rejected = False
    try:
        engine.build_proposal(
            opportunity=sample_opportunity(),
            policy=default_execution_policy(),
            portfolio=flat_portfolio(),
            quote=sample_quote(),
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
            runtime_governance=governance,
        )
    except Exception:
        rejected = True
    return ScenarioResultV1("P07", ScenarioStatus.PASS if rejected else ScenarioStatus.FAIL, "blocked", "rejected" if rejected else "allowed", {})


def _scenario_p08_live_authority_rejected() -> ScenarioResultV1:
    orchestrator = PaperExecutionOrchestrator()
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p08",
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_mode="LIVE",
        execution_authority="BLOCKED",
    )
    rejected = False
    try:
        orchestrator.execute_paper(
            opportunity=sample_opportunity(),
            policy=default_execution_policy(),
            portfolio=flat_portfolio(),
            quote=sample_quote(),
            ledger=ledger,
            bars=[],
            decision_time_ns=T,
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_authority="BLOCKED",
        )
    except Exception:
        rejected = True
    return ScenarioResultV1("P08", ScenarioStatus.PASS if rejected else ScenarioStatus.FAIL, "rejected", "rejected" if rejected else "allowed", {})


def _scenario_p09_sequential_portfolio() -> ScenarioResultV1:
    os.environ["IMP_PAPER_EXECUTION"] = "1"
    bars = sample_bars_for_execution(created_time_ns=T)
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p09",
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="AUTHORIZED",
    )
    orchestrator = PaperExecutionOrchestrator()
    policy = default_execution_policy(max_trade_notional_minor=5_000_00, trade_fraction_nav=0.02)
    portfolio1 = flat_portfolio(equity_minor=100_000_00, captured_at_ns=T)
    result1 = orchestrator.execute_paper(
        opportunity=sample_opportunity(opportunity_id="opp-seq-1", created_at_ns=T),
        policy=policy,
        portfolio=portfolio1,
        quote=sample_quote(available_time_ns=T),
        ledger=ledger,
        bars=bars,
        decision_time_ns=T,
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_authority="AUTHORIZED",
    )
    portfolio2 = snapshot_from_paper_ledger(ledger, captured_at_ns=T + 1)
    portfolio_changed = portfolio2.cash_minor < portfolio1.cash_minor or len(portfolio2.positions) > 0
    return ScenarioResultV1(
        "P09",
        ScenarioStatus.PASS if portfolio_changed or result1.risk_decision.decision.value == "REJECT" else ScenarioStatus.FAIL,
        "portfolio_evolved",
        str(portfolio_changed),
        {"cash_before": portfolio1.cash_minor, "cash_after": portfolio2.cash_minor},
    )


def _scenario_p10_fill_realism_buy() -> ScenarioResultV1:
    ok, codes = validate_quote_fill_realism(side="BUY", fill_price_minor=10100, bid_minor=9900, ask_minor=10100)
    bad, bad_codes = validate_quote_fill_realism(side="BUY", fill_price_minor=10000, bid_minor=9900, ask_minor=10100)
    return ScenarioResultV1(
        "P10",
        ScenarioStatus.PASS if ok and not bad else ScenarioStatus.FAIL,
        "ask_respected",
        str(bad_codes),
        {},
    )


def _scenario_p11_fill_realism_sell() -> ScenarioResultV1:
    ok, _ = validate_quote_fill_realism(side="SELL", fill_price_minor=9900, bid_minor=9900, ask_minor=10100)
    bad, bad_codes = validate_quote_fill_realism(side="SELL", fill_price_minor=10000, bid_minor=9900, ask_minor=10100)
    return ScenarioResultV1(
        "P11",
        ScenarioStatus.PASS if ok and not bad else ScenarioStatus.FAIL,
        "bid_respected",
        str(bad_codes),
        {},
    )


def _scenario_p12_counterfactual_masquerading() -> ScenarioResultV1:
    status, codes = validate_forward_lineage(
        evidence_class=PaperEvidenceClass.COUNTERFACTUAL_PAPER,
        forward_receipt_ref="ref",
        forecast_id="fc",
    )
    ok = status.value == "INVALID"
    return ScenarioResultV1("P12", ScenarioStatus.PASS if ok else ScenarioStatus.FAIL, "INVALID", status.value, {"codes": codes})


SCENARIO_REGISTRY: dict[str, Callable[[], ScenarioResultV1]] = {
    "P01": _scenario_p01_replay_masquerading,
    "P02": _scenario_p02_expired_opportunity,
    "P03": _scenario_p03_wide_spread_no_mid_fill,
    "P04": _scenario_p04_future_quote_forbidden,
    "P05": _scenario_p05_duplicate_order,
    "P06": _scenario_p06_concurrent_risk,
    "P07": _scenario_p07_governance_disabled,
    "P08": _scenario_p08_live_authority_rejected,
    "P09": _scenario_p09_sequential_portfolio,
    "P10": _scenario_p10_fill_realism_buy,
    "P11": _scenario_p11_fill_realism_sell,
    "P12": _scenario_p12_counterfactual_masquerading,
}


def run_scenarios(scenario_ids: tuple[str, ...] = REQUIRED_SCENARIOS) -> tuple[ScenarioResultV1, ...]:
    return tuple(SCENARIO_REGISTRY[sid]() for sid in scenario_ids)
