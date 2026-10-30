"""An operator can close a carried US equity after a restart; nothing else becomes admissible (2026-10-30).

After the 2026-10-29 restarts the API process held five carried equities that were no longer registered in XA-01
memory, so an operator close of any of them was refused UNKNOWN_INSTRUMENT. Only an order that strictly reduces the
position already held re-registers it from its US_EQUITIES catalog row; entries, increases and reversals do not.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.paper.eligibility import InstrumentAdmissionError, admit_order_instrument
from market_platform_foundation.ui_api import paper_automation
from market_platform_foundation.ui_api.paper_projections import _reregister_held_equity_for_reduction
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def catalog_row(symbol):
    return dict(instrument=dict(instrument_id=symbol, venue_id='US_EQUITY', asset_class='EQUITY',
                                instrument_kind='TRADABLE_SECURITY'),
                symbol=symbol, company=symbol,
                classification=dict(universe='US_EQUITIES', category='UNCLASSIFIED', status='ADMITTED'))


class Ledger:
    def __init__(self, positions):
        self.positions = positions

    def project_positions(self):
        return self.positions


class OperatorCloseReregistrationTests(unittest.TestCase):
    def setUp(self):
        reset_registry_for_tests()
        self.addCleanup(reset_registry_for_tests)
        self.lookups = []

        def row_for(iid, universe):
            self.lookups.append((iid, universe))
            return self.catalog.get(iid), None

        self.catalog = {s: catalog_row(s) for s in ('BTGO', 'HBAN', 'NEWCO')}
        # register_catalog_equity binds its catalog reader as a default argument, so the screener service it reads is
        # replaced instead.
        patcher = patch('market_platform_foundation.ui_api.screener_multi.multi_screener_service',
                        return_value=SimpleNamespace(row_for=row_for))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_case(self, positions, symbol, side, quantity):
        store = SimpleNamespace(paper_ledger=Ledger(positions))
        _reregister_held_equity_for_reduction(store, symbol, dict(side=side, quantity=quantity))

    def assert_admitted(self, symbol):
        self.assertEqual(admit_order_instrument(symbol)['instrument_kind'], 'TRADABLE_SECURITY')

    def assert_refused(self, symbol):
        with self.assertRaises(InstrumentAdmissionError) as caught:
            admit_order_instrument(symbol)
        self.assertEqual(caught.exception.code, 'UNKNOWN_INSTRUMENT')

    def test_buy_to_cover_a_held_short_is_reregistered_and_admitted(self):
        self.assert_refused('BTGO')
        self.run_case([dict(instrument_id='BTGO', quantity='-1', side='SHORT')], 'BTGO', 'BUY', 1)
        self.assertEqual(self.lookups, [('BTGO', 'US_EQUITIES')])
        self.assert_admitted('BTGO')

    def test_sell_of_a_held_long_is_reregistered_and_admitted(self):
        self.run_case([dict(instrument_id='HBAN', quantity='1', side='LONG')], 'HBAN', 'SELL', '1')
        self.assert_admitted('HBAN')

    def test_partial_reduction_is_reregistered(self):
        self.run_case([dict(instrument_id='HBAN', quantity='3', side='LONG')], 'HBAN', 'SELL', 2)
        self.assert_admitted('HBAN')

    def test_an_entry_without_a_position_registers_nothing(self):
        self.run_case([], 'NEWCO', 'BUY', 1)
        self.assertEqual(self.lookups, [])
        self.assert_refused('NEWCO')

    def test_increasing_a_long_registers_nothing(self):
        self.run_case([dict(instrument_id='HBAN', quantity='1', side='LONG')], 'HBAN', 'BUY', 1)
        self.assert_refused('HBAN')

    def test_increasing_a_short_registers_nothing(self):
        self.run_case([dict(instrument_id='BTGO', quantity='-1', side='SHORT')], 'BTGO', 'SELL', 1)
        self.assert_refused('BTGO')

    def test_a_reversal_through_zero_registers_nothing(self):
        self.run_case([dict(instrument_id='BTGO', quantity='-1', side='SHORT')], 'BTGO', 'BUY', 2)
        self.run_case([dict(instrument_id='HBAN', quantity='1', side='LONG')], 'HBAN', 'SELL', 2)
        self.assertEqual(self.lookups, [])
        self.assert_refused('BTGO')
        self.assert_refused('HBAN')

    def test_a_held_equity_the_catalog_does_not_admit_stays_refused(self):
        self.run_case([dict(instrument_id='GONE', quantity='-1', side='SHORT')], 'GONE', 'BUY', 1)
        self.assertEqual(self.lookups, [('GONE', 'US_EQUITIES')])
        self.assert_refused('GONE')

    def test_an_already_registered_instrument_does_not_consult_the_catalog(self):
        paper_automation.register_catalog_equity('HBAN', 'US_EQUITIES', catalog_row=lambda *_: catalog_row('HBAN'))
        self.run_case([dict(instrument_id='HBAN', quantity='1', side='LONG')], 'HBAN', 'SELL', 1)
        self.assertEqual(self.lookups, [])


if __name__ == '__main__':
    unittest.main()
