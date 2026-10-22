"""OCT1-09 — $100,000 Paper portfolio experiment accounting.

Ledger-level proof that one portfolio-scoped account balances: shared cash,
one position per instrument, instrument-keyed marks, realized / unrealized
P&L, total equity, costs, complete trade history, and replay equivalence.
Legacy instrument-scoped sessions keep their identity and pooled accounting.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes  # noqa: E402
from market_platform_foundation.paper.execution import (  # noqa: E402
    cancel_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.experiment import (  # noqa: E402
    EXPERIMENT_INITIAL_CAPITAL_MINOR,
    build_experiment_policy,
    build_experiment_record,
    cost_policy,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY, build_risk_policy  # noqa: E402

INITIAL = 10_000_000


def _bars(price: str, *, volume: int = 1_000_000) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {"close": price, "high": price, "low": price, "open": price, "volume": volume},
        }
        for i in range(1, 4)
    ]


def _experiment_ledger(
    *,
    experiment_id: str = "PPE-TEST",
    seed: str = "PORTFOLIO",
    policy: dict | None = None,
    authority: str = "PAPER_ONLY",
    mode: str = "INTERNAL_SIMULATION",
) -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="oct1-09",
        instrument_id=seed,
        symbol=seed,
        policy=policy or build_experiment_policy(),
        execution_mode=mode,
        execution_authority=authority,
        experiment_id=experiment_id,
    )


class _Orders:
    def __init__(self, ledger: PaperExecutionLedger) -> None:
        self.ledger = ledger
        self.count = 0

    def submit(self, instrument: str, side: str, quantity: int, price: str, **kwargs: object) -> dict:
        self.count += 1
        key = str(kwargs.pop("key", f"k{self.count}"))
        volume = int(kwargs.pop("volume", 1_000_000))
        return submit_interactive_order(
            ledger=self.ledger,
            bars=_bars(price, volume=volume),
            symbol=instrument,
            instrument_id=instrument,
            side=side,
            quantity=quantity,
            observation_time=100,
            client_order_id=key,
            idempotency_key=key,
            **kwargs,
        )


def _mark(ledger: PaperExecutionLedger, instrument: str, minor: int, *, quality: str = "PASS", as_of: int = 1) -> None:
    ledger.apply_live_mark(
        mark_minor=minor,
        mark_provider="CONTROLLED_FIXTURE",
        mark_as_of_ns=as_of,
        mark_quality=quality,
        instrument_id=instrument,
    )


class ExperimentCapitalTests(unittest.TestCase):
    def test_experiment_policy_is_exactly_100k_usd(self) -> None:
        policy = build_experiment_policy()
        self.assertEqual(EXPERIMENT_INITIAL_CAPITAL_MINOR, 10_000_000)
        self.assertEqual(policy["initial_cash_minor"], 10_000_000)
        self.assertEqual(policy["currency"], "USD")
        self.assertEqual(policy["price_scale"], 100)

    def test_default_policy_cash_is_unchanged(self) -> None:
        # The $100k is an experiment configuration, not a new global default.
        self.assertEqual(DEFAULT_RISK_POLICY["initial_cash_minor"], 1_000_000_00)
        self.assertNotEqual(
            build_experiment_policy()["risk_policy_identity_hash"],
            DEFAULT_RISK_POLICY["risk_policy_identity_hash"],
        )

    def test_initial_account_projection(self) -> None:
        ledger = _experiment_ledger()
        account = ledger.project_account()
        self.assertEqual(account["initial_cash_minor"], INITIAL)
        self.assertEqual(account["cash_minor"], INITIAL)
        self.assertEqual(account["buying_power_minor"], INITIAL)
        self.assertEqual(account["reserved_cash_minor"], 0)
        valuation = ledger.project_valuation()
        self.assertEqual(valuation["equity_minor"], INITIAL)
        self.assertEqual(valuation["total_pnl_minor"], 0)
        self.assertEqual(valuation["return_bps"], 0)
        self.assertEqual(valuation["quality"], "CURRENT")

    def test_record_rejects_non_100k_capital(self) -> None:
        with self.assertRaises(ValueError):
            build_experiment_record(
                experiment_id="PPE-X",
                name="x",
                created_at_ns=1,
                paper_account_id="a",
                paper_session_id="s",
                policy=build_risk_policy(initial_cash_minor=1_000_00),
                data_mode="FIXTURE_REPLAY",
                data_providers=["INTERNAL"],
                execution_provider="INTERNAL",
                execution_authority="PAPER_ONLY",
                source_scope="US_EQUITY_ETF",
            )

    def test_cost_policy_identity_changes_with_terms(self) -> None:
        base = cost_policy(build_experiment_policy())
        changed = cost_policy(build_risk_policy(initial_cash_minor=INITIAL, commission_minor_per_share=1))
        self.assertEqual(base["slippage_model"], "NOT_SEPARATELY_MODELED")
        self.assertNotEqual(base["cost_policy_id"], changed["cost_policy_id"])


class AccountIdentityTests(unittest.TestCase):
    def test_account_id_is_independent_of_instrument(self) -> None:
        first = _experiment_ledger(seed="AAPL")
        second = _experiment_ledger(seed="NVDA")
        self.assertEqual(first.paper_account_id, second.paper_account_id)
        self.assertTrue(first.is_portfolio_scoped())
        self.assertEqual(first.experiment_id, "PPE-TEST")

    def test_new_experiment_is_a_new_account(self) -> None:
        self.assertNotEqual(
            _experiment_ledger(experiment_id="PPE-A").paper_account_id,
            _experiment_ledger(experiment_id="PPE-B").paper_account_id,
        )

    def test_legacy_account_identity_is_byte_stable(self) -> None:
        policy = DEFAULT_RISK_POLICY
        ledger = PaperExecutionLedger.open_session(replay_session_id="legacy", instrument_id="AAPL", symbol="AAPL")
        expected = sha256_bytes(
            canonical_bytes(
                {
                    "currency": policy["currency"],
                    "initial_cash_minor": policy["initial_cash_minor"],
                    "instrument_id": "AAPL",
                    "replay_session_id": "legacy",
                }
            )
        )
        self.assertEqual(ledger.paper_account_id, expected)
        self.assertFalse(ledger.is_portfolio_scoped())
        self.assertIsNone(ledger.experiment_id)
        payload = ledger.events[0]["payload"]
        self.assertNotIn("account_identity_version", payload)
        self.assertNotIn("reserved_cash_minor", ledger.project_account())

    def test_legacy_ledger_keeps_pooled_position(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="legacy-pool",
            instrument_id="AAA",
            symbol="AAA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 10, "10.00")
        orders.submit("BBB", "BUY", 5, "20.00")
        # Legacy behaviour is preserved exactly: one pooled scalar position.
        self.assertEqual(ledger._project_ledger()["position_shares"], 15)
        self.assertEqual(len(ledger.project_positions()), 1)
        with self.assertRaises(ValueError):
            ledger.project_valuation()


class MultiInstrumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _experiment_ledger()
        self.orders = _Orders(self.ledger)

    def test_two_instruments_share_one_cash_account(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        self.assertEqual(self.ledger.project_account()["cash_minor"], INITIAL - 500_000 - 200_000)
        rows = {row["instrument_id"]: row for row in self.ledger.project_positions()}
        self.assertEqual(set(rows), {"AAA", "BBB"})
        self.assertEqual(rows["AAA"]["quantity"], 100)
        self.assertEqual(rows["BBB"]["quantity"], 10)
        self.assertEqual(rows["AAA"]["average_fill_minor"], 5_000)
        self.assertEqual(rows["BBB"]["average_fill_minor"], 20_000)

    def test_each_position_uses_only_its_own_mark(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        _mark(self.ledger, "AAA", 5_500)
        _mark(self.ledger, "BBB", 19_000)
        rows = {row["instrument_id"]: row for row in self.ledger.project_positions()}
        self.assertEqual(rows["AAA"]["mark_minor"], 5_500)
        self.assertEqual(rows["BBB"]["mark_minor"], 19_000)
        self.assertEqual(rows["AAA"]["unrealized_pnl_minor"], 50_000)
        self.assertEqual(rows["BBB"]["unrealized_pnl_minor"], -10_000)
        self.assertEqual(rows["AAA"]["market_value_minor"], 550_000)
        self.assertEqual(rows["BBB"]["market_value_minor"], 190_000)
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["position_value_minor"], 740_000)
        self.assertEqual(valuation["equity_minor"], INITIAL - 700_000 + 740_000)
        self.assertEqual(valuation["unrealized_pnl_minor"], 40_000)
        self.assertEqual(valuation["quality"], "CURRENT")

    def test_missing_mark_degrades_and_never_values_at_zero(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        _mark(self.ledger, "AAA", 5_500)
        rows = {row["instrument_id"]: row for row in self.ledger.project_positions()}
        self.assertEqual(rows["AAA"]["unrealized_pnl_minor"], 50_000)
        self.assertIsNone(rows["BBB"]["mark_minor"])
        self.assertIsNone(rows["BBB"]["unrealized_pnl_minor"])
        self.assertIsNone(rows["BBB"]["market_value_minor"])
        self.assertEqual(rows["BBB"]["mark_quality"], "UNAVAILABLE")
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["quality"], "PARTIAL")
        self.assertEqual(valuation["missing_mark_instruments"], ["BBB"])
        self.assertIsNone(valuation["equity_minor"])
        self.assertIsNone(valuation["total_pnl_minor"])
        self.assertIsNone(valuation["unrealized_pnl_minor"])
        # The part that can be valued is still reported, separately labelled.
        self.assertEqual(valuation["marked_position_value_minor"], 550_000)

    def test_no_marks_at_all_is_unavailable(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["quality"], "UNAVAILABLE")
        self.assertIsNone(valuation["equity_minor"])

    def test_last_fill_of_another_instrument_is_never_a_mark(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        rows = {row["instrument_id"]: row for row in self.ledger.project_positions()}
        self.assertIsNone(rows["AAA"]["mark_minor"])

    def test_stale_mark_propagates_to_portfolio_quality(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        _mark(self.ledger, "AAA", 5_500)
        _mark(self.ledger, "BBB", 19_000, quality="STALE")
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["quality"], "DEGRADED")
        self.assertEqual(valuation["degraded_instruments"], ["BBB"])
        # A stale mark still values the position, with the limitation attached.
        self.assertEqual(valuation["equity_minor"], INITIAL + 40_000)
        marks = {mark["instrument_id"]: mark for mark in valuation["marks"]}
        self.assertEqual(marks["BBB"]["quality"], "STALE")

    def test_mark_restore_returns_valuation_to_current(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        _mark(self.ledger, "AAA", 5_500, quality="STALE")
        self.assertEqual(self.ledger.project_valuation()["quality"], "DEGRADED")
        _mark(self.ledger, "AAA", 5_600, as_of=2)
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["quality"], "CURRENT")
        self.assertEqual(valuation["unrealized_pnl_minor"], 60_000)

    def test_invalid_marks_are_rejected(self) -> None:
        for bad in (0, -1, True, 1.5, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                _mark(self.ledger, "AAA", bad)  # type: ignore[arg-type]

    def test_valuation_reports_cutoff_and_individual_mark_times(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("BBB", "BUY", 10, "200.00")
        _mark(self.ledger, "AAA", 5_500, as_of=1_000)
        _mark(self.ledger, "BBB", 19_000, as_of=3_000)
        valuation = self.ledger.project_valuation(as_of_ns=9_000)
        self.assertEqual(valuation["valuation_cutoff_ns"], 9_000)
        self.assertEqual(valuation["oldest_mark_as_of_ns"], 1_000)
        self.assertEqual(valuation["newest_mark_as_of_ns"], 3_000)


class PositionAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _experiment_ledger()
        self.orders = _Orders(self.ledger)

    def test_partial_close_100_long_sell_40(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("AAA", "SELL", 40, "55.00")
        _mark(self.ledger, "AAA", 5_500)
        valuation = self.ledger.project_valuation()
        row = self.ledger.project_positions()[0]
        self.assertEqual(row["quantity"], 60)
        self.assertEqual(row["cost_basis_minor"], 300_000)
        self.assertEqual(row["average_fill_minor"], 5_000)
        self.assertEqual(valuation["realized_pnl_minor"], 20_000)
        self.assertEqual(valuation["unrealized_pnl_minor"], 30_000)
        self.assertEqual(valuation["cash_minor"], INITIAL - 500_000 + 220_000)
        self.assertEqual(valuation["equity_minor"], INITIAL + 50_000)

    def test_scale_in_weighted_average_and_entry_clocks(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("AAA", "BUY", 100, "60.00")
        row = self.ledger.project_positions()[0]
        self.assertEqual(row["quantity"], 200)
        self.assertEqual(row["cost_basis_minor"], 1_100_000)
        self.assertEqual(row["average_fill_minor"], 5_500)
        fills = self.ledger.project_fills()
        self.assertEqual(row["first_entry_time_ns"], fills[0]["fill_time"])
        self.assertEqual(row["latest_fill_time_ns"], fills[1]["fill_time"])
        self.assertEqual(len(fills), 2)

    def test_realized_uses_weighted_cost_not_latest_entry(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("AAA", "BUY", 100, "60.00")
        self.orders.submit("AAA", "SELL", 100, "58.00")
        # Weighted cost 55.00: realized = 100 x (58 - 55) = +300.00, not -200.00.
        self.assertEqual(self.ledger.project_valuation()["realized_pnl_minor"], 30_000)
        self.assertEqual(self.ledger.project_positions()[0]["cost_basis_minor"], 550_000)

    def test_full_close_goes_flat_and_reopen_restarts_entry_clock(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        self.orders.submit("AAA", "SELL", 100, "52.00")
        self.assertEqual(self.ledger.project_positions(), [])
        valuation = self.ledger.project_valuation()
        self.assertEqual(valuation["realized_pnl_minor"], 20_000)
        self.assertEqual(valuation["unrealized_pnl_minor"], 0)
        self.assertEqual(valuation["equity_minor"], INITIAL + 20_000)
        self.assertEqual(valuation["cash_minor"], INITIAL + 20_000)
        self.assertEqual(valuation["quality"], "CURRENT")
        effects = [trade["position_effect"] for trade in self.ledger.project_trades()]
        self.assertEqual(effects, ["OPEN", "CLOSE"])

    def test_reversal_is_rejected_not_treated_as_close(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        before = len(self.ledger.events)
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit("AAA", "SELL", 150, "50.00")
        self.assertIn("INSUFFICIENT_POSITION", str(ctx.exception))
        self.assertEqual(len(self.ledger.events), before)
        self.assertEqual(self.ledger.project_positions()[0]["quantity"], 100)

    def test_sell_without_position_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit("AAA", "SELL", 1, "50.00")
        self.assertIn("INSUFFICIENT_POSITION", str(ctx.exception))

    def test_sell_cannot_borrow_another_instruments_position(self) -> None:
        self.orders.submit("AAA", "BUY", 100, "50.00")
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit("BBB", "SELL", 10, "50.00")
        self.assertIn("INSUFFICIENT_POSITION", str(ctx.exception))

    def test_position_limit_is_per_instrument(self) -> None:
        for _ in range(5):
            self.orders.submit("AAA", "BUY", 100, "10.00")
        # AAA is at the 500-share cap; a different instrument is still admissible.
        result = self.orders.submit("BBB", "BUY", 100, "10.00")
        self.assertEqual(result["decision"], "APPROVE")
        rejected = self.orders.submit("AAA", "BUY", 100, "10.00")
        self.assertNotEqual(rejected["decision"], "APPROVE")


class CostAndInvariantTests(unittest.TestCase):
    def test_costs_are_explicit_and_counted_once(self) -> None:
        policy = build_risk_policy(initial_cash_minor=INITIAL, commission_minor_per_share=1, fee_minor_per_order=50)
        ledger = _experiment_ledger(policy=policy)
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")   # commission 100 + fee 50
        orders.submit("AAA", "SELL", 40, "55.00")   # commission 40 + fee 50
        _mark(ledger, "AAA", 5_500)
        valuation = ledger.project_valuation()
        self.assertEqual(valuation["total_commission_minor"], 140)
        self.assertEqual(valuation["total_fees_minor"], 100)
        self.assertEqual(valuation["total_transaction_costs_minor"], 240)
        self.assertEqual(valuation["cash_minor"], INITIAL - 500_000 - 150 + 220_000 - 90)
        # Gross realized 200.00 less every cost paid so far (240).
        self.assertEqual(valuation["realized_pnl_minor"], 20_000 - 240)
        self.assertEqual(valuation["unrealized_pnl_minor"], 30_000)
        # Costs live inside realized P&L only: equity = initial + realized + unrealized.
        self.assertEqual(
            valuation["equity_minor"],
            INITIAL + valuation["realized_pnl_minor"] + valuation["unrealized_pnl_minor"],
        )
        self.assertEqual(valuation["total_pnl_minor"], valuation["equity_minor"] - INITIAL)
        trades = ledger.project_trades()
        self.assertEqual(sum(t["commission_minor"] for t in trades), valuation["total_commission_minor"])
        self.assertEqual(sum(t["fees_minor"] for t in trades), valuation["total_fees_minor"])
        self.assertEqual(sum(t["realized_pnl_delta_minor"] for t in trades), valuation["realized_pnl_minor"])

    def test_accounting_invariant_across_a_mixed_lifecycle(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        steps = [
            ("AAA", "BUY", 100, "50.00"),
            ("BBB", "BUY", 10, "200.00"),
            ("AAA", "BUY", 50, "53.33"),
            ("AAA", "SELL", 70, "54.17"),
            ("BBB", "SELL", 3, "187.41"),
            ("AAA", "SELL", 80, "49.99"),
        ]
        for instrument, side, quantity, price in steps:
            orders.submit(instrument, side, quantity, price)
            for held in ledger.project_positions():
                _mark(ledger, held["instrument_id"], 12_345)
            valuation = ledger.project_valuation()
            self.assertEqual(
                valuation["equity_minor"],
                INITIAL + valuation["realized_pnl_minor"] + valuation["unrealized_pnl_minor"],
            )
            self.assertEqual(
                valuation["equity_minor"], valuation["cash_minor"] + valuation["position_value_minor"]
            )
            self.assertLessEqual(valuation["buying_power_minor"], valuation["cash_minor"])

    def test_return_is_basis_points_of_initial_capital(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")
        _mark(ledger, "AAA", 5_441)
        valuation = ledger.project_valuation()
        self.assertEqual(valuation["total_pnl_minor"], 44_100)
        self.assertEqual(valuation["return_bps"], 44)


class OrderVersusTradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _experiment_ledger()
        self.orders = _Orders(self.ledger)

    def test_risk_rejected_order_is_not_a_trade(self) -> None:
        result = self.orders.submit("AAA", "BUY", 1_000, "10.00")  # above max_order_shares
        self.assertNotEqual(result["decision"], "APPROVE")
        self.assertEqual(self.ledger.project_trades(), [])
        self.assertEqual(self.ledger.project_positions(), [])
        self.assertEqual(self.ledger.project_account()["cash_minor"], INITIAL)
        self.assertEqual(len(self.ledger.project_orders()), 1)

    def test_insufficient_cash_changes_nothing(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.orders.submit("AAA", "BUY", 100, "5000.00")
        self.assertIn("INSUFFICIENT", str(ctx.exception))
        self.assertEqual(self.ledger.project_account()["cash_minor"], INITIAL)
        self.assertEqual(self.ledger.project_trades(), [])

    def test_partial_fill_only_filled_quantity_counts(self) -> None:
        # 1/100 participation of a 2,000-share bar fills 20 of 100.
        result = self.orders.submit("AAA", "BUY", 100, "50.00", volume=2_000)
        order = result["order"]
        self.assertEqual(order["state"], "PARTIALLY_FILLED")
        row = self.ledger.project_positions()[0]
        self.assertEqual(row["quantity"], 20)
        account = self.ledger.project_account()
        self.assertEqual(account["cash_minor"], INITIAL - 20 * 5_000)
        trades = self.ledger.project_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["filled_quantity"], 20)
        self.assertEqual(trades[0]["requested_quantity"], 100)
        # The unfilled remainder reserves cash; it is not spent and not double counted.
        self.assertGreater(account["reserved_cash_minor"], 0)
        self.assertEqual(account["buying_power_minor"], account["cash_minor"] - account["reserved_cash_minor"])

    def test_cancelled_remainder_is_not_a_trade_and_frees_reservation(self) -> None:
        result = self.orders.submit("AAA", "BUY", 100, "50.00", volume=2_000)
        cancel_interactive_order(ledger=self.ledger, order_id=str(result["order_id"]))
        account = self.ledger.project_account()
        self.assertEqual(account["reserved_cash_minor"], 0)
        self.assertEqual(account["buying_power_minor"], account["cash_minor"])
        self.assertEqual(len(self.ledger.project_trades()), 1)
        self.assertEqual(self.ledger.project_positions()[0]["quantity"], 20)

    def test_duplicate_submit_does_not_double_debit(self) -> None:
        first = self.orders.submit("AAA", "BUY", 100, "50.00", key="dup-1")
        cash = self.ledger.project_account()["cash_minor"]
        second = self.orders.submit("AAA", "BUY", 100, "50.00", key="dup-1")
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["order_id"], first["order_id"])
        self.assertEqual(self.ledger.project_account()["cash_minor"], cash)
        self.assertEqual(self.ledger.project_positions()[0]["quantity"], 100)
        self.assertEqual(len(self.ledger.project_trades()), 1)

    def test_trade_row_carries_lineage_and_simulated_fill_label(self) -> None:
        snapshot = {
            "headline": "Action decision ENTER",
            "reasons": [
                {"code": "ACTION_DECISION", "label": "AD-123"},
                {"code": "ACTION_SNAPSHOT", "label": "AS-456"},
            ],
            "source_id": "opp-1",
            "source_type": "watched_opportunity",
        }
        lineage = [
            {"id": "AD-123", "kind": "ACTION_DECISION", "schema_version": "1"},
            {"id": "run-1", "kind": "CANDIDATE_RUN", "schema_version": "1"},
            {"id": "PV-1", "kind": "PAPER_PREVIEW", "schema_version": "1"},
        ]
        self.orders.submit(
            "AAA", "BUY", 10, "50.00",
            decision_source_snapshot=snapshot, lineage_refs=lineage, risk_decision_id="RD-9",
        )
        self.orders.submit("AAA", "SELL", 10, "51.00")
        governed, manual = self.ledger.project_trades()
        self.assertEqual(governed["decision_source"], "AI_DECISION_GOVERNED")
        self.assertEqual(governed["decision_id"], "AD-123")
        self.assertEqual(governed["risk_decision_id"], "RD-9")
        self.assertEqual({ref["kind"] for ref in governed["lineage_refs"]},
                         {"ACTION_DECISION", "CANDIDATE_RUN", "PAPER_PREVIEW"})
        self.assertEqual(governed["fill_kind"], "SIMULATED_FILL")
        self.assertFalse(governed["is_market_truth"])
        self.assertIsNone(governed["realized_pnl_minor"])
        self.assertEqual(manual["decision_source"], "MANUAL_TEST")
        self.assertEqual(manual["position_effect"], "CLOSE")
        self.assertEqual(manual["realized_pnl_minor"], 1_000)
        self.assertEqual(manual["position_after"], 0)
        self.assertTrue(governed["order_id"] and governed["fill_id"] and governed["intent_id"])


class ExecutionBoundaryTests(unittest.TestCase):
    def test_live_execution_mode_is_hard_rejected(self) -> None:
        ledger = _experiment_ledger(mode="LIVE", authority="AUTHORIZED")
        with self.assertRaises(ValueError) as ctx:
            _Orders(ledger).submit("AAA", "BUY", 1, "50.00")
        self.assertIn("PAPER_EXECUTION_MODE_INVALID", str(ctx.exception))
        self.assertEqual(ledger.project_trades(), [])

    def test_authority_loss_blocks_submit_but_portfolio_stays_readable(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")
        _mark(ledger, "AAA", 5_100)
        ledger.execution_authority = "BLOCKED"
        with self.assertRaises(ValueError) as ctx:
            orders.submit("AAA", "BUY", 1, "50.00")
        self.assertIn("PAPER_EXECUTION_NOT_AUTHORIZED", str(ctx.exception))
        self.assertEqual(ledger.project_positions()[0]["quantity"], 100)
        self.assertEqual(ledger.project_valuation()["equity_minor"], INITIAL + 10_000)

    def test_every_fill_is_labelled_simulation_not_market_truth(self) -> None:
        ledger = _experiment_ledger()
        _Orders(ledger).submit("AAA", "BUY", 1, "50.00")
        fill = ledger.project_fills()[0]
        self.assertFalse(fill["is_market_truth"])
        self.assertEqual(fill["execution_mode"], "INTERNAL_SIMULATION")
        self.assertEqual(fill["evidence_layer"], "IMP_EXECUTION_SIMULATION")


class ReplayReconciliationTests(unittest.TestCase):
    def test_replaying_events_reproduces_cash_positions_and_trades(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")
        orders.submit("BBB", "BUY", 10, "200.00")
        orders.submit("AAA", "SELL", 40, "55.00")
        rebuilt = PaperExecutionLedger(
            paper_account_id=ledger.paper_account_id,
            session_id=ledger.session_id,
            events=[dict(event) for event in ledger.events],
            policy=dict(ledger.policy),
            execution_mode=ledger.execution_mode,
            execution_authority=ledger.execution_authority,
        )
        self.assertTrue(rebuilt.is_portfolio_scoped())
        self.assertEqual(rebuilt.project_account(), ledger.project_account())
        self.assertEqual(rebuilt.project_trades(), ledger.project_trades())
        self.assertEqual(
            [(r["instrument_id"], r["quantity"], r["cost_basis_minor"]) for r in rebuilt.project_positions()],
            [(r["instrument_id"], r["quantity"], r["cost_basis_minor"]) for r in ledger.project_positions()],
        )

    def test_position_changed_events_match_the_projection(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")
        orders.submit("BBB", "BUY", 10, "200.00")
        changes = [e["payload"] for e in ledger.events if e["event_type"] == "PositionChanged"]
        self.assertEqual([c["instrument_id"] for c in changes], ["AAA", "BBB"])
        self.assertEqual(changes[-1]["cash_minor"], ledger.project_account()["cash_minor"])
        self.assertEqual(changes[-1]["position_shares"], 10)

    def test_each_fill_appears_exactly_once_in_trade_history(self) -> None:
        ledger = _experiment_ledger()
        orders = _Orders(ledger)
        orders.submit("AAA", "BUY", 100, "50.00")
        orders.submit("AAA", "BUY", 100, "50.00", key="k1")  # idempotent retry of the first order
        orders.submit("AAA", "SELL", 100, "50.00")
        fill_ids = [fill["fill_id"] for fill in ledger.project_fills()]
        trade_ids = [trade["fill_id"] for trade in ledger.project_trades()]
        self.assertEqual(trade_ids, fill_ids)
        self.assertEqual(len(set(trade_ids)), len(trade_ids))


if __name__ == "__main__":
    unittest.main()
