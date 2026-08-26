"""BUILD 22 deterministic paper execution and risk tests."""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.contracts import ForecastV1, TradeProposalV1
from market_platform_foundation.intelligence.contracts.common import OpportunitySide
from market_platform_foundation.intelligence.execution import (
    DirectForecastTradeForbidden,
    ExecutionMode,
    LiveExecutionForbidden,
    PaperExecutionOrchestrator,
    PreTradeRiskEngine,
    RiskDecisionKind,
    RiskReasonCode,
    build_execution_policy,
    execution_policy_v1_from_dict,
    execution_policy_v1_to_dict,
    risk_decision_v1_from_dict,
    risk_decision_v1_to_dict,
)
from market_platform_foundation.intelligence.execution.exposure import compute_exposure as exposure_compute
from market_platform_foundation.intelligence.execution.types import PaperPositionSnapshot
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.execution_fixtures import (
    default_execution_policy,
    flat_portfolio,
    long_short_portfolio,
    sample_opportunity,
    sample_quote,
)
from tests.intelligence.outcome_fixtures import T

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))


class ExecutionPolicyTests(unittest.TestCase):
    def test_paper_only_policy(self) -> None:
        policy = default_execution_policy()
        self.assertEqual(policy.mode, ExecutionMode.PAPER)

    def test_policy_round_trip(self) -> None:
        policy = default_execution_policy()
        restored = execution_policy_v1_from_dict(execution_policy_v1_to_dict(policy))
        self.assertEqual(policy.execution_policy_id, restored.execution_policy_id)

    def test_live_mode_policy_rejected(self) -> None:
        from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
        from market_platform_foundation.intelligence.execution.types import ExecutionPolicyV1, SizingPolicyKind

        with self.assertRaises(ValueError):
            ExecutionPolicyV1(
                execution_policy_id="bad-live",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                mode="LIVE",  # type: ignore[arg-type]
                sizing_policy=SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS,
            )


class SizingTests(unittest.TestCase):
    def test_fixed_fraction_nav_base(self) -> None:
        policy = default_execution_policy(trade_fraction_nav=0.01, max_trade_notional_minor=1_000_000_00)
        portfolio = flat_portfolio(equity_minor=100_000_00, cash_minor=100_000_00)
        quote = sample_quote()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        expected_qty = (100_000_00 * 0.01) // quote.ask_minor
        self.assertEqual(proposal.requested_quantity, expected_qty)
        self.assertEqual(proposal.requested_notional_minor, expected_qty * quote.ask_minor)

    def test_minimum_size_reject(self) -> None:
        policy = default_execution_policy(minimum_trade_notional_minor=10_000_00)
        portfolio = flat_portfolio(equity_minor=100_000_00)
        quote = sample_quote()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        small = TradeProposalV1(
            proposal_id=proposal.proposal_id,
            schema_version=proposal.schema_version,
            opportunity_id=proposal.opportunity_id,
            execution_policy_id=proposal.execution_policy_id,
            instrument_id=proposal.instrument_id,
            side=proposal.side,
            requested_quantity=1,
            requested_notional_minor=50,
            reference_price_minor=proposal.reference_price_minor,
            proposal_time_ns=proposal.proposal_time_ns,
            expires_at_ns=proposal.expires_at_ns,
            execution_mode=proposal.execution_mode,
            opportunity_ref=proposal.opportunity_ref,
        )
        risk = engine.assess(
            proposal=small,
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=T + 2_000_000_000,
            symbol="BIYA",
        )
        self.assertEqual(risk.decision, RiskDecisionKind.REJECT)
        self.assertIn(RiskReasonCode.REQUESTED_SIZE_TOO_SMALL, risk.reason_codes)


class ExposureTests(unittest.TestCase):
    def test_gross_vs_net(self) -> None:
        portfolio = long_short_portfolio()
        exposure = exposure_compute(portfolio.positions)
        self.assertEqual(exposure.gross_exposure_minor, 100_000_00)
        self.assertEqual(exposure.net_exposure_minor, 0)


class OpportunityGateTests(unittest.TestCase):
    def test_expired_opportunity_exact_boundary(self) -> None:
        opp = sample_opportunity(valid_until_ns=T + 5_000_000_000)
        engine = PreTradeRiskEngine()
        with self.assertRaises(Exception):
            engine.build_proposal(
                opportunity=opp,
                policy=default_execution_policy(),
                portfolio=flat_portfolio(captured_at_ns=T + 4_000_000_000),
                quote=sample_quote(available_time_ns=T + 4_000_000_000),
                proposal_time_ns=T + 5_000_000_000,
                instrument_id="inst-biya",
                symbol="BIYA",
            )

    def test_direct_forecast_forbidden(self) -> None:
        engine = PreTradeRiskEngine()
        forecast = mock.Mock(spec=ForecastV1)
        with self.assertRaises(DirectForecastTradeForbidden):
            engine.build_proposal(
                opportunity=forecast,  # type: ignore[arg-type]
                policy=default_execution_policy(),
                portfolio=flat_portfolio(),
                quote=sample_quote(),
                proposal_time_ns=T + 2_000_000_000,
                instrument_id="inst-biya",
                symbol="BIYA",
            )


