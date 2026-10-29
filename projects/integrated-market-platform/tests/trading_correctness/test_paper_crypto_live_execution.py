"""SOFTWARE_CONTROLLED: Kraken trade prints are the only execution price for internal Paper crypto.

The Kraken stream itself is a stand-in (lifecycle, acknowledgement and trade deque, exactly as the evidence
reader observes them) and the clock is controlled. The print-to-bar builder, the Paper bar source, the
pre-trade gate, the bar-conservative simulator, the ledger and the autonomous controller are production code.
Every fill here is a simulated fill against fixture prints, never market truth.
"""
from __future__ import annotations

import json
import os
import threading
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.crypto_market import kraken_stream
from market_platform_foundation.crypto_market.kraken_stream import BOOK, TRADES
from market_platform_foundation.paper.contracts import build_instrument_ref, order_quantity
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.ui_api import paper_projections, screener_crypto
from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
from tests.support.paper_automation_harness import Automation, policy_body
from tests.trading_correctness.test_paper_automation import AutoBase
from tests.trading_correctness.test_paper_exact_boundaries import CryptoAi

S = 1_000_000_000


class Tape:
    """Kraken Spot runtime stand-in: connection lifecycle, TRADES acknowledgement and per-pair trade deque."""

    def __init__(self, connected_ns):
        self._lock = threading.RLock()
        self.lifecycle = SimpleNamespace(connection_state='CONNECTED', connected_ns=connected_ns)
        self.acked, self.trades, self.markets, self.calls = {}, {}, {}, []
        self.subscriptions = SimpleNamespace(activated_at=self._activated_at)
        self.state = SimpleNamespace(trades_for=lambda iid: list(self.trades.get(iid, ())))
        self._ids = 0

    def _activated_at(self, *, instrument_id, capability):
        return self.acked.get(instrument_id) if capability == TRADES else None

    def ack(self, iid, at_ns):
        self.acked[iid] = at_ns

    def trade(self, iid, price, qty, *, received_ns, event_ns=None):
        self._ids += 1
        self.trades.setdefault(iid, []).append(dict(trade_id=str(self._ids), event_time_ns=received_ns - 1_000 if event_ns is None else event_ns,
                                                    available_time_ns=received_ns, received_ns=received_ns, price=price, quantity=qty, provider='KRAKEN'))

    def market(self, iid, price, qty, prints=None):
        """The venue prints this pair at this price and size on every read, ``prints`` times (``None``: always)."""
        self.markets[iid] = dict(price=price, qty=qty, prints=prints)

    def tick(self, iid, now_ns):
        market = self.markets.get(iid)
        if market is None or market['prints'] == 0:
            return
        if market['prints'] is not None:
            market['prints'] -= 1
        self.trade(iid, market['price'], market['qty'], received_ns=now_ns)

    def subscribe(self, *, instrument_id, capabilities, consumer_id):
        self.calls.append(('subscribe', instrument_id, tuple(capabilities)))
        return [dict(accepted=True) for _ in capabilities]

    def unsubscribe(self, *, instrument_id, capabilities, consumer_id):
        self.calls.append(('unsubscribe', instrument_id, tuple(capabilities)))


IID = 'XA01:NANOUSDFIXTURE'


def nano():
    """Live NANO/USD economics shape: 1e-8 lot, 1e-6 tick, ordermin 15, costmin 0.5."""
    return dict(build_instrument_ref(instrument_id=IID, symbol=IID, asset_class='CRYPTO', venue='KRAKEN', instrument_kind='CRYPTO_PAIR',
                                     tradability='TRADABLE'), tick_size='0.000001', quantity_step='0.00000001', minimum_quantity='15',
                price_scale=1_000_000, minimum_notional='0.5')


def book():
    # The live ledger's participation policy: 1/100 of observed venue quantity.
    policy = build_risk_policy(initial_cash_minor=10_000_000, participation_cap_numerator=1, participation_cap_denominator=100)
    return PaperExecutionLedger.open_session(replay_session_id='s2', instrument_id='SEED', symbol='SEED', policy=policy,
                                             execution_mode='INTERNAL_SIMULATION', execution_authority='PAPER_ONLY', experiment_id='s2-test')


