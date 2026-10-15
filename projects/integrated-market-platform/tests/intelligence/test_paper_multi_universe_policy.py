"""Shared-account policy regressions; controlled values are not market evidence."""
import unittest
from decimal import Decimal

from market_platform_foundation.intelligence.inference.paper_automation import (
    build_policy, entry_risk_blockers, exposure_minor, size_entry, universe_scopes,
)
from tests.intelligence.test_paper_automation_policy import body, LEDGER_POLICY


class MultiUniversePolicyTests(unittest.TestCase):
    def build(self, value):
        return build_policy(value, account_id='acct', experiment_id='PPE-1',
                            initial_capital_minor=10_000_000, ledger_policy=LEDGER_POLICY)

    def multi(self):
        value = body(risk=dict(allowed_universes=['US_EQUITIES', 'CRYPTO']))
        value['scopes'] = [dict(scope=value['scope'], sessions=['REGULAR']),
                           dict(scope=dict(universe='CRYPTO', filters=[]), sessions=['CONTINUOUS'])]
        return value

    def test_explicit_scopes_keep_one_shared_risk_and_legacy_identity(self):
        legacy = self.build(body())
        self.assertNotIn('scopes', legacy)
        self.assertEqual(universe_scopes(legacy), [dict(scope=legacy['scope'], sessions=['REGULAR'])])
        value = self.build(self.multi())
        self.assertEqual(len(universe_scopes(value)), 2)
        self.assertEqual(value['risk']['max_aggregate_exposure_minor'], legacy['risk']['max_aggregate_exposure_minor'])
        self.assertNotEqual(value['policy_id'], legacy['policy_id'])

    def test_sessions_cannot_be_transplanted_between_asset_classes(self):
        for universe, sessions in [('CRYPTO', ['REGULAR']), ('US_ETFS', ['CONTINUOUS']),
                                   ('FUTURES', ['CONTINUOUS'])]:
            value = self.multi()
            value['risk']['allowed_universes'].append('FUTURES')
            value['risk']['allowed_universes'].append('US_ETFS')
            value['scopes'][1] = dict(scope=dict(universe=universe), sessions=sessions)
            with self.subTest(universe=universe), self.assertRaisesRegex(ValueError, 'AUTOMATION_SCOPE_SESSION_UNSUPPORTED'):
                self.build(value)

    def test_duplicate_or_unbound_scope_is_refused(self):
        for duplicate in [True, False]:
            value = self.multi()
            value['scopes'][1]['scope']['universe'] = 'US_EQUITIES' if duplicate else 'BONDS'
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                self.build(value)

    def test_continuous_entry_does_not_inherit_equity_close(self):
        p = self.build(self.multi())
        facts = dict(positions=[], valuation=dict(quality='CURRENT', equity_minor=10_000_000),
                     day_start_equity_minor=10_000_000, pending_orders=[], minutes_to_close=None)
        self.assertNotIn('ENTRY_WINDOW_CLOSED', entry_risk_blockers(p, **facts, session_label='CONTINUOUS'))
        self.assertIn('ENTRY_WINDOW_CLOSED', entry_risk_blockers(p, **facts, session_label='REGULAR'))

    def test_fractional_exposure_retains_price_scale_and_multiplier(self):
        positions = [dict(quantity='0.015', mark_minor=100_000_000, price_scale=10000, contract_multiplier='1'),
                     dict(quantity=2, mark_minor=550000, price_scale=100, contract_multiplier='50')]
        self.assertEqual(exposure_minor(positions), 55_015_000)
        self.assertIsNone(exposure_minor([dict(quantity='NaN', mark_minor=100)]))

    def test_crypto_size_rounds_down_to_authoritative_step_inside_shared_notional(self):
        p = self.build(self.multi())
        result = size_entry(p, price_minor=6_000_000, positions=[], buying_power_minor=10_000_000,
                            ledger_policy=LEDGER_POLICY, instrument=dict(instrument_kind='CRYPTO_PAIR',
                            price_scale=100, quantity_step='0.0001', minimum_quantity='0.0002', contract_multiplier='1'))
        self.assertEqual(Decimal(str(result['quantity'])), Decimal('0.0833'))
        self.assertLessEqual(Decimal(str(result['quantity'])) * 6_000_000, p['risk']['max_position_notional_minor'])

    def test_missing_crypto_increment_is_blocked(self):
        result = size_entry(self.build(self.multi()), price_minor=6_000_000, positions=[],
                            buying_power_minor=10_000_000, ledger_policy=LEDGER_POLICY,
                            instrument=dict(instrument_kind='CRYPTO_PAIR', price_scale=100))
        self.assertEqual(result['quantity'], 0)
        self.assertEqual(result['binding'], 'INSTRUMENT_QUANTITY_RULES_UNAVAILABLE')
