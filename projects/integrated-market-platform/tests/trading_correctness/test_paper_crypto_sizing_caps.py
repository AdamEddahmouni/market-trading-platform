"""Owner decision 5 (draft): crypto sizing caps. SOFTWARE_CONTROLLED; fixture prints and a controlled clock.

(a) A spot pair's smallest automated entry is the venue's own minimum order, not one whole unit, for both the order
    path (``execute_decision``) and the pre-model floor (``unsizeable_from_flat``).
(b) The 100/500 unit caps are frozen account terms. They stay exactly as they are on every existing account. A NEW
    account may be created with frozen crypto notional caps, which then bound CRYPTO_PAIR in dollars instead.
(0) A short-enabled account (the live one) can hold a fractional crypto long without breaking its account projection.
"""
from __future__ import annotations

import importlib.util
import os
import unittest
from decimal import Decimal

from market_platform_foundation.intelligence.inference.paper_automation import (
    entry_below_minimum, minimum_entry_quantity, size_entry, unsizeable_from_flat)
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.ui_api import paper_experiment
from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
from tests.trading_correctness import test_paper_crypto_live_execution as live
from tests.trading_correctness.test_paper_crypto_live_execution import IID, S, Tape, nano
from tests.support.paper_automation_harness import Automation, policy_body

CAPS = dict(crypto_max_order_notional_minor=500_000, crypto_max_position_notional_minor=500_000)  # $5,000 each
OWNER_RISK = dict(max_position_notional_minor=500_000, max_per_trade_risk_minor=50_000, assumed_adverse_move_bps=200,
                  max_aggregate_exposure_minor=7_500_000)


def unpatched_policy_module():
    """The worktree's own risk/policy.py, loaded beside the overlaid one, to prove existing identities are unchanged."""
    path = os.path.join(os.getcwd(), 'src', 'market_platform_foundation', 'risk', 'policy.py')
    spec = importlib.util.spec_from_file_location('market_platform_foundation.risk.unpatched_policy', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger(**terms):
    policy = build_risk_policy(initial_cash_minor=10_000_000, **terms)
    return PaperExecutionLedger.open_session(replay_session_id='s5', instrument_id='SEED', symbol='SEED', policy=policy,
                                             execution_mode='INTERNAL_SIMULATION', execution_authority='PAPER_ONLY', experiment_id='s5-test')


def pair(minimum, *, step='0.00000001', scale=1_000_000):
    return dict(instrument_kind='CRYPTO_PAIR', quantity_step=step, minimum_quantity=minimum, minimum_notional='0.5',
                contract_multiplier='1', price_scale=scale)


class FrozenTermsTests(unittest.TestCase):
    def test_existing_policies_keep_their_exact_body_and_identity(self):
        old = unpatched_policy_module()
        for terms in ({}, dict(allow_short=True), dict(allow_short=True, short_initial_margin_bps=5000)):
            with self.subTest(terms=terms):
                self.assertEqual(build_risk_policy(**terms), old.build_risk_policy(**terms))

    def test_crypto_caps_are_a_new_identity_and_both_are_required(self):
        capped = build_risk_policy(allow_short=True, **CAPS)
        self.assertEqual(capped['crypto_caps_version'], 'paper-crypto-notional-caps/1.0.0')
        self.assertEqual((capped['max_order_shares'], capped['max_position_shares']), (100, 500))  # equity terms unchanged
        self.assertNotEqual(capped['risk_policy_identity_hash'], build_risk_policy(allow_short=True)['risk_policy_identity_hash'])
        for bad in (dict(crypto_max_order_notional_minor=500_000), dict(CAPS, crypto_max_position_notional_minor=0),
                    dict(CAPS, crypto_max_order_notional_minor='500000')):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'CRYPTO_CAP_TERM_INVALID'):
                build_risk_policy(**bad)


class MinimumEntryRuleTests(unittest.TestCase):
    def test_one_rule_whole_units_for_shares_and_the_venue_minimum_for_pairs(self):
        self.assertEqual(minimum_entry_quantity(None), 1)
        self.assertEqual(minimum_entry_quantity(dict(instrument_kind='TRADABLE_SECURITY')), 1)
        self.assertEqual(minimum_entry_quantity(pair('0.00005')), Decimal('0.00005'))
        self.assertIsNone(minimum_entry_quantity(dict(instrument_kind='CRYPTO_PAIR')))
        self.assertTrue(entry_below_minimum(Decimal('0.99'), None))
        self.assertFalse(entry_below_minimum(Decimal('0.06188'), pair('0.00005')))
        self.assertTrue(entry_below_minimum(Decimal('0.00004'), pair('0.00005')))
        self.assertTrue(entry_below_minimum(0, pair('0.00005')))
        self.assertTrue(entry_below_minimum(Decimal('5'), dict(instrument_kind='CRYPTO_PAIR')))