class CryptoTradeBarContractTests(unittest.TestCase):
    """WP-B: the print-to-bar contract keeps the existing Kraken evidence rules."""

    def setUp(self):
        self.tape = Tape(connected_ns=100 * S)
        self.tape.ack(IID, 101 * S)
        self.reader = PaperMarketEvidence(kraken_runtime=self.tape)

    def bars(self, now_s=120):
        return self.reader.crypto_trade_bars(IID, now_ns=now_s * S)

    def test_fresh_prints_become_exact_complete_bars_in_receipt_order(self):
        self.tape.trade(IID, 0.987654, 1234.5, received_ns=118 * S)
        self.tape.trade(IID, 1e-05, 3000.0, received_ns=110 * S)
        bars = self.bars()
        self.assertEqual([b['available_time'] for b in bars], [110 * S, 118 * S])
        late = bars[1]
        self.assertEqual(late['bar_payload']['high'], '0.987654')
        self.assertEqual(late['bar_payload']['low'], '0.987654')
        self.assertEqual(late['bar_payload']['volume'], '1234.5')
        self.assertEqual(bars[0]['bar_payload']['close'], '0.00001')  # never exponent notation
        self.assertEqual(late['normalized_event_id'], f'KRAKEN:{IID}:TRADE:1')
        self.assertTrue(late['complete'] and late['bar_payload']['complete'])
        self.assertEqual((late['provider'], late['source'], late['volume_basis']), ('KRAKEN', 'KRAKEN_TRADE_PRINT', 'VENUE_TRADE_QUANTITY'))
        self.assertEqual(late['event_time'], 118 * S - 1_000)

    def test_stale_future_previous_connection_and_unacknowledged_prints_are_never_bars(self):
        self.tape.trade(IID, 1.0, 10.0, received_ns=104 * S)  # 16 s old: stale
        self.tape.trade(IID, 1.0, 10.0, received_ns=121 * S)  # received after now: future clock
        self.tape.trade(IID, 1.0, 10.0, received_ns=119 * S, event_ns=119 * S + 1)  # event after receipt
        self.tape.trade(IID, 1.0, 10.0, received_ns=119 * S, event_ns=90 * S)  # event 30 s old
        self.assertEqual(self.bars(), [])
        reader = PaperMarketEvidence(kraken_runtime=self.tape, clock=lambda: 120.0)
        self.assertEqual(reader.crypto_trade_bars(IID), [])  # default clock path agrees
        self.tape.trade(IID, 1.0, 10.0, received_ns=99 * S, event_ns=99 * S)
        wide = PaperMarketEvidence(kraken_runtime=self.tape, quote_max_age_seconds=60)
        # With a 60 s age bound only the clock-ordered prints of this connection remain; the 99 s print predates it.
        self.assertEqual([b['available_time'] for b in wide.crypto_trade_bars(IID, now_ns=120 * S)], [104 * S, 119 * S])
        self.tape.trade(IID, 1.0, 10.0, received_ns=118 * S)
        self.tape.ack(IID, 118 * S + 1)  # resubscribed after that print: it belongs to the earlier subscription
        self.assertEqual(self.bars(), [])
        self.tape.acked.pop(IID)
        self.assertEqual(self.bars(), [])
        self.tape.ack(IID, 101 * S)
        self.tape.lifecycle.connection_state = 'RECONNECTING'
        self.assertEqual(self.bars(), [])
        self.assertEqual(PaperMarketEvidence(kraken_runtime=None).crypto_trade_bars(IID, now_ns=120 * S), [])

    def test_reader_observes_only(self):
        self.tape.trade(IID, 1.0, 10.0, received_ns=118 * S)
        self.bars()
        self.assertEqual(self.tape.calls, [])


