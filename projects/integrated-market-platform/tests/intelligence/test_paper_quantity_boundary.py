"""Unsupported fractional Workspace input must never be silently rounded."""
import unittest
from market_platform_foundation.ui_api.paper_projections import _parse_order_body

class WorkspaceQuantityBoundaryTests(unittest.TestCase):
    def parse(self, quantity):
        return _parse_order_body(dict(side='BUY',quantity=quantity,client_order_id='fixture-only',
                                     idempotency_key='fixture-only'),None)

    def test_unsupported_fractional_and_boolean_requests_fail_closed(self):
        for value in (1.5,True,False,float('inf'),float('-inf'),float('nan'),'0.125','1.5'):
            with self.subTest(quantity=value), self.assertRaisesRegex(ValueError,'ORDER_QUANTITY_INVALID'):
                self.parse(value)

    def test_existing_whole_equity_quantities_remain_exact(self):
        for value in (1,5,'5',5.0):
            self.assertEqual(self.parse(value)['quantity'],int(value))
