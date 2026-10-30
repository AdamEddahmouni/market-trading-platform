"""AUD-015: an intent's recorded order state is history; the status also shows the order's state now."""
from __future__ import annotations

import unittest

from market_platform_foundation.ui_api.paper_automation import _with_latest_order_state


class Ledger:
    def __init__(self, orders):
        self.orders, self.projections = orders, 0

    def project_orders(self):
        self.projections += 1
        return list(self.orders)


class LatestOrderStateTests(unittest.TestCase):
    def test_a_partially_filled_intent_shows_its_cancelled_order_without_rewriting_history(self):
        intents = [dict(intent_id='PAI-1', order_id='O-1', state='SUBMITTED', order_state='PARTIALLY_FILLED'),
                   dict(intent_id='PAI-2', order_id=None, state='REFUSED', order_state=None)]
        ledger = Ledger([dict(order_id='O-1', state='CANCELLED')])
        shown = _with_latest_order_state(intents, ledger)
        self.assertEqual([(i['order_state'], i['latest_order_state']) for i in shown],
                         [('PARTIALLY_FILLED', 'CANCELLED'), (None, None)])
        self.assertNotIn('latest_order_state', intents[0])  # the stored intent is not modified
        self.assertEqual(ledger.projections, 1)  # one projection for the whole list

    def test_no_order_means_no_projection(self):
        ledger = Ledger([])
        self.assertEqual(_with_latest_order_state([dict(intent_id='PAI-3')], ledger)[0]['latest_order_state'], None)
        self.assertEqual(ledger.projections, 0)


if __name__ == "__main__":
    unittest.main()