class PaperBarSourceRoutingTests(unittest.TestCase):
    """D1: crypto previews and submits read Kraken prints; equities keep the Moomoo L1 buffer unchanged."""

    def setUp(self):
        self.tape = Tape(connected_ns=100 * S)
        self.tape.ack(IID, 101 * S)
        self.tape.trade(IID, 0.987654, 2000.0, received_ns=118 * S)
        self.buffer = SimpleNamespace(bars_for_execution=lambda **kw: [dict(available_time=1, source='LIVE_L1_SNAPSHOT', kw=kw)])
        self.moomoo = SimpleNamespace(execution_buffer=self.buffer)
        self.store = SimpleNamespace(paper_ledger=SimpleNamespace(policy=dict(price_scale=100)), bars_for_execution=lambda: ['REPLAY'])
        for target, value in (('market_platform_foundation.crypto_market.kraken_stream._RUNTIME', self.tape),
                              ('market_platform_foundation.clock.monotonic_wall_ns', lambda: 120 * S),
                              ('market_platform_foundation.market_data.live_runtime.get_live_runtime', lambda create=False: self.moomoo)):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def source(self, env, instrument):
        with patch.dict(os.environ, env):
            return paper_projections._bars_for_paper_execution(self.store, instrument_id=IID, instrument=instrument)

    def test_crypto_reads_its_own_venue_prints_and_never_the_equity_buffer(self):
        bars = self.source(dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='1'), nano())
        self.assertEqual([b['source'] for b in bars], ['KRAKEN_TRADE_PRINT'])
        self.assertEqual(bars[0]['bar_payload']['high'], '0.987654')

    def test_equities_and_replay_keep_their_existing_sources(self):
        live = dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='1')
        self.assertEqual(self.source(live, dict(instrument_kind='TRADABLE_SECURITY'))[0]['source'], 'LIVE_L1_SNAPSHOT')
        self.assertEqual(self.source(live, None)[0]['source'], 'LIVE_L1_SNAPSHOT')
        self.assertEqual(self.source(dict(IMP_LIVE_OBSERVATIONAL='0'), nano()), ['REPLAY'])

    def test_crypto_without_the_live_wall_clock_fails_closed(self):
        self.assertEqual(self.source(dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='0'), nano()), [])
        with patch('market_platform_foundation.market_data.live_runtime.get_live_runtime', lambda create=False: None):
            self.assertEqual(self.source(dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='1'), nano()), [])

    def test_market_submit_waits_for_a_post_intent_print_within_the_bound(self):
        live = dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='1', IMP_LIVE_EXECUTION_WAIT_MS='2000')
        reads = []

        def later_print(iid):
            reads.append(iid)
            if len(reads) == 3:
                self.tape.trade(IID, 0.987655, 2000.0, received_ns=119 * S)
            return PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(iid, now_ns=120 * S)

        initial = self.source(live, nano())
        with patch.dict(os.environ, live), patch.object(paper_projections, '_crypto_execution_bars', later_print):
            bars = paper_projections._wait_for_post_intent_bars(self.store, instrument_id=IID, created_time_ns=118 * S + 5,
                                                                bars=initial, instrument=nano())
        self.assertEqual([b['bar_payload']['high'] for b in bars if b['available_time'] > 118 * S + 5], ['0.987655'])
        live['IMP_LIVE_EXECUTION_WAIT_MS'] = '100'
        with patch.dict(os.environ, live):
            bars = paper_projections._wait_for_post_intent_bars(self.store, instrument_id=IID, created_time_ns=119 * S + 5,
                                                                bars=initial, instrument=nano())
        self.assertFalse([b for b in bars if b['available_time'] > 119 * S + 5])  # no print: nothing to fill against


