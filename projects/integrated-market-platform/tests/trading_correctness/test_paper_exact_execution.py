"""Exact crypto execution uses the existing Paper account and event stream."""
from decimal import Decimal
import copy
import unittest

from market_platform_foundation.paper.contracts import build_instrument_ref, build_user_order_intent, build_semantic_intent_digest
from market_platform_foundation.paper.eligibility import admit_order_instrument
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.xa01.compatibility import register_crypto_pair
from market_platform_foundation.xa01.registry import InstrumentRegistry


def crypto(symbol="BTC/USD"):
    return dict(build_instrument_ref(instrument_id=symbol, symbol=symbol, asset_class="CRYPTO", venue="KRAKEN",
        instrument_kind="CRYPTO_PAIR", tradability="TRADABLE"), tick_size="0.0001", quantity_step="0.00001",
        minimum_quantity="0.0001", price_scale=10000)


def bars(price="10.1234", volume="1", available_time=200):
    return [dict(available_time=available_time, normalized_event_id="bar", bar_payload=dict(open=price, close=price, high=price, low=price, volume=volume))]


def ledger(cash=100000):
    policy = build_risk_policy(initial_cash_minor=cash, participation_cap_numerator=1, participation_cap_denominator=1)
    return PaperExecutionLedger.open_session(replay_session_id="exact", instrument_id="SEED", symbol="SEED", policy=policy,
        execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY", experiment_id="exact-test")


def submit(book, quantity="0.125", instrument=None, key="buy", side="BUY", feed=None):
    ref = instrument or crypto()
    return submit_interactive_order(ledger=book, bars=feed or bars(), symbol=ref["symbol"], instrument_id=ref["instrument_id"],
        instrument=ref, quantity=quantity, side=side, observation_time=100, client_order_id=key, idempotency_key=key)


class ExactPaperExecutionTests(unittest.TestCase):
    def test_fractional_intent_is_exact_and_stably_serialized(self):
        intent = build_user_order_intent(instrument=crypto(), side="BUY", quantity=Decimal("0.12500"), observation_time=100,
            client_order_id="a", idempotency_key="a")
        self.assertEqual(intent["desired_quantity"], "0.125")
        self.assertEqual(build_semantic_intent_digest(intent), build_semantic_intent_digest(dict(intent, desired_quantity="0.1250")))

    def test_crypto_rejects_invalid_or_unverified_quantities(self):
        for qty in (0.125, True, "NaN", "Infinity", "0.000001", "0.00001"):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                build_user_order_intent(instrument=crypto(), side="BUY", quantity=qty, observation_time=100, client_order_id="a", idempotency_key="a")
        ref = crypto()
        del ref["quantity_step"]
        with self.assertRaises(ValueError):
            build_user_order_intent(instrument=ref, side="BUY", quantity="0.125", observation_time=100, client_order_id="a", idempotency_key="a")

    def test_economics_revision_changes_semantic_digest(self):
        ref = crypto()
        left = dict(instrument=ref, instrument_id=ref["instrument_id"], side="BUY", desired_quantity="0.125", order_type="MARKET")
        right = copy.deepcopy(left)
        right["instrument"]["tick_size"] = "0.001"
        self.assertNotEqual(build_semantic_intent_digest(left), build_semantic_intent_digest(right))

    def test_canonical_and_provider_alias_admission_preserve_currency_and_venue(self):
        registry = InstrumentRegistry()
        identity = register_crypto_pair(base_asset="BTC", quote_asset="USD", venue_id="KRAKEN", provider_id="KRAKEN", provider_symbol="XBTUSD", registry=registry)
        for symbol, provider in ((identity, None), ("XBTUSD", "KRAKEN")):
            ref = admit_order_instrument(symbol, registry=registry, provider_id=provider)
            self.assertEqual(ref["instrument_id"], identity)
            self.assertEqual(ref["venue"], "KRAKEN")
            self.assertEqual(ref["asset_class"], "CRYPTO")
        with self.assertRaises(ValueError):
            admit_order_instrument("XBTUSD", registry=registry, provider_id="OTHER")

    def test_fractional_buy_close_and_replay_keep_cash_and_quantity(self):
        book = ledger()
        result = submit(book)
        self.assertEqual(result["fill"]["fill_quantity"], "0.125")
        self.assertEqual(result["fill"]["fill_price_minor"], 101234)
        self.assertEqual(book.project_positions()[0]["quantity"], "0.125")
        self.assertEqual(book.project_account()["cash_minor"], 99873)
        submit(book, quantity="0.025", side="SELL", key="close", feed=bars("12.1234"))
        self.assertEqual(book.project_positions()[0]["quantity"], "0.1")
        restored = PaperExecutionLedger(paper_account_id=book.paper_account_id, session_id=book.session_id,
            policy=book.policy.copy(), events=copy.deepcopy(book.events), execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.assertEqual(restored.project_positions(), book.project_positions())
        self.assertEqual(restored.project_account()["cash_minor"], book.project_account()["cash_minor"])

    def test_fractional_partial_fill_and_working_remaining_are_exact(self):
        book = ledger()
        result = submit(book, feed=bars(volume="0.100009"))
        self.assertEqual(result["fill"]["fill_quantity"], "0.1")
        self.assertEqual(book.project_orders()[0]["working_remaining"], "0.025")
        self.assertGreater(book.reserved_cash_minor(), 0)

    def test_participation_capacity_is_per_instrument(self):
        book = ledger()
        first = submit(book, quantity="0.1", feed=bars(volume="0.1"))
        second = submit(book, quantity="0.1", instrument=crypto("ETH/USD"), key="eth", feed=bars(volume="0.1"))
        self.assertIsNotNone(first["fill"])
        self.assertIsNotNone(second["fill"])

    def test_cash_gate_uses_execution_price_and_fees(self):
        book = ledger(cash=100)
        book.policy["fee_minor_per_order"] = 10
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_CASH"):
            submit(book, quantity="0.1", feed=bars("10.0000"))
        self.assertEqual(len(book.events), 2)

    def test_sell_cannot_overcommit_fractional_working_exit(self):
        book = ledger()
        submit(book, quantity="0.2")
        # Successive submissions are real successive bars: the per-ledger
        # simulator accumulates participation per (instrument, bar), so each
        # exit fills on its own later bar, not the entry bar.
        submit(book, quantity="0.15", side="SELL", key="sell1", feed=bars(volume="0.1", available_time=300))
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_POSITION"):
            submit(book, quantity="0.1", side="SELL", key="sell2", feed=bars(available_time=400))

    def test_unfunded_quote_currency_is_blocked_without_events(self):
        book = ledger()
        ref = crypto("BTC/USDT")
        ref["currency"] = "USDT"
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_SETTLEMENT_CURRENCY"):
            submit(book, instrument=ref)
        self.assertEqual(len(book.events), 2)


class CryptoTradeHistoryTests(unittest.TestCase):
    def test_fractional_history_preserves_fill_quantities_prices_and_net_pnl(self):
        book = ledger()
        book.policy["fee_minor_per_order"] = 2
        submit(book, quantity="0.2", feed=bars("10.0000"))
        submit(book, quantity="0.05", side="SELL", key="partial", feed=bars("12.0000", available_time=300))
        book.apply_live_mark(instrument_id="BTC/USD", mark_minor=120000,
            mark_provider="CONTROLLED_FIXTURE", mark_as_of_ns=300, mark_quality="PASS")
        self.assertEqual(book.project_account()["realized_pnl_minor"], 6)
        self.assertEqual(book.project_account()["cash_minor"], 99856)
        self.assertEqual(book.project_valuation(as_of_ns=300)["equity_minor"], 100036)
        self.assertEqual(sum(t["realized_pnl_delta_minor"] for t in book.project_trades()), 6)
        submit(book, quantity="0.15", side="SELL", key="close", feed=bars("12.0000", available_time=400))
        trades = book.project_trades()
        self.assertEqual(len(trades), 3)
        self.assertEqual([t["filled_quantity"] for t in trades], ["0.2", "0.05", "0.15"])
        self.assertEqual([t["position_before"] for t in trades], ["0", "0.2", "0.15"])
        self.assertEqual([t["position_after"] for t in trades], ["0.2", "0.15", "0"])
        self.assertEqual([t["position_effect"] for t in trades], ["OPEN", "REDUCE", "CLOSE"])
        self.assertEqual([t["fill_price_display"] for t in trades], ["10", "12", "12"])
        self.assertEqual([t["realized_pnl_delta_minor"] for t in trades], [-2, 8, 28])
        self.assertEqual(sum(t["realized_pnl_delta_minor"] for t in trades), 34)
        self.assertEqual(book.project_account()["realized_pnl_minor"], 34)
        self.assertEqual(book.project_account()["cash_minor"], 100034)
        self.assertEqual(book.project_valuation()["equity_minor"], 100034)
        restored = PaperExecutionLedger(paper_account_id=book.paper_account_id, session_id=book.session_id,
            policy=book.policy.copy(), events=copy.deepcopy(book.events), execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.assertEqual(restored.project_account(), book.project_account())
        self.assertEqual(restored.project_trades(), trades)
        self.assertEqual(restored.project_valuation()["equity_minor"], 100034)
        self.assertEqual([t["costs_minor"] for t in trades], [2, 2, 2])
        self.assertTrue(all(t["fill_kind"] == "SIMULATED_FILL" and not t["is_market_truth"] for t in trades))

    def test_trade_history_is_read_only_duplicate_safe_and_restart_exact(self):
        book = ledger()
        result = submit(book, quantity="0.2", feed=bars("10.0000"))
        again = submit(book, quantity="0.2", feed=bars("10.0000"))
        self.assertTrue(again["duplicate"])
        events = copy.deepcopy(book.events)
        trades = book.project_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["fill_id"], result["fill"]["fill_id"])
        self.assertEqual(book.project_trades(), trades)
        self.assertEqual(book.events, events)
        restored = PaperExecutionLedger(paper_account_id=book.paper_account_id, session_id=book.session_id,
            policy=book.policy.copy(), events=copy.deepcopy(events), execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.assertEqual(restored.project_trades(), trades)
        self.assertEqual(restored.project_account(), book.project_account())

    def test_crypto_partial_fill_history_counts_only_filled_units(self):
        book = ledger()
        result = submit(book, quantity="0.2", feed=bars("10.0000", volume="0.1"))
        self.assertEqual(result["fill"]["fill_quantity"], "0.1")
        trades = book.project_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual((trades[0]["requested_quantity"], trades[0]["filled_quantity"], trades[0]["position_after"]),
                         ("0.2", "0.1", "0.1"))


    def test_subminor_close_pnl_accumulates_without_losing_account_reconciliation(self):
        book = ledger()
        submit(book, quantity="0.005", feed=bars("10.0000"))
        for index in range(5):
            submit(book, quantity="0.001", side="SELL", key=f"close-{index}",
                   feed=bars("12.0000", available_time=300 + index))
        trades = book.project_trades()
        self.assertEqual(len(trades), 6)
        self.assertEqual(sum(t["realized_pnl_delta_minor"] for t in trades), 1)
        self.assertEqual(book.project_account()["realized_pnl_minor"], 1)
        self.assertEqual(book.project_account()["cash_minor"], 100001)
        self.assertEqual(book.project_positions(), [])
        restored = PaperExecutionLedger(paper_account_id=book.paper_account_id, session_id=book.session_id,
            policy=book.policy.copy(), events=copy.deepcopy(book.events), execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.assertEqual(restored.project_trades(), trades)
        self.assertEqual(restored.project_account(), book.project_account())

    def test_crypto_history_keeps_existing_equity_row_unchanged(self):
        book = ledger()
        submit_interactive_order(ledger=book, bars=bars("20.00"), symbol="AAPL", instrument_id="AAPL",
            quantity=1, side="BUY", observation_time=100, client_order_id="equity", idempotency_key="equity")
        equity = book.project_trades()[0]
        submit(book, quantity="0.1", feed=bars("10.0000"))
        trades = book.project_trades()
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0], equity)
        self.assertEqual(trades[0]["filled_quantity"], 1)
        self.assertEqual(trades[1]["filled_quantity"], "0.1")
        self.assertEqual(book.project_account()["cash_minor"], 97900)


    def test_duplicate_crypto_fill_receipt_does_not_duplicate_trade_history(self):
        book = ledger()
        book.policy["fee_minor_per_order"] = 2
        result = submit(book, quantity="0.1", feed=bars("10.0000"))
        book.append_fill(result["fill"], order=result["order"])
        self.assertEqual(len(book.project_trades()), 1)
        self.assertEqual(book.project_account()["cash_minor"], 99898)
        self.assertEqual(book.project_account()["total_fees_minor"], 2)
        self.assertEqual(book.project_account()["realized_pnl_minor"], -2)
        self.assertEqual(book.project_trades()[0]["costs_minor"], 2)
