"""Lane 01 — the autonomous controller's order boundary for Screener-admitted US equities and spot crypto.

SOFTWARE_CONTROLLED, through the production controller, Action Decision gate, XA-01 admission, Paper
preview/risk/submit route, simulator and ledger (``tests.support.paper_automation_harness``). The US_EQUITIES
catalog row, the model, the clock and the Kraken prints are fixtures. Live findings these pin (2026-10-27):

* every US_EQUITIES target the AI selected (ALL, XXII, SKYD, WYNN, ...) failed admission ``UNKNOWN_INSTRUMENT``,
  because Finviz catalog rows are keyed by ticker and never registered in XA-01;
* that refusal was raised outside the adapter's refusal handling, so it aborted the scope's whole cycle and left
  no intent;
* ``/paper/automation/status`` was refused by the response leak audit because the epoch index is keyed by ticker
  and ``KEYS`` (Keysight) is a secret-shaped key name;
* a spot crypto SELL from flat was deferred on price before being refused for the position it lacks.

These prove software behaviour only; they are not live-session acceptance.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.crypto_market import kraken_stream
from market_platform_foundation.intelligence.contracts.common import OpportunitySide
from market_platform_foundation.paper.eligibility import admit_order_instrument
from market_platform_foundation.platform.security.leak_audit import SecretLeakError, assert_no_secrets_in_payload
from market_platform_foundation.ui_api import paper_experiment, paper_projections, screener_crypto
from market_platform_foundation.ui_api.paper_automation import register_catalog_equity, status_universe
from tests.support.paper_automation_harness import Automation, policy_body
from tests.trading_correctness.test_paper_automation import AutoBase
from tests.trading_correctness.test_paper_automation_shorts import SHORTS, ShortProvider
from tests.trading_correctness.test_paper_crypto_live_execution import S, Tape
from tests.trading_correctness.test_paper_exact_boundaries import CryptoAi


def equity_row(symbol, *, status='ADMITTED', kind='TRADABLE_SECURITY', asset_class='EQUITY', universe='US_EQUITIES'):
    """The shape ``screener_projections._snapshot_row`` gives a Finviz ``geo_usa`` listing."""
    return dict(instrument=dict(instrument_id=symbol, venue_id='US_EQUITY', asset_class=asset_class, instrument_kind=kind),
                symbol=symbol, company=symbol, classification=dict(universe=universe, category='UNCLASSIFIED', status=status))


class CatalogEquityRegistrationTests(AutoBase):
    """Only a row the scope's own catalog admitted becomes an executable identity."""

    def test_only_an_admitted_equity_row_of_this_scope_is_registered(self):
        refused = {
            'REJECTED': equity_row('LANEA', status='REJECTED'),
            'FUTURE': equity_row('LANEB', kind='FUTURE_CONTRACT'),
            'ETF_CLASS': equity_row('LANEC', asset_class='ETF_FUND'),
            'OTHER_UNIVERSE': equity_row('LANED', universe='US_ETFS'),
            'SYMBOL_MISMATCH': dict(equity_row('LANEE'), symbol='OTHER'),
        }
        for label, row in refused.items():
            with self.subTest(label):
                iid = row['instrument']['instrument_id']
                self.assertIsNone(register_catalog_equity(iid, 'US_EQUITIES', catalog_row=lambda *_: row))
                with self.assertRaisesRegex(ValueError, 'UNKNOWN_INSTRUMENT'):
                    admit_order_instrument(iid)
        self.assertIsNone(register_catalog_equity('LANEF', 'US_EQUITIES', catalog_row=lambda *_: None))
        self.assertIsNone(register_catalog_equity('LANEG', 'CRYPTO', catalog_row=lambda *_: equity_row('LANEG')))
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_INSTRUMENT'):
            admit_order_instrument('LANEG')

        def broken(*_):
            raise OSError('catalog down')
        with self.assertRaisesRegex(ValueError, 'UNIVERSE_CATALOG_UNAVAILABLE'):
            register_catalog_equity('LANEH', 'US_EQUITIES', catalog_row=broken)

        canonical = register_catalog_equity('LANEI', 'US_EQUITIES', catalog_row=lambda *_: equity_row('LANEI'))
        admitted = admit_order_instrument('LANEI')
        self.assertTrue(canonical.startswith('XA01:'))
        self.assertEqual((admitted['instrument_kind'], admitted['tradability'], admitted['venue'], admitted['currency'],
                          admitted['contract_multiplier']), ('TRADABLE_SECURITY', 'TRADABLE', 'US_EQUITY', 'USD', '1'))
        # Registration is idempotent: the next decision on the same ticker resolves to the same identity.
        self.assertEqual(register_catalog_equity('LANEI', 'US_EQUITIES', catalog_row=lambda *_: equity_row('LANEI')), canonical)