class CryptoPrintExecutionTests(unittest.TestCase):
    """WP-B/C/D at the ledger: real pre-trade gate and simulator against print bars."""

    def setUp(self):
        self.tape = Tape(connected_ns=100 * S)
        self.tape.ack(IID, 101 * S)
        self.book = book()
        self.n, self.now = 0, 115 * S

    def bars(self):
        return PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID, now_ns=self.now)

    def submit(self, quantity, side='BUY', intent_s=110):
        self.n += 1
        return submit_interactive_order(ledger=self.book, bars=self.bars(), symbol=IID, instrument_id=IID, instrument=nano(), quantity=quantity,
                                        side=side, observation_time=int(intent_s * S), client_order_id=f'k{self.n}', idempotency_key=f'k{self.n}')

    def test_post_intent_print_fills_at_the_exact_venue_price(self):
        self.tape.trade(IID, 0.987654, 3000.0, received_ns=111 * S)
        result = self.submit('20')
        self.assertEqual(result['order']['state'], 'FILLED')
        self.assertEqual(result['fill']['fill_quantity'], '20')
        self.assertEqual(result['fill']['fill_price_minor'], 987654)
        self.assertEqual(result['fill']['normalized_event_id'], f'KRAKEN:{IID}:TRADE:1')
        self.assertEqual(self.book.project_positions()[0]['quantity'], '20')

    def test_participation_partial_fill_never_leaves_a_sub_minimum_remainder(self):
        self.tape.trade(IID, 1.0, 2500.0, received_ns=111 * S)
        result = self.submit('40')  # 1% of 2500 = 25; remainder 15 is a valid order
        self.assertEqual((result['order']['state'], result['fill']['fill_quantity']), ('PARTIALLY_FILLED', '25'))
        self.tape.trade(IID, 1.0, 3000.0, received_ns=112 * S)
        result = self.submit('40', intent_s=111.5)  # 1% = 30 would leave 10 < ordermin 15: reduced to 25
        self.assertEqual(result['fill']['fill_quantity'], '25')

    def test_sub_minimum_participation_is_no_fill_and_no_unclosable_position(self):
        self.tape.trade(IID, 1.0, 1000.0, received_ns=111 * S)
        result = self.submit('20')  # 1% = 10 < ordermin 15
        self.assertIsNone(result['fill'])
        self.assertEqual(result['order']['reason_codes'], ['SIM_NO_ELIGIBLE_VOLUME'])
        self.assertEqual(self.book.project_positions(), [])
        with self.assertRaisesRegex(ValueError, 'ORDER_QUANTITY_INCREMENT_INVALID'):
            order_quantity('10', nano())  # why: a 10-unit position could never be closed at this venue

    def test_print_before_the_intent_is_never_filled_against(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=109 * S)
        result = self.submit('20')
        self.assertIsNone(result['fill'])
        self.assertEqual(result['order']['reason_codes'], ['SIM_NO_POST_SIGNAL_BAR'])
        self.assertEqual(self.book.project_account()['cash_minor'], 10_000_000)

    def test_missing_or_stale_prints_refuse_before_any_ledger_event(self):
        before = list(self.book.events)
        for side in ('BUY', 'SELL'):
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, 'REQUIRED_PRICE_MISSING'):
                self.submit('20', side=side)
        self.tape.trade(IID, 1.0, 3000.0, received_ns=112 * S)
        with patch.object(self, 'bars', lambda: PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID, now_ns=200 * S)):
            with self.assertRaisesRegex(ValueError, 'REQUIRED_PRICE_MISSING'):
                self.submit('20')
        self.assertEqual(self.book.events, before)

    def test_off_tick_print_is_an_invalid_fill_price(self):
        self.tape.trade(IID, 0.9876545, 3000.0, received_ns=111 * S)
        result = self.submit('20')
        self.assertIsNone(result['fill'])
        self.assertEqual(result['order']['reason_codes'], ['SIM_INVALID_FILL_PRICE'])

    def test_crypto_short_from_flat_is_refused_before_any_ledger_event(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=111 * S)
        before = list(self.book.events)
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_POSITION'):
            self.submit('20', side='SELL')
        self.assertEqual(self.book.events, before)

    def test_exit_fills_against_its_own_post_intent_print_with_exact_pnl(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=111 * S)
        self.submit('20')
        self.tape.trade(IID, 1.25, 3000.0, received_ns=121 * S)
        self.now = 125 * S
        result = self.submit('20', side='SELL', intent_s=120)
        self.assertEqual((result['order']['state'], result['fill']['fill_price_minor']), ('FILLED', 1_250_000))
        self.assertEqual(self.book.project_positions(), [])
        self.assertEqual(self.book.project_account()['realized_pnl_minor'], 500)
        self.assertEqual(self.book.project_account()['cash_minor'], 10_000_500)


