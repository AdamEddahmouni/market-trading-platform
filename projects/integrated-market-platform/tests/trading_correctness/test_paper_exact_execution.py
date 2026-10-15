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
