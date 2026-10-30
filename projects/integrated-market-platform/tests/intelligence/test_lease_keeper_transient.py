"""AUD-042: one 'database is locked' renewal must not end the lease renewal thread.

The thread named imp-reevaluation-lease died on the first sqlite3.OperationalError (2026-10-27 ~13:42 ET and
2026-10-29 15:32 ET; audit repro R2). The same keeper renews the Paper controller's lease during a cycle, and
cycles took 293 s to 27 min against a 180 s lease, so a dead keeper let the lease expire mid-cycle.
"""
from __future__ import annotations

import sqlite3
import threading
import unittest

from market_platform_foundation.ui_api.screener_reevaluation import LeaseKeeper


class Renewals:
    def __init__(self, outcomes, keeper_box, limit):
        self.outcomes, self.calls, self.keeper_box, self.limit = list(outcomes), 0, keeper_box, limit

    def __call__(self):
        self.calls += 1
        if self.calls >= self.limit:
            self.keeper_box[0].stopped.set()  # the cycle ends
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def run_keeper(outcomes, limit=6):
    box, waits = [None], []
    renew = Renewals(outcomes, box, limit)
    keeper = LeaseKeeper(renew, 60, wait=waits.append)
    box[0] = keeper
    keeper.run()  # synchronous: the same loop the thread runs
    return keeper, renew, waits


class LeaseKeeperTransientTests(unittest.TestCase):
    def test_a_locked_renewal_is_retried_sooner_and_the_lease_keeps_being_renewed(self):
        keeper, renew, waits = run_keeper([True, sqlite3.OperationalError('database is locked'), True, True])
        self.assertEqual(keeper.transient_errors, 1)
        self.assertIn('database is locked', keeper.last_transient_error)
        self.assertGreaterEqual(keeper.renewals, 3)
        self.assertEqual(waits[:3], [60, 60, 15])  # after the refusal the next attempt comes at a quarter interval
        self.assertEqual(waits[3], 60)

    def test_a_refused_renewal_still_ends_the_keeper_for_good(self):
        keeper, renew, _ = run_keeper([True, False, True])
        self.assertEqual((keeper.renewals, renew.calls), (1, 2))

    def test_a_non_transient_error_still_ends_the_keeper(self):
        with self.assertRaises(sqlite3.IntegrityError):
            run_keeper([sqlite3.IntegrityError('UNIQUE constraint failed')])

    def test_the_thread_survives_a_lock_error_while_the_cycle_runs(self):
        renewed = threading.Event()
        calls = []

        def renew():
            calls.append(1)
            if len(calls) == 1:
                raise sqlite3.OperationalError('database is locked')
            renewed.set()
            return True
        with LeaseKeeper(renew, 0.04) as keeper:
            self.assertTrue(renewed.wait(5))
            self.assertTrue(keeper.thread.is_alive())
        keeper.thread.join(5)
        self.assertFalse(keeper.thread.is_alive())
        self.assertEqual(keeper.transient_errors, 1)


if __name__ == "__main__":
    unittest.main()