class RecordedCryptoSizingTests(unittest.TestCase):
    """WP-C: the 2026-10-27 operational intents re-sized from the live policy and Kraken economics, unchanged."""

    # Policy PAP-c52691998c1a5d2fb5f29ca7e6c9ea12 risk section and the operational ledger caps, as deployed.
    POLICY = dict(risk=dict(max_position_notional_minor=500_000, max_per_trade_risk_minor=50_000, assumed_adverse_move_bps=200,
                            max_aggregate_exposure_minor=7_500_000))
    LEDGER = dict(max_order_shares=100, max_position_shares=500, price_scale=100)

    def size(self, price_minor, *, pair_decimals, lot_decimals, ordermin):
        from market_platform_foundation.intelligence.inference.paper_automation import size_entry
        instrument = dict(instrument_kind='CRYPTO_PAIR', quantity_step=str(Decimal(1).scaleb(-lot_decimals)), minimum_quantity=ordermin,
                          contract_multiplier='1', price_scale=10 ** pair_decimals)
        return size_entry(self.POLICY, price_minor=price_minor, positions=[], buying_power_minor=10_000_000, ledger_policy=self.LEDGER,
                          instrument=instrument)

    def test_sub_cent_long_entries_are_below_the_venue_minimum_under_the_order_cap(self):
        cases = {  # pair: (price minor, pair decimals, lot decimals, ordermin, recorded MAX_POSITION_NOTIONAL bound)
            'BANANAS31/USD': (5960, 6, 5, '600', '838926.17449'),
            'ALEO/USD': (3296, 5, 5, '180', '151699.02912'),
            'FLR/USD': (604, 5, 8, '700', '827814.56953642'),
        }
        for pair, (price, pair_decimals, lot_decimals, ordermin, notional) in cases.items():
            with self.subTest(pair=pair):
                sizing = self.size(price, pair_decimals=pair_decimals, lot_decimals=lot_decimals, ordermin=ordermin)
                self.assertEqual((sizing['quantity'], sizing['binding']), ('0', 'PAPER_ACCOUNT_MAX_ORDER_SHARES'))
                self.assertEqual(sizing['bounds']['MAX_POSITION_NOTIONAL'], notional)
                self.assertEqual(sizing['bounds']['PAPER_ACCOUNT_MAX_ORDER_SHARES'], '100')

    def test_recorded_short_entry_sizes_reproduce_exactly(self):
        bnb = self.size(73587, pair_decimals=2, lot_decimals=5, ordermin='0.007')
        self.assertEqual((bnb['quantity'], bnb['binding'], bnb['bounds']['BUYING_POWER']), ('6.79467', 'MAX_POSITION_NOTIONAL', '135.89356'))
        nano_size = self.size(331858, pair_decimals=6, lot_decimals=8, ordermin='15')
        self.assertEqual((nano_size['quantity'], nano_size['binding']), ('100', 'PAPER_ACCOUNT_MAX_ORDER_SHARES'))
        self.assertEqual(nano_size['bounds']['MAX_POSITION_NOTIONAL'], '15066.68514846')

    def test_print_bars_never_widen_the_ledger_order_cap(self):
        tape = Tape(connected_ns=100 * S)
        tape.ack(IID, 101 * S)
        tape.trade(IID, 1.0, 1_000_000.0, received_ns=111 * S)
        ledger = book()
        result = submit_interactive_order(ledger=ledger, bars=PaperMarketEvidence(kraken_runtime=tape).crypto_trade_bars(IID, now_ns=115 * S),
                                          symbol=IID, instrument_id=IID, instrument=nano(), quantity='150', side='BUY',
                                          observation_time=110 * S, client_order_id='cap', idempotency_key='cap')
        self.assertEqual((result['decision'], result['order']['reason_codes'], result['fill']), ('REJECT', ['SIM_RISK_NOT_APPROVED'], None))
        self.assertIn('RISK_MAX_ORDER_EXCEEDED', json.dumps(ledger.events, default=str))
        self.assertEqual(ledger.project_positions(), [])