class CryptoNotionalSizingTests(unittest.TestCase):
    LEDGER = dict(max_order_shares=100, max_position_shares=500, price_scale=100)

    def size(self, price_minor, instrument, ledger_policy):
        return size_entry(dict(risk=OWNER_RISK), price_minor=price_minor, positions=[], buying_power_minor=10_000_000,
                          ledger_policy=ledger_policy, instrument=instrument)

    def test_without_the_new_terms_sizing_is_unchanged(self):
        sizing = self.size(5960, pair('600', step='0.00001'), self.LEDGER)  # BANANAS31/USD, 2026-10-27
        self.assertEqual((sizing['quantity'], sizing['binding']), ('0', 'PAPER_ACCOUNT_MAX_ORDER_SHARES'))

    def test_with_crypto_caps_a_sub_cent_pair_sizes_to_the_owner_notional(self):
        terms = dict(self.LEDGER, crypto_caps_version='paper-crypto-notional-caps/1.0.0', **CAPS)
        sizing = self.size(5960, pair('600', step='0.00001'), terms)
        self.assertEqual((sizing['quantity'], sizing['binding']), ('838926.17449', 'MAX_POSITION_NOTIONAL'))
        self.assertNotIn('PAPER_ACCOUNT_MAX_ORDER_SHARES', sizing['bounds'])
        self.assertEqual(sizing['bounds']['PAPER_ACCOUNT_MAX_ORDER_NOTIONAL'], '838926.17449')
        # The owner's $5,000 and per-trade risk stay binding: never more than $5,000 of anything.
        self.assertLessEqual(Decimal(sizing['quantity']) * Decimal('0.005960'), Decimal(5000))
        bounds = dict(risk=OWNER_RISK, paper_account=terms)
        self.assertIsNone(unsizeable_from_flat(bounds, price_minor=5960, instrument=pair('600', step='0.00001')))
        self.assertEqual(unsizeable_from_flat(dict(risk=OWNER_RISK, paper_account=self.LEDGER), price_minor=5960,
                                              instrument=pair('600', step='0.00001')), 'PAPER_ACCOUNT_MAX_ORDER_SHARES')

    def test_a_tighter_account_cap_binds_below_the_owner_notional(self):
        terms = dict(self.LEDGER, crypto_caps_version='v', crypto_max_order_notional_minor=100_000, crypto_max_position_notional_minor=500_000)
        sizing = self.size(1_000_000, pair('15'), terms)  # $1.00 a unit, $1,000 order cap
        self.assertEqual((sizing['quantity'], sizing['binding']), ('1000', 'PAPER_ACCOUNT_MAX_ORDER_NOTIONAL'))

    def test_equities_keep_their_share_caps_on_a_capped_account(self):
        terms = dict(self.LEDGER, crypto_caps_version='v', **CAPS)
        sizing = size_entry(dict(risk=OWNER_RISK), price_minor=1_000, positions=[], buying_power_minor=10_000_000, ledger_policy=terms)
        self.assertEqual((sizing['quantity'], sizing['binding']), (100, 'PAPER_ACCOUNT_MAX_ORDER_SHARES'))


class LedgerCryptoCapTests(unittest.TestCase):
    """The ledger's own risk check, at the print the simulator fills against."""

    def setUp(self):
        self.tape = Tape(connected_ns=100 * S)
        self.tape.ack(IID, 101 * S)
        self.n = 0

    def submit(self, book, quantity, side='BUY', intent_s=110, now_s=115):
        self.n += 1
        bars = PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID, now_ns=now_s * S)
        return submit_interactive_order(ledger=book, bars=bars, symbol=IID, instrument_id=IID, instrument=nano(), quantity=quantity,
                                        side=side, observation_time=int(intent_s * S), client_order_id=f'c{self.n}', idempotency_key=f'c{self.n}')

    def test_unit_caps_still_bind_an_account_without_crypto_terms(self):
        self.tape.trade(IID, 1.0, 1_000_000.0, received_ns=111 * S)
        result = self.submit(ledger(), '150')
        self.assertEqual((result['decision'], result['fill']), ('REJECT', None))

    def test_crypto_terms_replace_unit_caps_with_dollar_caps(self):
        book = ledger(**CAPS)
        self.tape.trade(IID, 1.0, 1_000_000.0, received_ns=111 * S)
        result = self.submit(book, '150')  # 150 units = $150: above the 100-unit cap, far below $5,000
        self.assertEqual((result['order']['state'], result['fill']['fill_quantity']), ('FILLED', '150'))
        refused = self.submit(book, '5001', intent_s=110.5)  # $5,001 at the $1.00 print
        self.assertEqual(refused['decision'], 'REJECT')
        self.assertIn('RISK_MAX_ORDER_NOTIONAL_EXCEEDED', str(book.events))

    def test_position_cap_refuses_an_add_but_never_a_reduction(self):
        book = ledger(**CAPS)
        self.tape.trade(IID, 1.0, 1_000_000.0, received_ns=111 * S)
        self.assertEqual(self.submit(book, '4000')['order']['state'], 'FILLED')
        add = self.submit(book, '1500', intent_s=110.5)  # $5,500 held after: over the position cap
        self.assertEqual(add['decision'], 'REJECT')
        self.assertIn('RISK_MAX_POSITION_NOTIONAL_EXCEEDED', str(book.events))
        self.tape.trade(IID, 2.0, 1_000_000.0, received_ns=121 * S)  # the 4,000 held are now worth $8,000
        reduce = self.submit(book, '1000', side='SELL', intent_s=120, now_s=125)
        self.assertEqual((reduce['order']['state'], reduce['fill']['fill_quantity']), ('FILLED', '1000'))