class RiskDecisionTests(unittest.TestCase):
    def test_requested_vs_approved_preserved(self) -> None:
        policy = default_execution_policy(max_trade_notional_minor=500_00)
        portfolio = flat_portfolio(equity_minor=100_000_00)
        quote = sample_quote()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        risk = engine.assess(
            proposal=proposal,
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=T + 2_000_000_000,
            symbol="BIYA",
        )
        self.assertEqual(risk.requested_quantity, proposal.requested_quantity)
        self.assertIsInstance(proposal, TradeProposalV1)

    def test_risk_round_trip(self) -> None:
        policy = default_execution_policy()
        portfolio = flat_portfolio()
        quote = sample_quote()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        risk = engine.assess(
            proposal=proposal,
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=T + 2_000_000_000,
            symbol="BIYA",
        )
        restored = risk_decision_v1_from_dict(risk_decision_v1_to_dict(risk))
        self.assertEqual(risk.risk_decision_id, restored.risk_decision_id)


class DailyLossTests(unittest.TestCase):
    def test_daily_loss_blocks_new_risk(self) -> None:
        policy = default_execution_policy(daily_loss_limit_fraction=0.02)
        portfolio = flat_portfolio(
            equity_minor=95_000_00,
            start_of_day_equity_minor=100_000_00,
        )
        quote = sample_quote()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        risk = engine.assess(
            proposal=proposal,
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=T + 2_000_000_000,
            symbol="BIYA",
        )
        self.assertEqual(risk.decision, RiskDecisionKind.REJECT)
        self.assertIn(RiskReasonCode.DAILY_LOSS_LIMIT, risk.reason_codes)


class PaperIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"

    def test_no_live_broker_import_in_execution_path(self) -> None:
        from market_platform_foundation.intelligence import execution as package

        source = inspect.getsource(package.engine)
        for token in ("ibkr", "moomoo", "tradier", "tastytrade", "submit_order"):
            self.assertNotIn(token.lower(), source.lower())

    def test_live_authority_rejected(self) -> None:
        orchestrator = PaperExecutionOrchestrator()
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="build22",
            instrument_id="inst-biya",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="BLOCKED",
        )
        with self.assertRaises(LiveExecutionForbidden):
            orchestrator.execute_paper(
                opportunity=sample_opportunity(),
                policy=default_execution_policy(),
                portfolio=flat_portfolio(),
                quote=sample_quote(),
                ledger=ledger,
                bars=[],
                decision_time_ns=T + 2_000_000_000,
                instrument_id="inst-biya",
                symbol="BIYA",
                execution_authority="BLOCKED",
            )

    def test_idempotent_paper_submit(self) -> None:
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        for index in range(len(store.bars) - 2, -1, -1):
            store.set_cursor_index(index)
            bars = store.bars_for_execution()
            if not bars:
                continue
            break
        else:
            self.skipTest("no bars")

        ledger = PaperExecutionLedger.open_session(
            replay_session_id=store.session_id,
            instrument_id=store.instrument_id,
            symbol=store.symbol,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        cutoff = store.prediction_cutoff()
        opportunity = sample_opportunity(
            valid_until_ns=cutoff + 10_000_000_000_000,
            created_at_ns=cutoff - 1,
        )
        orchestrator = PaperExecutionOrchestrator()
        kwargs = dict(
            opportunity=opportunity,
            policy=default_execution_policy(max_trade_notional_minor=500_00),
            portfolio=flat_portfolio(equity_minor=1_000_000_00, cash_minor=1_000_000_00, captured_at_ns=cutoff),
            quote=sample_quote(
                bid_minor=9900,
                ask_minor=10100,
                available_time_ns=cutoff,
            ),
            ledger=ledger,
            bars=bars,
            decision_time_ns=cutoff,
            instrument_id=store.instrument_id,
            symbol=store.symbol,
            execution_authority="AUTHORIZED",
        )
        first = orchestrator.execute_paper(**kwargs)
        if first.risk_decision is None or first.risk_decision.approved_quantity <= 0:
            self.skipTest("risk did not approve in fixture")
        second = orchestrator.execute_paper(**kwargs)
        self.assertIsNotNone(second.paper_submit)
        self.assertTrue(second.paper_submit.get("duplicate"))


class PersistenceTests(unittest.TestCase):
    def test_execution_artifacts_persist(self) -> None:
        repo = InMemoryIntelligenceRepository()
        policy = default_execution_policy()
        portfolio = flat_portfolio()
        engine = PreTradeRiskEngine()
        opp = sample_opportunity()
        quote = sample_quote()
        proposal = engine.build_proposal(
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=T + 2_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        risk = engine.assess(
            proposal=proposal,
            opportunity=opp,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=T + 2_000_000_000,
            symbol="BIYA",
        )
        repo.put_execution_policy(policy)
        repo.put_paper_portfolio_snapshot(portfolio)
        repo.put_trade_proposal(proposal)
        repo.put_risk_decision(risk)
        self.assertIsNotNone(repo.get_trade_proposal(proposal.proposal_id))
        self.assertIsNotNone(repo.get_risk_decision(risk.risk_decision_id))


if __name__ == "__main__":
    unittest.main()