class CryptoAutonomousExecutionTests(AutoBase):
    """WP-D: the armed controller, from a gated decision to a simulated fill, priced only by venue prints."""

    def setUp(self):
        super().setUp()
        payload = {'error': [], 'result': {'BTC/USD': dict(base='BTC', quote='USD', aclass_base='currency', aclass_quote='currency',
            status='online', ordermin='0.001', costmin='1', tick_size='0.0001', lot_decimals=3, pair_decimals=4, cost_decimals=2)}}
        self.crypto_source = screener_crypto.CryptoScreener(client=SimpleNamespace(asset_pairs=lambda: payload), env={'IMP_CRYPTO_LIVE': '1'})
        rows, _, error = self.crypto_source._catalog()
        self.assertIsNone(error)
        self.iid = rows[0]['instrument']['instrument_id']
        self.tape = Tape(connected_ns=int(self.clock() * S) - S)
        self.tape.ack(self.iid, int(self.clock() * S) - S)
        fixture_bars = paper_projections._bars_for_paper_execution  # the harness feed, for anything that is not crypto

        def bars(store, *, instrument_id=None, instrument=None):
            if (instrument or {}).get('instrument_kind') != 'CRYPTO_PAIR':
                return fixture_bars(store, instrument_id=instrument_id, instrument=instrument)
            self.tape.tick(instrument_id, self.feed.now_ns())  # the venue prints now, if it is printing
            with patch('market_platform_foundation.clock.monotonic_wall_ns', self.feed.now_ns):
                return paper_projections._crypto_execution_bars(instrument_id)

        for patcher in (patch.object(screener_crypto, '_SERVICE', self.crypto_source), patch.object(kraken_stream, '_RUNTIME', self.tape),
                        patch.object(paper_projections, '_bars_for_paper_execution', bars)):
            patcher.start()
            self.addCleanup(patcher.stop)
        ai = CryptoAi(self.clock, self.auto.provider)
        ai.rows = {}
        ai.selected = []
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, ai=ai, provider=self.auto.provider)

        def mark(store, instrument_id, price, quality='PASS'):
            from market_platform_foundation.local_state.startup import persist_ledger
            ref = store.paper_ledger.instrument_for(instrument_id)
            store.paper_ledger.apply_live_mark(instrument_id=instrument_id, mark_minor=int(Decimal(price) * int(ref.get('price_scale', 100))),
                                               mark_provider='CONTROLLED_FIXTURE', mark_as_of_ns=self.feed.now_ns(), mark_quality=quality, freshness_ms=0)
            persist_ledger(store.paper_ledger)
        self.feed.mark = mark

    def start_crypto(self):
        a = self.auto
        a.quote(self.iid, 800, 2)
        a.opportunity(self.iid)
        body = policy_body(risk=dict(allowed_universes=['US_EQUITIES', 'CRYPTO'], max_position_notional_minor=90000))
        body['scopes'] = [dict(scope=dict(body['scope']), sessions=['REGULAR']), dict(scope=dict(universe='CRYPTO'), sessions=['CONTINUOUS'])]
        a.session_label = 'CLOSED'
        a.service.configure(body)
        a.arm()
        a.service.start(threaded=False)
        a.cycle()
        a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'], [self.iid])
        return a.cycle()

    def outcomes(self, receipt):
        return [(r['outcome'], r['reason_codes']) for r in receipt['actions']]

    def test_entry_partial_fill_remainder_cancel_exit_pnl_restart_and_duplicate(self):
        a = self.auto
        self.tape.market(self.iid, 800.0, 50.0)  # 1% of each 50 BTC print is 0.5
        receipt = self.start_crypto()
        entry = [r for r in receipt['actions'] if r['outcome'] == 'SUBMITTED']
        self.assertEqual(len(entry), 1, receipt)
        self.assertEqual((entry[0]['quantity'], entry[0]['filled_quantity']), ('1.125', '0.5'))
        self.assertEqual(entry[0]['order_state'], 'PARTIALLY_FILLED')
        self.assertEqual(a.orders()[0]['state'], 'CANCELLED')  # the unfilled remainder never stays working
        self.assertEqual(a.position(self.iid)['quantity'], '0.5')
        self.assertEqual(a.store.paper_ledger.project_fills()[0]['fill_price_minor'], 8_000_000)
        self.assertEqual(a.store.paper_ledger.project_account()['cash_minor'], 9_960_000)
        decision = a.actions.history(self.iid)[0]
        self.assertEqual(decision['action_state'], 'ENTER')
        self.assertIsNone(a.service.execute_decision(decision, a.service.status()['policy'], a.service._controller(), a.session(self.clock())))
        self.assertEqual(len(a.orders()), 1)
        a.quote(self.iid, 820, -2)
        self.tape.market(self.iid, 820.0, 100.0)
        closing = a.cycle(400)
        exits = [r for r in closing['actions'] if r['outcome'] == 'SUBMITTED']
        self.assertEqual([(r['quantity'], r['filled_quantity']) for r in exits], [('0.5', '0.5')], closing)
        self.assertIsNone(a.position(self.iid))
        account = a.store.paper_ledger.project_account()
        self.assertEqual((account['realized_pnl_minor'], account['cash_minor']), (1000, 10_001_000))
        history = a.store.paper_ledger.project_trades()
        restarted = self.restart()
        self.assertEqual(restarted.store.paper_ledger.project_trades(), history)
        self.assertEqual(restarted.store.paper_ledger.project_account()['cash_minor'], 10_001_000)
        self.assertIsNone(restarted.service.execute_decision(decision, restarted.service.status()['policy'], restarted.service._controller(),
                                                             restarted.session(self.clock())))
        self.assertEqual(len(restarted.orders()), 2)

    def test_no_fresh_print_defers_then_a_live_print_executes_the_same_decision(self):
        a = self.auto
        receipt = self.start_crypto()
        self.assertIn(('DEFERRED', ['REQUIRED_PRICE_MISSING']), self.outcomes(receipt))
        self.assertEqual(a.orders(), [])
        self.assertEqual(a.store.paper_ledger.project_account()['cash_minor'], 10_000_000)
        self.tape.market(self.iid, 800.0, 200.0)
        a.quote(self.iid, 800, 2)
        receipt = a.cycle()
        self.assertEqual([(r['outcome'], r['filled_quantity']) for r in receipt['actions'] if r['outcome'] == 'SUBMITTED'], [('SUBMITTED', '1.125')], receipt)
        self.assertEqual(len(a.orders()), 1)

    def test_print_only_before_the_intent_is_a_rejected_order_with_no_fill(self):
        a = self.auto
        self.tape.market(self.iid, 800.0, 200.0, prints=1)  # the preview sees one print; none arrives after the order
        receipt = self.start_crypto()
        submitted = [r for r in receipt['actions'] if r['outcome'] == 'SUBMITTED']
        self.assertEqual([(r['order_state'], r['filled_quantity']) for r in submitted], [('REJECTED', 0)], receipt)
        self.assertIn('SIM_NO_POST_SIGNAL_BAR', submitted[0]['reason_codes'])
        self.assertIsNone(a.position(self.iid))
        self.assertEqual(a.store.paper_ledger.project_account()['cash_minor'], 10_000_000)

    def test_crypto_short_from_flat_is_refused_at_preview_without_mutation(self):
        a = self.auto
        self.tape.market(self.iid, 800.0, 200.0)
        before = list(a.store.paper_ledger.events)
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_POSITION'):
            paper_projections.preview_paper_order(a.store, dict(instrument_id=self.iid, side='SELL', quantity='1.125', client_order_id='short'))
        self.assertEqual(a.store.paper_ledger.events, before)

    def test_held_pair_keeps_its_stream_after_leaving_the_selection(self):
        a = self.auto
        self.tape.market(self.iid, 800.0, 200.0)
        self.start_crypto()
        self.assertIsNotNone(a.position(self.iid))
        work, summary = dict(subscriptions=[]), {}
        with patch.object(a.service, '_crypto_stream_runtime', lambda create: self.tape), \
                patch.object(a.service.reevaluation, '_loop', lambda: dict(selected=[], pending_selection=None)):
            a.service._crypto_candidate_quotes(work, summary)
        self.assertEqual(work['subscriptions'], [self.iid])
        self.assertIn(('subscribe', self.iid, (BOOK, TRADES)), self.tape.calls)


