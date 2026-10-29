"""SOFTWARE_CONTROLLED: read-only export of the Paper ledger journal and per-date borrow (owner decision D8, 2026-10-29).

Full accounting acceptance needs the contiguous INTENT/ORDER/FILL/CANCEL/COST/BORROW journal; fill-level routes do not
carry it. ``GET /paper/journal`` returns the ledger's own events in sequence order, pages by sequence, reports
whether the journal is contiguous, lists every borrow accrual with its date, and never appends anything.
"""
import unittest

from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
from market_platform_foundation.platform.security.route_policy import policy_for_route as policy_for
from market_platform_foundation.ui_api import paper_experiment
from tests.trading_correctness import test_paper_crypto_shorts as shorts
from tests.trading_correctness.test_paper_experiment_api import _Base

S = shorts.S


class JournalPayloadTests(_Base):
    def test_events_come_back_in_sequence_order_and_page_without_gaps(self):
        experiment = self.create()
        for index in range(4):
            self.order("AAPL", "BUY" if index % 2 == 0 else "SELL", 1, "150.00")
        ledger = self.store.paper_ledger
        before = list(ledger.events)
        first = paper_experiment.journal_payload(self.store, limit=5)
        self.assertEqual(first["experiment_id"], experiment["experiment_id"])
        self.assertEqual(first["total_count"], len(before))
        self.assertTrue(first["contiguous"])
        pages, after = [first], first["next_after"]
        while after is not None:
            pages.append(paper_experiment.journal_payload(self.store, after=after, limit=5))
            after = pages[-1]["next_after"]
        sequences = [event["sequence"] for page in pages for event in page["events"]]
        self.assertEqual(sequences, sorted(int(event["sequence"]) for event in before))
        types = {event["event_type"] for page in pages for event in page["events"]}
        self.assertTrue({"OrderIntentCreated", "RiskDecisionRecorded", "OrderSubmitted", "FillRecorded"} <= types, types)
        self.assertEqual(ledger.events, before)  # reading appended nothing

    def test_payload_passes_the_response_leak_audit(self):
        self.create()
        self.order("AAPL", "BUY", 1, "150.00")
        assert_no_secrets_in_payload(paper_experiment.journal_payload(self.store))

    def test_bounds_and_bad_cursor(self):
        self.create()
        self.assertEqual(paper_experiment.journal_payload(self.store, limit=10_000)["page_size"], 500)
        self.assertEqual(paper_experiment.journal_payload(self.store, limit=-5)["page_size"], 1)
        with self.assertRaisesRegex(ValueError, "JOURNAL_CURSOR_INVALID"):
            paper_experiment.journal_payload(self.store, after=-1)
        self.assertEqual(paper_experiment.journal_payload(self.store, after=10**9)["events"], [])

    def test_unknown_experiment_is_refused_and_no_experiment_is_empty(self):
        with self.assertRaisesRegex(ValueError, "EXPERIMENT_NOT_FOUND"):
            paper_experiment.journal_payload(self.store, experiment_id="PPE-NOPE")
        empty = paper_experiment.journal_payload(self.store)
        self.assertEqual((empty["events"], empty["total_count"]), ([], 0))


class JournalBorrowTests(unittest.TestCase):
    # The crypto-short fixture's helpers only, so its own tests are not collected twice.
    setUp, order, mark = shorts.CryptoShortTests.setUp, shorts.CryptoShortTests.order, shorts.CryptoShortTests.mark

    def test_borrow_accruals_are_listed_per_date_and_match_the_projection(self):
        self.order('1.5'); self.mark(2)
        self.book.accrue_short_borrow_fees(accrual_date='2026-10-28', as_of_ns=200 * S)
        self.book.accrue_short_borrow_fees(accrual_date='2026-10-29', as_of_ns=220 * S)
        self.book.accrue_short_borrow_fees(accrual_date='2026-10-29', as_of_ns=230 * S)  # idempotent per date
        journal = paper_experiment.ledger_journal(self.book)
        self.assertEqual([row['accrual_date'] for row in journal['borrow_accruals']], ['2026-10-28', '2026-10-29'])
        self.assertEqual(journal['borrow_total_minor'], journal['projected_total_borrow_fees_minor'])
        self.assertEqual(journal['borrow_total_minor'], 2)
        self.assertTrue(journal['contiguous'])
        borrow_events = [e for e in journal['events'] if e['event_type'] == 'ShortBorrowFeeAccrued']
        self.assertEqual([e['sequence'] for e in borrow_events], [row['sequence'] for row in journal['borrow_accruals']])

    def test_a_gap_in_sequences_is_reported_not_hidden(self):
        self.order('1.5')
        journal = paper_experiment.ledger_journal(self.book)
        self.assertTrue(journal['contiguous'])
        self.book.events.pop(1)  # simulate an incomplete capture of the journal
        self.assertFalse(paper_experiment.ledger_journal(self.book)['contiguous'])


class JournalRoutePolicyTests(unittest.TestCase):
    def test_journal_is_an_audit_read(self):
        policy = policy_for("GET", "/paper/journal")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.capability, "audit.read")


if __name__ == '__main__':
    unittest.main()
