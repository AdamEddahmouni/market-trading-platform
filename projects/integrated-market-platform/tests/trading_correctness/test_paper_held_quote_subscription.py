"""A held equity keeps its own live quote subscription after every other consumer lets go.

2026-10-28: RCL (-1 short) left the AI candidate list, the candidate consumer released its
BASIC_QUOTE subscription, and the portfolio-mark pass saw a cached (stale) mark and never
re-subscribed. No post-intent L1 event arrived, all six end-of-day closes were rejected
SIM_NO_POST_SIGNAL_BAR, and the unplanned carry then blocked every new entry.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager
from market_platform_foundation.ui_api.live_projections import PORTFOLIO_MARK_CONSUMER, _apply_portfolio_marks

CANDIDATES = "paper-automation-candidates"


class FakeRuntime:
    """Real reference-counted subscription manager; the quote cache outlives any subscription."""

    def __init__(self, cached=None, max_quota=100):
        self.subscriptions = LiveSubscriptionManager(max_quota=max_quota)
        self.cached = dict(cached or {})

    def subscribe(self, *, instrument_id, capabilities, consumer_id):
        return [dict(accepted=r.accepted, reason=r.reason) for r in (
            self.subscriptions.acquire(instrument_id=instrument_id, capability=c, consumer_id=consumer_id)
            for c in capabilities)]

    def unsubscribe(self, *, instrument_id, capabilities, consumer_id):
        for c in capabilities:
            self.subscriptions.release(instrument_id=instrument_id, capability=c, consumer_id=consumer_id)

    def live_mark_for(self, instrument_id):
        return self.cached.get(instrument_id.upper())

    def consumers(self, instrument_id):
        return {c for row in self.subscriptions.active_subscriptions()
                if row["instrument_id"] == instrument_id.upper() for c in row["consumers"]}


class FakeLedger:
    data_mode = "LIVE_OBSERVATIONAL"

    def __init__(self, positions):
        self.positions, self.marks = positions, {}

    def project_positions(self):
        return list(self.positions)

    def mark_for(self, instrument_id):
        return self.marks.get(instrument_id)

    def apply_live_mark(self, *, instrument_id, **mark):
        self.marks[instrument_id] = dict(mark)


def stale_mark(minor=29800):
    return dict(mark_minor=minor, mark_provider="MOOMOO", mark_as_of_ns=1, mark_quality="STALE", freshness_ms=600_000)


def run(runtime, ledger):
    store = SimpleNamespace(paper_ledger=ledger, data_mode="LIVE_OBSERVATIONAL")
    with patch("market_platform_foundation.local_state.startup.persist_ledger"):
        _apply_portfolio_marks(store, runtime)


class HeldQuoteSubscriptionTests(unittest.TestCase):
    def test_held_equity_is_resubscribed_after_candidate_release_despite_cached_mark(self):
        runtime = FakeRuntime(cached={"RCL": stale_mark()})
        runtime.subscribe(instrument_id="RCL", capabilities=["BASIC_QUOTE"], consumer_id=CANDIDATES)
        runtime.unsubscribe(instrument_id="RCL", capabilities=["BASIC_QUOTE"], consumer_id=CANDIDATES)
        self.assertEqual(runtime.consumers("RCL"), set())
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        run(runtime, ledger)
        self.assertEqual(runtime.consumers("RCL"), {PORTFOLIO_MARK_CONSUMER})

    def test_portfolio_subscription_survives_a_later_candidate_release(self):
        runtime = FakeRuntime(cached={"RCL": stale_mark()})
        runtime.subscribe(instrument_id="RCL", capabilities=["BASIC_QUOTE"], consumer_id=CANDIDATES)
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        run(runtime, ledger)
        runtime.unsubscribe(instrument_id="RCL", capabilities=["BASIC_QUOTE"], consumer_id=CANDIDATES)
        self.assertEqual(runtime.consumers("RCL"), {PORTFOLIO_MARK_CONSUMER})

    def test_repeated_passes_hold_one_reference(self):
        runtime = FakeRuntime(cached={"RCL": stale_mark()})
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        for _ in range(3):
            run(runtime, ledger)
        self.assertEqual(runtime.subscriptions.ref_count(instrument_id="RCL", capability="BASIC_QUOTE"), 1)

    def test_no_cached_mark_still_subscribes(self):
        runtime = FakeRuntime()
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        run(runtime, ledger)
        self.assertEqual(runtime.consumers("RCL"), {PORTFOLIO_MARK_CONSUMER})

    def test_stale_cached_mark_is_still_applied_as_stale(self):
        runtime = FakeRuntime(cached={"RCL": stale_mark(29900)})
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        run(runtime, ledger)
        self.assertEqual((ledger.marks["RCL"]["mark_minor"], ledger.marks["RCL"]["mark_quality"]), (29900, "STALE"))

    def test_quota_refusal_is_not_worked_around(self):
        runtime = FakeRuntime(cached={"RCL": stale_mark()}, max_quota=1)
        runtime.subscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE"], consumer_id=CANDIDATES)
        ledger = FakeLedger([dict(instrument_id="RCL", instrument_kind="TRADABLE_SECURITY", quantity=-1)])
        run(runtime, ledger)
        self.assertEqual(runtime.consumers("RCL"), set())
        self.assertEqual(runtime.consumers("AAPL"), {CANDIDATES})

    def test_crypto_position_never_takes_a_moomoo_subscription(self):
        runtime = FakeRuntime()
        ledger = FakeLedger([dict(instrument_id="XA01:81C3A5A44A4CC2B2", instrument_kind="CRYPTO_PAIR", quantity="0.5")])
        ledger.instrument_for = lambda iid: dict(instrument_id=iid, price_scale=10000)
        with patch("market_platform_foundation.ui_api.paper_market_evidence.PaperMarketEvidence.quote",
                   return_value=dict(admissible=False)):
            run(runtime, ledger)
        self.assertEqual(runtime.subscriptions.active_subscriptions(), [])

    def test_flat_position_takes_no_subscription(self):
        runtime = FakeRuntime()
        run(runtime, FakeLedger([]))
        self.assertEqual(runtime.subscriptions.active_subscriptions(), [])


if __name__ == "__main__":
    unittest.main()
