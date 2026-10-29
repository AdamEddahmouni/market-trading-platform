"""A held US equity stays closable after a process restart (2026-10-29).

US_EQUITIES identities reach the XA-01 registry only in memory, when an entry is admitted from the catalog row. After
the 2026-10-29 restarts RCL (-1, an unplanned carry) was no longer registered, so every open close was refused
UNKNOWN_INSTRUMENT and the carry blocked all equity entries. A held equity that fails admission is re-registered from
its US_EQUITIES catalog row (the same rule as entries) and admitted again; anything the catalog does not admit stays
blocked carry, never guessed.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.ui_api import paper_automation as controller

EQUITY = dict(instrument_kind='TRADABLE_SECURITY', asset_class='EQUITY')


class Ledger:
    def project_positions(self):
        return [dict(instrument_id='RCL', quantity='1', side='SHORT')]


def owned(registers):
    registry, calls = set(), []

    def register(iid, universe, **kwargs):
        calls.append((iid, universe))
        if registers:
            registry.add(iid)

    def admit(store, iid):
        if iid not in registry:
            raise ValueError('UNKNOWN_INSTRUMENT: unresolved canonical instrument')
        return EQUITY

    service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
    service.store = SimpleNamespace(paper_ledger=Ledger())
    with patch.object(controller, '_automation_quantities', return_value={'RCL': -1}), \
            patch.object(controller, 'register_catalog_equity', side_effect=register), \
            patch('market_platform_foundation.ui_api.paper_projections._admit_focus_instrument', side_effect=admit):
        return service._owned_positions(), calls


class HeldEquityReregistrationTests(unittest.TestCase):
    def test_unregistered_held_equity_is_reregistered_and_closable(self):
        rows, calls = owned(registers=True)
        self.assertEqual(calls, [('RCL', 'US_EQUITIES')])
        self.assertEqual(len(rows), 1)
        self.assertNotIn('instrument_admission_unavailable', rows[0])
        self.assertEqual(str(rows[0]['quantity']), '-1')

    def test_catalog_refusal_keeps_the_position_as_blocked_carry(self):
        rows, calls = owned(registers=False)
        self.assertEqual(calls, [('RCL', 'US_EQUITIES')])
        self.assertTrue(rows[0]['instrument_admission_unavailable'])


if __name__ == '__main__':
    unittest.main()
