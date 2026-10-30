"""The saved carry snapshot stays historical evidence; the ledger names current holdings."""

from __future__ import annotations

import unittest

from market_platform_foundation.ui_api.paper_automation import carry_ledger_projection


class CarryLedgerProjectionTests(unittest.TestCase):
    def test_stale_names_stay_in_the_snapshot_and_are_absent_from_the_ledger(self):
        carry = {'pending': {'BTGO': {'quantity': -1}, 'HBAN': {'quantity': 1}}, 'approved': {}, 'blocked': ['RCL']}
        positions = [{'instrument_id': 'HBAN', 'quantity': 1}]

        view = carry_ledger_projection(carry, positions)

        self.assertEqual(view['semantics'], 'LAST_CYCLE_CARRY_SNAPSHOT')
        self.assertEqual(view['current_holdings'], 'LEDGER_POSITIONS')
        self.assertEqual(view['pending_still_open'], ['HBAN'])
        self.assertEqual(view['pending_absent_from_ledger'], ['BTGO'])
        self.assertEqual(carry['pending']['BTGO']['quantity'], -1)
        self.assertEqual(carry['blocked'], ['RCL'])

    def test_a_flat_ledger_does_not_turn_the_old_snapshot_into_open_holdings(self):
        carry = {'pending': {'BTGO': {}, 'CRGY': {}, 'HBAN': {}, 'SSRM': {}, 'WGS': {}}}

        view = carry_ledger_projection(carry, [])

        self.assertEqual(view['pending_still_open'], [])
        self.assertEqual(view['pending_absent_from_ledger'], ['BTGO', 'CRGY', 'HBAN', 'SSRM', 'WGS'])

    def test_a_symbol_field_matches_a_pending_key(self):
        view = carry_ledger_projection({'pending': {'WGS': {'quantity': 1}}}, [{'symbol': 'WGS', 'quantity': 1}])

        self.assertEqual(view['pending_still_open'], ['WGS'])
        self.assertEqual(view['pending_absent_from_ledger'], [])


if __name__ == '__main__':
    unittest.main()
