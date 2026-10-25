"""Rebuild step 6 — Paper-only equity/ETF short selling.

Ledger-level proof for a short-enabled experiment account: the frozen ``allow_short`` term, the short-sale
gate (scope, price floor, short-sale restriction, 50% initial margin, no reversal), short proceeds held back
from buying power, mark-to-market, cover P&L, the 30% maintenance test, the simulated borrow fee, and the
BUILD 22 engine reading a real short with its sign and never blocking a cover. Accounts that do not allow
shorts keep their exact policy identity and their refusal.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes  # noqa: E402
from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.execution import (  # noqa: E402
    preview_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.experiment import build_experiment_policy  # noqa: E402
from market_platform_foundation.paper.ledger import SHORT_BORROW_BASIS, PaperExecutionLedger  # noqa: E402
from market_platform_foundation.paper.short_gate import (  # noqa: E402
    build_short_sale_facts,
    short_sale_facts_from_change_pct,
)
from market_platform_foundation.risk.policy import SHORT_POLICY_DEFAULTS, build_risk_policy  # noqa: E402

INITIAL = 10_000_000
FLAT_DAY = build_short_sale_facts(day_change_bps=0, source="TEST", as_of_ns=1)


def _bars(price: str) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {"close": price, "high": price, "low": price, "open": price, "volume": 1_000_000},
        }
        for i in range(1, 4)
    ]


def _ledger(*, allow_short: bool = True, mode: str = "INTERNAL_SIMULATION") -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="step6",
        instrument_id="PORTFOLIO",
        symbol="PORTFOLIO",
        policy=build_experiment_policy(allow_short=allow_short),
        execution_mode=mode,
        execution_authority="PAPER_ONLY",
        experiment_id="PPE-STEP6",
    )


class _Orders:
    def __init__(self, ledger: PaperExecutionLedger) -> None:
        self.ledger = ledger
        self.count = 0

    def submit(self, instrument_id: str, side: str, quantity: int, price: str, **kwargs: object) -> dict:
        self.count += 1
        key = f"k{self.count}"
        if side == "SELL" and "short_sale_facts" not in kwargs:
            kwargs["short_sale_facts"] = FLAT_DAY
        return submit_interactive_order(
            ledger=self.ledger,
            bars=_bars(price),
            symbol=instrument_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            observation_time=100,
            client_order_id=key,
            idempotency_key=key,
            **kwargs,
        )


def _mark(ledger: PaperExecutionLedger, instrument: str, minor: int) -> None:
    ledger.apply_live_mark(mark_minor=minor, mark_provider="CONTROLLED_FIXTURE", mark_as_of_ns=1,
                           mark_quality="PASS", instrument_id=instrument)


class ShortPolicyIdentityTests(unittest.TestCase):
    def test_off_policy_keeps_its_exact_body_and_hash(self) -> None:
        off = build_experiment_policy()
        self.assertEqual(off, build_experiment_policy(allow_short=False))
        self.assertNotIn("allow_short", off)
        self.assertFalse(set(SHORT_POLICY_DEFAULTS) & set(off))
        body = {key: value for key, value in off.items() if key != "risk_policy_identity_hash"}
        self.assertEqual(off["risk_policy_identity_hash"], sha256_bytes(canonical_bytes(body)))

    def test_short_terms_are_frozen_and_hashed(self) -> None:
        on = build_experiment_policy(allow_short=True)
        self.assertTrue(on["allow_short"])
        self.assertEqual(on["short_initial_margin_bps"], 5000)
        self.assertEqual(on["short_maintenance_margin_bps"], 3000)
        self.assertEqual(on["short_borrow_fee_bps_per_year"], 50)
        self.assertEqual(on["short_min_price_minor"], 500)
        self.assertEqual(on["short_ssr_drop_bps"], 1000)
        self.assertNotEqual(on["risk_policy_identity_hash"], build_experiment_policy()["risk_policy_identity_hash"])

    def test_short_terms_without_allow_short_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            build_risk_policy(short_initial_margin_bps=2500)
        with self.assertRaises(TypeError):
            build_risk_policy(allow_short=True, short_leverage=3)

    def test_shorts_exist_only_on_the_internal_simulator(self) -> None:
        self.assertTrue(_ledger().allows_short())
        self.assertFalse(_ledger(mode="BROKER_PAPER").allows_short())
        self.assertFalse(_ledger(allow_short=False).allows_short())


class ShortAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _ledger()
        self.orders = _Orders(self.ledger)

    def test_open_mark_and_cover_balance(self) -> None:
        self.orders.submit("AAA", "SELL", 100, "50.00")
        position = self.ledger.project_positions()[0]
        self.assertEqual(position["quantity"], -100)
        self.assertEqual(position["side"], "SHORT")
        _mark(self.ledger, "AAA", 5_000)
        valuation = self.ledger.project_valuation()
        # Proceeds are credited to cash, then held back with the 50% margin: buying power drops by $2,500.
        self.assertEqual(valuation["cash_minor"], INITIAL + 500_000)
        self.assertEqual(valuation["short_market_value_minor"], 500_000)
        self.assertEqual(valuation["short_margin_reserved_minor"], 750_000)
        self.assertEqual(valuation["buying_power_minor"], INITIAL - 250_000)
        self.assertEqual(valuation["buying_power_basis"], "CASH_LESS_WORKING_ORDER_RESERVATIONS_SHORT_MARGIN_RESERVED")
        self.assertEqual(valuation["borrow_basis"], SHORT_BORROW_BASIS)
        self.assertEqual(valuation["equity_minor"], INITIAL)
        _mark(self.ledger, "AAA", 4_800)
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["unrealized_pnl_minor"], 20_000)
        self.assertEqual(valuation["equity_minor"], INITIAL + 20_000)
        _mark(self.ledger, "AAA", 5_300)
        self.assertEqual(self.ledger.project_valuation()["equity_minor"], INITIAL - 30_000)
        self.orders.submit("AAA", "BUY", 100, "48.00")
        self.assertEqual(self.ledger.project_positions(), [])
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["realized_pnl_minor"], 20_000)
        self.assertEqual(valuation["cash_minor"], INITIAL + 20_000)
        self.assertEqual(valuation["buying_power_minor"], INITIAL + 20_000)
        self.assertEqual([t["position_effect"] for t in self.ledger.project_trades()], ["OPEN", "CLOSE"])

    def test_a_cover_is_never_refused_for_cash(self) -> None:
        self.orders.submit("AAA", "SELL", 100, "50.00")
        # The short rose 22x: the cover costs $110,000 against $105,000 of cash. Closing is still allowed and the
        # loss shows as negative cash and equity, never as a position the account cannot exit.
        self.orders.submit("AAA", "BUY", 100, "1100.00")
        self.assertEqual(self.ledger.project_positions(), [])
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["cash_minor"], INITIAL + 500_000 - 11_000_000)
        self.assertEqual(valuation["realized_pnl_minor"], -10_500_000)
        self.assertEqual(valuation["buying_power_minor"], 0)

    def test_short_proceeds_never_fund_a_long(self) -> None:
        self.orders.submit("AAA", "SELL", 100, "50.00")
        _mark(self.ledger, "AAA", 5_000)
        # Cash is $105,000 but buying power is $97,500: a $98,000 buy must be refused.
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit("BBB", "BUY", 100, "980.00")
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))
        self.orders.submit("BBB", "BUY", 100, "970.00")

    def test_maintenance_breach_is_declared_from_complete_marks(self) -> None:
        self.orders.submit("AAA", "SELL", 100, "50.00")
        self.assertFalse(self.ledger.short_margin_status()["maintenance_breached"])  # unmarked: never guessed
        _mark(self.ledger, "AAA", 70_000)
        status = self.ledger.short_margin_status()
        self.assertEqual(status["equity_minor"], INITIAL + 500_000 - 7_000_000)
        self.assertEqual(status["maintenance_requirement_minor"], 2_100_000)
        self.assertFalse(status["maintenance_breached"])
        _mark(self.ledger, "AAA", 90_000)
        status = self.ledger.short_margin_status()
        self.assertTrue(status["maintenance_breached"])
        self.assertTrue(self.ledger.project_valuation()["maintenance_breached"])

    def test_borrow_fee_is_charged_once_per_day(self) -> None:
        self.orders.submit("AAA", "SELL", 100, "50.00")
        _mark(self.ledger, "AAA", 5_000)
        events = self.ledger.accrue_short_borrow_fees(accrual_date="2026-10-26", as_of_ns=5)
        self.assertEqual(len(events), 1)
        payload = events[0]["payload"]
        # $5,000 x 0.50% / 360 = $0.0694, rounded up to $0.07.
        self.assertEqual(payload["fee_minor"], 7)
        self.assertEqual(payload["borrow_basis"], SHORT_BORROW_BASIS)
        self.assertEqual(self.ledger.accrue_short_borrow_fees(accrual_date="2026-10-26", as_of_ns=6), [])
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["total_borrow_fees_minor"], 7)
        self.assertEqual(valuation["cash_minor"], INITIAL + 500_000 - 7)
        self.assertEqual(valuation["realized_pnl_minor"], -7)
        self.assertEqual(valuation["equity_minor"], INITIAL - 7)

    def test_no_fee_without_shorts_or_on_an_off_account(self) -> None:
        self.assertEqual(self.ledger.accrue_short_borrow_fees(accrual_date="2026-10-26", as_of_ns=1), [])
        off = _ledger(allow_short=False)
        _Orders(off).submit("AAA", "BUY", 10, "50.00")
        self.assertEqual(off.accrue_short_borrow_fees(accrual_date="2026-10-26", as_of_ns=1), [])
        self.assertNotIn("short_margin_reserved_minor", off.project_valuation())


class ShortGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _ledger()
        self.orders = _Orders(self.ledger)

    def _refused(self, code: str, *args: object, **kwargs: object) -> None:
        before = len(self.ledger.events)
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit(*args, **kwargs)
        self.assertTrue(str(ctx.exception).startswith(code), str(ctx.exception))
        self.assertEqual(len(self.ledger.events), before)

    def test_unknown_day_change_is_refused(self) -> None:
        self._refused("SHORT_SALE_RESTRICTION_UNKNOWN", "AAA", "SELL", 10, "50.00", short_sale_facts=None)
        unknown = build_short_sale_facts(day_change_bps=None, source="DAY_CHANGE_UNAVAILABLE", as_of_ns=None)
        self._refused("SHORT_SALE_RESTRICTION_UNKNOWN", "AAA", "SELL", 10, "50.00", short_sale_facts=unknown)

    def test_short_sale_restriction_at_ten_percent_down(self) -> None:
        down10 = short_sale_facts_from_change_pct(-10.0, source="TEST", as_of_ns=1)
        self._refused("SHORT_SALE_RESTRICTION", "AAA", "SELL", 10, "50.00", short_sale_facts=down10)
        down9 = short_sale_facts_from_change_pct(-9.99, source="TEST", as_of_ns=1)
        self.orders.submit("AAA", "SELL", 10, "50.00", short_sale_facts=down9)

    def test_price_floor(self) -> None:
        self._refused("SHORT_PRICE_BELOW_MINIMUM", "AAA", "SELL", 10, "4.99")
        self.orders.submit("AAA", "SELL", 10, "5.00")

    def test_initial_margin_against_buying_power(self) -> None:
        # 100 x $2,500 = $250,000; 50% margin is $125,000 against $100,000 of buying power.
        self._refused("INSUFFICIENT_SHORT_MARGIN", "AAA", "SELL", 100, "2500.00")
        self.orders.submit("AAA", "SELL", 100, "1900.00")

    def test_no_reversal_either_way(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self._refused("POSITION_REVERSAL_NOT_ALLOWED", "AAA", "SELL", 150, "50.00")
        self.orders.submit("AAA", "SELL", 100, "50.00")  # an ordinary close needs no short facts
        self.orders.submit("BBB", "SELL", 100, "50.00")
        self._refused("POSITION_REVERSAL_NOT_ALLOWED", "BBB", "BUY", 150, "50.00")
        self.orders.submit("BBB", "BUY", 100, "50.00")

    def test_long_close_ignores_short_terms(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "4.00")
        self.orders.submit("AAA", "SELL", 100, "4.00", short_sale_facts=None)
        self.assertEqual(self.ledger.project_positions(), [])

    def test_admitted_security_is_shortable(self) -> None:
        # Equities and ETFs are both admitted as TRADABLE_SECURITY (xa01); the explicit kind is shortable.
        etf = dict(build_instrument_ref(instrument_id="SPY", symbol="SPY"), instrument_kind="TRADABLE_SECURITY")
        self.orders.submit("SPY", "SELL", 10, "500.00", instrument=etf)
        self.assertEqual(self.ledger.project_positions()[0]["quantity"], -10)

    def test_preview_runs_the_same_gate(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            preview_interactive_order(ledger=self.ledger, bars=_bars("50.00"), symbol="AAA", instrument_id="AAA",
                                      side="SELL", quantity=10, observation_time=100, client_order_id="p1",
                                      idempotency_key="p1")
        self.assertIn("SHORT_SALE_RESTRICTION_UNKNOWN", str(ctx.exception))
        preview = preview_interactive_order(ledger=self.ledger, bars=_bars("50.00"), symbol="AAA", instrument_id="AAA",
                                            side="SELL", quantity=10, observation_time=100, client_order_id="p2",
                                            idempotency_key="p2", short_sale_facts=FLAT_DAY)
        self.assertIsNotNone(preview)

    def test_off_account_still_refuses_a_sell_from_flat(self) -> None:
        off = _ledger(allow_short=False)
        with self.assertRaises(ValueError) as ctx:
            _Orders(off).submit("AAA", "SELL", 1, "50.00")
        self.assertIn("INSUFFICIENT_POSITION", str(ctx.exception))


class ShortEngineTests(unittest.TestCase):
    def test_snapshot_keeps_a_real_short_negative(self) -> None:
        from market_platform_foundation.intelligence.execution.snapshot import snapshot_from_paper_ledger

        ledger = _ledger()
        _Orders(ledger).submit("AAA", "SELL", 100, "50.00")
        _mark(ledger, "AAA", 5_000)
        snapshot = snapshot_from_paper_ledger(ledger, captured_at_ns=10)
        self.assertEqual(snapshot.positions[0].quantity, -100)
        self.assertEqual(snapshot.positions[0].market_value_minor, 500_000)
        self.assertEqual(snapshot.equity_minor, INITIAL)

    def test_cover_is_never_cut_by_exposure_cash_or_loss_limits(self) -> None:
        from market_platform_foundation.intelligence.contracts.common import OpportunitySide
        from market_platform_foundation.intelligence.execution import (
            PaperPositionSnapshot,
            PreTradeRiskEngine,
            RiskDecisionKind,
            build_portfolio_snapshot,
        )
        from tests.intelligence.execution_fixtures import default_execution_policy, sample_opportunity, sample_quote
        from tests.intelligence.outcome_fixtures import T

        # Short value is twice equity (gross cap 1.0x), cash is below the cover cost, and the day is down 50%.
        portfolio = build_portfolio_snapshot(
            equity_minor=1_000_000, cash_minor=50_000, captured_at_ns=T + 2_000_000_000,
            start_of_day_equity_minor=2_000_000,
            positions=(PaperPositionSnapshot(instrument_id="inst-biya", symbol="BIYA", quantity=-200,
                                             market_value_minor=2_000_000),),
        )
        policy = default_execution_policy(allow_short=True, daily_loss_limit_fraction=0.1)
        opportunity = sample_opportunity(opportunity_id="opp-cover", side=OpportunitySide.LONG,
                                         created_at_ns=T + 1_000_000_000, valid_until_ns=T + 10_000_000_000)
        engine = PreTradeRiskEngine()
        proposal = engine.build_proposal(opportunity=opportunity, policy=policy, portfolio=portfolio,
                                         quote=sample_quote(available_time_ns=T + 2_000_000_000),
                                         proposal_time_ns=T + 2_000_000_000, instrument_id="inst-biya", symbol="BIYA",
                                         allocation_desired_quantity=200)
        self.assertEqual(proposal.side, "BUY")
        self.assertEqual(proposal.requested_quantity, 200)
        risk = engine.assess(proposal=proposal, opportunity=opportunity, policy=policy, portfolio=portfolio,
                             decision_time_ns=T + 2_000_000_000, symbol="BIYA")
        self.assertEqual(risk.decision, RiskDecisionKind.APPROVE)
        self.assertEqual(risk.approved_quantity, 200)

    def test_short_open_still_needs_allow_short(self) -> None:
        from market_platform_foundation.intelligence.contracts.common import OpportunitySide
        from market_platform_foundation.intelligence.execution import PreTradeRiskEngine, RiskReasonCode
        from tests.intelligence.execution_fixtures import (
            default_execution_policy,
            flat_portfolio,
            sample_opportunity,
            sample_quote,
        )
        from tests.intelligence.outcome_fixtures import T

        opportunity = sample_opportunity(opportunity_id="opp-short", side=OpportunitySide.SHORT,
                                         created_at_ns=T + 1_000_000_000, valid_until_ns=T + 10_000_000_000)
        portfolio = flat_portfolio(captured_at_ns=T + 2_000_000_000)
        engine = PreTradeRiskEngine()
        for allow, expected in ((False, RiskReasonCode.SHORT_NOT_ALLOWED), (True, None)):
            policy = default_execution_policy(allow_short=allow)
            proposal = engine.build_proposal(opportunity=opportunity, policy=policy, portfolio=portfolio,
                                             quote=sample_quote(available_time_ns=T + 2_000_000_000),
                                             proposal_time_ns=T + 2_000_000_000, instrument_id="inst-biya",
                                             symbol="BIYA", requested_quantity=10)
            risk = engine.assess(proposal=proposal, opportunity=opportunity, policy=policy, portfolio=portfolio,
                                 decision_time_ns=T + 2_000_000_000, symbol="BIYA")
            if expected is None:
                self.assertGreater(risk.approved_quantity, 0)
            else:
                self.assertIn(expected, risk.reason_codes)
                self.assertEqual(risk.approved_quantity, 0)


class ShortLiveIsolationTests(unittest.TestCase):
    def test_live_canary_still_refuses_shorts(self) -> None:
        from dataclasses import replace

        from market_platform_foundation.intelligence.live_canary import policy as canary

        # A short-enabled Paper account exists in the same process; the canary policy never reads it.
        self.assertTrue(_ledger().allows_short())
        base = canary.build_default_canary_policy(broker="IBKR", account_ref="ACCT-STEP6")
        self.assertFalse(base.allow_short)
        self.assertEqual(base.allowed_sides, ("BUY",))
        self.assertIn("SHORT_NOT_ALLOWED_FIRST_CANARY", canary.validate_policy_constraints(replace(base, allow_short=True)))


if __name__ == "__main__":
    unittest.main()