class CatalogEquityExecutionTests(AutoBase):
    def setUp(self):
        super().setUp()
        self.catalog = {}
        self.auto.service.catalog_row = lambda iid, universe: self.catalog.get((iid, universe))

    def admit(self, *symbols):
        for symbol in symbols:
            self.catalog[(symbol, 'US_EQUITIES')] = equity_row(symbol)

    def test_a_catalog_admitted_equity_enters_through_the_unchanged_paper_route(self):
        self.admit('WYNN')
        position = self.enter('WYNN', price=90)
        self.assertEqual(position['side'], 'LONG')
        order = self.automation_orders()[0]
        self.assertEqual(order['instrument_id'], 'WYNN')
        self.assertEqual(self.auto.store.paper_ledger.execution_provider, 'INTERNAL')
        self.assertEqual(self.auto.service.status()['boundary']['execution'], 'INTERNAL_PAPER_SIMULATION_ONLY')
        self.assertFalse(self.auto.service._controller().get('consecutive_failures'))

    def test_a_target_the_catalog_did_not_admit_is_its_own_refusal_and_the_queue_goes_on(self):
        a = self.auto
        for symbol, price in (('SKYD', 40), ('AAPL', 150)):
            a.quote(symbol, price, 2)
            a.opportunity(symbol)
        a.go()
        a.cycle()
        a.select('SKYD', 'AAPL')  # SKYD is queued first and is not in the catalog
        receipts = [a.cycle() for _ in range(3)]
        refused = [r for receipt in receipts for r in receipt['actions'] if r['instrument_id'] == 'SKYD']
        # Its first attempt is refused at admission. Later cycles may refuse it earlier for other reasons (the
        # account's valuation after the AAPL fill), and every attempt stays a recorded refusal.
        self.assertEqual((refused[0]['outcome'], refused[0]['reason_codes']), ('BLOCKED', ['UNKNOWN_INSTRUMENT']))
        self.assertEqual({r['outcome'] for r in refused}, {'BLOCKED'})
        intent = a.service.repository.get_intent(refused[0]['intent_id'])
        self.assertEqual(intent['state'], 'BLOCKED')
        self.assertTrue(all(receipt.get('error') is None for receipt in receipts), receipts)
        self.assertFalse(a.service._controller().get('consecutive_failures'))
        self.assertIsNotNone(a.position('AAPL'))  # the decision behind the refusal still reached the Paper route
        self.assertEqual([o['instrument_id'] for o in self.automation_orders()], ['AAPL'])


class CatalogEquityShortTests(AutoBase):
    """The approved equity short policy applies to a Screener-admitted ticker exactly as to a fixture."""

    def setUp(self):
        super().setUp()
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = paper_experiment.create_experiment(self.store, {'allow_short': True})['experiment']
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, provider=ShortProvider())
        self.auto.service.catalog_row = lambda iid, universe: equity_row(iid) if (iid, universe) == ('KEYS', 'US_EQUITIES') else None

    def test_sell_to_open_then_buy_to_cover_on_an_admitted_equity(self):
        a = self.auto
        a.quote('KEYS', 150, -2)
        a.opportunity('KEYS', side=OpportunitySide.SHORT)
        a.go(**SHORTS)
        a.cycle()
        a.select('KEYS')
        opened = [o for _ in range(3) for o in a.cycle()['actions'] if o['outcome'] == 'SUBMITTED']
        self.assertEqual([(o['action'], o['side']) for o in opened], [('ENTER', 'SELL')])
        position = a.position('KEYS')
        self.assertEqual(position['side'], 'SHORT')
        held = -position['quantity']
        account = a.store.paper_ledger.project_account()
        self.assertGreater(account['short_margin_reserved_minor'], 0)
        # The status read stays readable with KEYS in every per-instrument structure it reports.
        assert_no_secrets_in_payload(a.service.status())
        a.quote('KEYS', 148, 2)
        covered = [o for o in a.cycle(400)['actions'] if o['outcome'] == 'SUBMITTED']
        self.assertEqual([(o['action'], o['side'], o['quantity']) for o in covered], [('EXIT', 'BUY', held)])
        self.assertIsNone(a.position('KEYS'))
        valuation = a.store.paper_ledger.project_valuation()
        self.assertGreater(valuation['realized_pnl_minor'], 0)
        self.assertEqual(a.store.paper_ledger.project_account()['short_margin_reserved_minor'], 0)