class BackgroundPrintBoundaryTests(unittest.TestCase):
    """Additional exact-boundary probes; no servers, providers, model, or wall-clock waits."""

    def setUp(self):
        self.tape = Tape(100 * S)
        self.tape.ack(IID, 101 * S)
        self.reader = PaperMarketEvidence(kraken_runtime=self.tape)

    def test_age_limit_is_inclusive_and_one_nanosecond_older_is_stale(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=105*S, event_ns=105*S)
        self.assertEqual(len(self.reader.crypto_trade_bars(IID, now_ns=120*S)), 1)
        self.assertEqual(self.reader.crypto_trade_bars(IID, now_ns=120*S+1), [])

    def test_future_receipt_by_one_nanosecond_is_rejected(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=120*S+1, event_ns=120*S)
        self.assertEqual(self.reader.crypto_trade_bars(IID, now_ns=120*S), [])

    def test_reconnect_and_subscription_cutoff_exclude_old_prints(self):
        self.tape.trade(IID, 1.0, 3000.0, received_ns=118*S, event_ns=118*S)
        self.tape.lifecycle.connected_ns = 118*S+1
        self.assertEqual(self.reader.crypto_trade_bars(IID, now_ns=120*S), [])
        self.tape.ack(IID, 119*S)
        self.tape.trade(IID, 1.0, 3000.0, received_ns=119*S-1, event_ns=119*S-1)
        self.assertEqual(self.reader.crypto_trade_bars(IID, now_ns=120*S), [])
        self.tape.trade(IID, 1.0, 3000.0, received_ns=119*S, event_ns=119*S)
        bars = self.reader.crypto_trade_bars(IID, now_ns=120*S)
        self.assertEqual([b['available_time'] for b in bars], [119*S])
        self.assertEqual(self.tape.calls, [])

    def _wait(self, *, print_at_last_read=False):
        elapsed = [0.0]
        reads = []
        self.tape.trade(IID, 1.0, 3000.0, received_ns=118*S, event_ns=118*S)
        initial = self.reader.crypto_trade_bars(IID, now_ns=120*S)
        ledger = book(); before = list(ledger.events)
        def latest(iid):
            reads.append(elapsed[0])
            if print_at_last_read and len(reads) == 3:
                self.tape.trade(IID, 1.0, 3000.0, received_ns=119*S, event_ns=119*S)
            return self.reader.crypto_trade_bars(iid, now_ns=120*S)
        def sleep(seconds): elapsed[0] += seconds
        with patch.dict(os.environ, dict(IMP_LIVE_OBSERVATIONAL='1', IMP_MOOMOO_LIVE='1', IMP_LIVE_EXECUTION_WAIT_MS='100')), \
             patch('market_platform_foundation.market_data.live_runtime.get_live_runtime', return_value=SimpleNamespace()), \
             patch.object(paper_projections, '_crypto_execution_bars', side_effect=latest), \
             patch('time.monotonic', side_effect=lambda: elapsed[0]), patch('time.sleep', side_effect=sleep):
            bars = paper_projections._wait_for_post_intent_bars(SimpleNamespace(paper_ledger=ledger),
                instrument_id=IID, created_time_ns=118*S, bars=initial, instrument=nano())
        self.assertEqual(ledger.events, before)
        self.assertLessEqual(elapsed[0], 0.100001)
        self.assertEqual(len(reads), 3)
        return bars

    def test_timeout_with_equal_intent_print_cannot_manufacture_a_new_bar(self):
        self.assertFalse(any(b['available_time'] > 118*S for b in self._wait()))

    def test_final_deadline_observation_accepts_only_a_real_fresh_print(self):
        bars = self._wait(print_at_last_read=True)
        self.assertEqual([b['available_time'] for b in bars if b['available_time'] > 118*S], [119*S])

    def test_equal_intent_print_is_not_a_fill_and_cash_is_unchanged(self):
        ledger = book()
        self.tape.trade(IID, 1.0, 3000.0, received_ns=110*S, event_ns=110*S)
        result = submit_interactive_order(ledger=ledger,
            bars=self.reader.crypto_trade_bars(IID, now_ns=115*S), symbol=IID, instrument_id=IID,
            instrument=nano(), quantity='20', side='BUY', observation_time=110*S,
            client_order_id='equal', idempotency_key='equal')
        self.assertIsNone(result['fill'])
        self.assertEqual(result['order']['reason_codes'], ['SIM_NO_POST_SIGNAL_BAR'])
        self.assertEqual(ledger.project_account()['cash_minor'], 10_000_000)
        self.assertEqual(ledger.project_positions(), [])

    def test_same_intent_and_print_cannot_duplicate_a_fill(self):
        ledger = book()
        self.tape.trade(IID, 1.0, 3000.0, received_ns=111*S, event_ns=111*S)
        kwargs=dict(ledger=ledger,bars=self.reader.crypto_trade_bars(IID,now_ns=115*S),
            symbol=IID,instrument_id=IID,instrument=nano(),quantity='20',side='BUY',observation_time=110*S,
            client_order_id='repeat',idempotency_key='repeat')
        first=submit_interactive_order(**kwargs);events=list(ledger.events)
        second=submit_interactive_order(**kwargs)
        self.assertEqual(second['order']['order_id'],first['order']['order_id'])
        self.assertEqual(ledger.events,events)
        self.assertEqual(ledger.project_positions()[0]['quantity'],'20')


if __name__ == '__main__':
    unittest.main()