class ShortEnabledFractionalLongTests(unittest.TestCase):
    """A0: on a short-enabled account a fractional crypto long made project_account() raise int('20.5')."""

    def test_a_fractional_crypto_long_on_a_short_enabled_account_projects(self):
        book = ledger(allow_short=True)
        tape = Tape(connected_ns=100 * S)
        tape.ack(IID, 101 * S)
        tape.trade(IID, 1.0, 3000.0, received_ns=111 * S)
        bars = PaperMarketEvidence(kraken_runtime=tape).crypto_trade_bars(IID, now_ns=115 * S)
        result = submit_interactive_order(ledger=book, bars=bars, symbol=IID, instrument_id=IID, instrument=nano(), quantity='20.5',
                                          side='BUY', observation_time=110 * S, client_order_id='f', idempotency_key='f')
        self.assertEqual(result['fill']['fill_quantity'], '20.5')
        account = book.project_account()
        self.assertEqual(account['short_market_value_minor'], 0)
        self.assertEqual(account['buying_power_minor'], 10_000_000 - 2050)
        status = book.short_margin_status()
        self.assertEqual((status['short_positions'], status['maintenance_breached']), ([], False))
        self.assertIsNotNone(book.project_valuation())


class _NoInherited(live.CryptoAutonomousExecutionTests):
    pass


for _name in [n for n in dir(live.CryptoAutonomousExecutionTests) if n.startswith('test_')]:
    setattr(_NoInherited, _name, None)  # reuse the crypto controller fixture only, not its tests


class AutomatedFractionalEntryTests(_NoInherited):
    """execute_decision on the live account's shape: short-enabled, BTC above the owner's notional per unit."""

    def setUp(self):
        super().setUp()
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = paper_experiment.create_experiment(self.store, {'allow_short': True})['experiment']
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, ai=self.auto.ai, provider=self.auto.provider)

    def start(self, price):
        a = self.auto
        a.quote(self.iid, price, 2)
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

    def test_a_pair_priced_above_the_notional_cap_enters_a_fraction(self):
        a = self.auto
        self.tape.market(self.iid, 8000.0, 50.0)  # $900 owner cap / $8,000 = 0.1125 -> 0.112 on the 0.001 lot
        receipt = self.start(8000)
        entered = [r for r in receipt['actions'] if r['outcome'] == 'SUBMITTED']
        self.assertEqual([(r['quantity'], r['filled_quantity']) for r in entered], [('0.112', '0.112')], receipt)
        self.assertNotIn('SIZING_BELOW_MINIMUM', [c for r in receipt['actions'] for c in r['reason_codes']])
        self.assertEqual(a.position(self.iid)['quantity'], '0.112')
        account = a.store.paper_ledger.project_account()  # A0: the short-enabled account still projects
        self.assertEqual(account['short_market_value_minor'], 0)
        self.assertEqual(account['cash_minor'], 10_000_000 - 89_600)

    def test_below_the_venue_minimum_is_still_refused(self):
        self.tape.market(self.iid, 1_000_000.0, 50.0)  # $900 buys 0.0009 < ordermin 0.001
        receipt = self.start(1_000_000)
        self.assertIn('SIZING_BELOW_MINIMUM', [c for r in receipt['actions'] for c in r['reason_codes']], receipt)
        self.assertIsNone(self.auto.position(self.iid))


if __name__ == '__main__':
    unittest.main()