class StatusEpochIndexTests(AutoBase):
    def test_a_secret_shaped_ticker_in_the_epoch_index_does_not_block_the_status_read(self):
        a = self.auto
        a.go()
        a.cycle()
        index = {'KEYS': 1793122752.1, 'AAPL': 1793122752.1}
        stored = a.service.repository.get_controller

        def controller(account_id):
            row = stored(account_id)
            row['universe'] = dict(row.get('universe') or {}, epoch=dict(number=6, started_epoch=1.0, prior_turns=dict(index),
                                                                          prior_evaluated=dict(index), runs=[]))
            return row

        with self.assertRaises(SecretLeakError):  # the unchanged audit refuses the raw index
            assert_no_secrets_in_payload(dict(universe=controller(a.service._account())['universe']))
        with patch.object(a.service.repository, 'get_controller', controller):
            status = a.service.status()
        assert_no_secrets_in_payload(status)
        epoch = status['universe']['epoch']
        self.assertEqual((epoch['number'], epoch['prior_turns_count'], epoch['prior_evaluated_count']), (6, 2, 2))
        self.assertNotIn('prior_turns', epoch)
        self.assertIsNone(status_universe(None))
        self.assertEqual(status_universe(dict(active_run_id='r')), dict(active_run_id='r'))


class CryptoSpotShortTests(AutoBase):
    """A spot pair has no approved short product: SELL-to-open is refused for that, before any price is needed."""

    def setUp(self):
        super().setUp()
        payload = {'error': [], 'result': {'BTC/USD': dict(base='BTC', quote='USD', aclass_base='currency', aclass_quote='currency',
            status='online', ordermin='0.001', costmin='1', tick_size='0.0001', lot_decimals=3, pair_decimals=4, cost_decimals=2)}}
        source = screener_crypto.CryptoScreener(client=SimpleNamespace(asset_pairs=lambda: payload), env={'IMP_CRYPTO_LIVE': '1'})
        rows, _, error = source._catalog()
        self.assertIsNone(error)
        self.iid = rows[0]['instrument']['instrument_id']
        self.tape = Tape(connected_ns=int(self.clock() * S) - S)
        self.tape.ack(self.iid, int(self.clock() * S) - S)
        fixture_bars = paper_projections._bars_for_paper_execution

        def bars(store, *, instrument_id=None, instrument=None):
            if (instrument or {}).get('instrument_kind') != 'CRYPTO_PAIR':
                return fixture_bars(store, instrument_id=instrument_id, instrument=instrument)
            self.tape.tick(instrument_id, self.feed.now_ns())
            with patch('market_platform_foundation.clock.monotonic_wall_ns', self.feed.now_ns):
                return paper_projections._crypto_execution_bars(instrument_id)

        for patcher in (patch.object(screener_crypto, '_SERVICE', source), patch.object(kraken_stream, '_RUNTIME', self.tape),
                        patch.object(paper_projections, '_bars_for_paper_execution', bars)):
            patcher.start()
            self.addCleanup(patcher.stop)
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = paper_experiment.create_experiment(self.store, {'allow_short': True})['experiment']
        provider = ShortProvider()
        ai = CryptoAi(self.clock, provider)
        ai.rows, ai.selected = {}, []
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, ai=ai, provider=provider)

    def short_cycles(self, *, prints):
        a = self.auto
        if prints:
            self.tape.market(self.iid, 800.0, 200.0)
        a.quote(self.iid, 800, -2)
        a.opportunity(self.iid, side=OpportunitySide.SHORT)
        body = policy_body(risk=dict(allowed_universes=['US_EQUITIES', 'CRYPTO'], allow_short=True, max_position_notional_minor=90000))
        body['scopes'] = [dict(scope=dict(body['scope']), sessions=['REGULAR']), dict(scope=dict(universe='CRYPTO'), sessions=['CONTINUOUS'])]
        a.session_label = 'CLOSED'
        a.service.configure(body)
        a.arm()
        a.service.start(threaded=False)
        a.cycle()
        a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'], [self.iid])
        return [r for _ in range(3) for r in a.cycle()['actions'] if r['instrument_id'] == self.iid]

    def assert_refused_without_mutation(self, outcomes):
        self.assertEqual([(r['outcome'], r['side'], r['reason_codes']) for r in outcomes],
                         [('BLOCKED', 'SELL', ['SHORT_INSTRUMENT_UNSUPPORTED', 'CRYPTO_PAIR'])])
        self.assertEqual(self.auto.orders(), [])
        account = self.auto.store.paper_ledger.project_account()
        self.assertEqual((account['cash_minor'], account['short_margin_reserved_minor']), (10_000_000, 0))

    def test_spot_sell_to_open_without_a_fresh_print_is_refused_not_deferred_on_price(self):
        self.assert_refused_without_mutation(self.short_cycles(prints=False))

    def test_spot_sell_to_open_with_fresh_prints_is_refused_before_the_preview(self):
        self.assert_refused_without_mutation(self.short_cycles(prints=True))
