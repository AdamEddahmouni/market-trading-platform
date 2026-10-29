"""Owner decision D12, option A (2026-10-29): a liquid crypto entry waits up to 30 s for a fresh venue print.

SOFTWARE_CONTROLLED: the Kraken stream stand-in, the screener's 24 h trade count and the clock are fixtures; the
controller, preview, pre-trade gate, simulator and ledger are production code. Freshness itself is unchanged: only
prints within the quote age price an entry, and when none arrives the entry is still deferred REQUIRED_PRICE_MISSING.
"""
from __future__ import annotations

from market_platform_foundation.ui_api import paper_automation as controller
from tests.trading_correctness import test_paper_crypto_live_execution as live

POLL = getattr(controller, 'PRICE_WAIT_POLL_SECONDS', 0.25)
BOUND = getattr(controller, 'PRICE_WAIT_SECONDS', 30)
FLOOR = getattr(controller, 'PRICE_WAIT_MIN_TRADES_24H', 2000)


class _NoInherited(live.CryptoAutonomousExecutionTests):
    pass


for _name in [n for n in dir(live.CryptoAutonomousExecutionTests) if n.startswith('test_')]:
    setattr(_NoInherited, _name, None)  # reuse the crypto controller fixture only, not its tests


class EntryPriceWaitTests(_NoInherited):
    def setUp(self):
        super().setUp()
        self.polls, self.on_poll = [], None
        self.auto.service.sleep = self.sleep

    def sleep(self, seconds):
        if seconds == POLL:
            self.polls.append(seconds)
            if self.on_poll:
                self.on_poll(len(self.polls))

    def liquidity(self, trades):
        """The screener's last Kraken ticker snapshot, as the controller's catalog row carries it."""
        values = {} if trades is None else {self.iid: dict(trade_count=float(trades))}
        self.crypto_source._snapshot_cache = (0.0, '2026-10-29T15:00:00Z', values, None)

    def intent(self):
        decision = self.auto.actions.history(self.iid)[0]
        account = self.auto.store.paper_ledger.paper_account_id
        return self.auto.service.repository.get_intent(controller.intent_identity(account, decision['decision_id']))

    def assert_untouched(self):
        self.assertEqual(self.auto.orders(), [])
        self.assertEqual(self.auto.store.paper_ledger.project_account()['cash_minor'], 10_000_000)

    def assert_previewed_at_once(self):
        receipt = self.start_crypto()
        self.assertIn(('DEFERRED', ['REQUIRED_PRICE_MISSING']), self.outcomes(receipt))
        self.assertEqual(self.polls, [])
        self.assertNotIn('price_wait', self.intent())
        self.assert_untouched()

    def test_a_liquid_pair_waits_for_the_next_print_and_enters_on_it(self):
        self.liquidity(5000)
        self.on_poll = lambda n: n == 3 and self.tape.market(self.iid, 800.0, 200.0)
        receipt = self.start_crypto()
        submitted = [r for r in receipt['actions'] if r['outcome'] == 'SUBMITTED']
        self.assertEqual([r['filled_quantity'] for r in submitted], ['1.125'], receipt)
        self.assertEqual(len(self.polls), 3)
        wait = self.intent()['price_wait']
        self.assertEqual((wait['fresh_print'], wait['polls'], wait['trades_24h']), (True, 3, 5000))

    def test_a_liquid_pair_without_a_print_waits_the_bound_then_defers_as_before(self):
        self.liquidity(FLOOR)  # the floor itself is liquid
        receipt = self.start_crypto()
        self.assertIn(('DEFERRED', ['REQUIRED_PRICE_MISSING']), self.outcomes(receipt))
        self.assertEqual(len(self.polls), int(BOUND / POLL))
        wait = self.intent()['price_wait']
        self.assertEqual((wait['fresh_print'], wait['waited_seconds']), (False, BOUND))
        self.assert_untouched()

    def test_a_pair_with_a_fresh_print_already_is_not_delayed(self):
        self.liquidity(5000)
        self.tape.market(self.iid, 800.0, 200.0)
        receipt = self.start_crypto()
        self.assertEqual([r['filled_quantity'] for r in receipt['actions'] if r['outcome'] == 'SUBMITTED'], ['1.125'], receipt)
        self.assertEqual(self.polls, [])

    def test_a_thin_pair_is_previewed_at_once(self):
        self.liquidity(FLOOR - 1)
        self.assert_previewed_at_once()

    def test_unknown_liquidity_is_previewed_at_once(self):
        self.liquidity(None)
        self.assert_previewed_at_once()

    def test_a_pair_without_a_live_trade_stream_is_previewed_at_once(self):
        self.liquidity(5000)
        self.tape.acked.pop(self.iid)  # no TRADES acknowledgement: no print can arrive, so waiting is pointless
        self.assert_previewed_at_once()

    def test_waiting_never_extends_the_decision(self):
        self.liquidity(5000)

        def expire(n):
            if n == 1:
                self.clock.value += 3600  # the decision's validity ends while the entry waits; then a print arrives
                self.tape.market(self.iid, 800.0, 200.0)
        self.on_poll = expire
        receipt = self.start_crypto()
        refused = [codes for outcome, codes in self.outcomes(receipt) if outcome == 'DEFERRED']
        self.assertTrue(any(codes[0] in ('ACTION_DECISION_EXPIRED', 'CANDIDATE_EXPIRED') for codes in refused), receipt)
        self.assert_untouched()

    def test_one_pass_waits_at_most_the_bound_in_total(self):
        self.liquidity(None)
        self.start_crypto()
        self.liquidity(5000)
        service, instrument = self.auto.service, dict(instrument_kind='CRYPTO_PAIR')
        service._price_wait_left = BOUND
        first, second = dict(intent_id='first'), dict(intent_id='second')
        service._await_entry_print(first, self.iid, instrument)
        service._await_entry_print(second, self.iid, instrument)
        self.assertEqual(len(self.polls), int(BOUND / POLL))
        self.assertEqual(first['price_wait']['polls'], int(BOUND / POLL))
        self.assertNotIn('price_wait', second)
