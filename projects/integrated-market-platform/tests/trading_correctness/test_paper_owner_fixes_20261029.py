"""SOFTWARE_CONTROLLED: owner decisions of 2026-10-29 (fresh-context review of the crypto exit series).

- D4: a crypto close trimmed to a legal residual carries an informational reason code; it is still PARTIALLY_FILLED.
- F1: trimmed and capped crypto closes leave the minimum notional plus a 2% buffer, so one lower print cannot
  strand the remainder below the venue minimum.
- F2: a participation-limited opening (or adding) crypto fill never creates a position below the venue minimum
  notional at its fill price: such a fill is not made.
- F5: a bad instrument field while sizing an automation close blocks that close, not the whole cycle.
- F4: close events (margin cover, end-of-day, open close) keep the order's own reason codes.
- Carry: an unplanned US equity carry blocks equity-session entries only; the continuous crypto scope trades on,
  and every portfolio-level gate still applies to it.
"""
import unittest
from decimal import Decimal

from market_platform_foundation.ui_api import paper_automation as controller
from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
from tests.trading_correctness import test_paper_crypto_exit_completion_stress as stress

TRIMMED = 'SIM_CRYPTO_CLOSE_TRIMMED_TO_LEGAL_RESIDUAL'
BUFFERED_MINIMUM = Decimal('0.5') * Decimal('1.02')


class TrimmedCloseTests(stress.StressBase):
    def one(self, is_short, close, price, volume, *, opened='1.6'):
        self.fresh(1000); self.open(opened, is_short=is_short); self.mark('2.0')
        return self.attempt(Decimal(close), 'BUY' if is_short else 'SELL', Decimal(price), volume)

    def test_trimmed_close_carries_the_informational_reason_code(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.6', '2.0', 140.0)
                self.assertEqual(entry['outcome'], 'PARTIALLY_FILLED', entry)
                self.assertEqual(entry['reason_codes'], [TRIMMED], entry)

    def test_untrimmed_participation_partial_has_no_trim_code(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.6', '2.0', 50.0)  # eligible 0.5 leaves a legal 1.1
                self.assertEqual((entry['outcome'], entry['filled']), ('PARTIALLY_FILLED', '0.5'), entry)
                self.assertNotIn(TRIMMED, entry['reason_codes'], entry)

    def test_trimmed_residual_keeps_the_notional_buffer_at_the_fill_price(self):
        for price in ('2.0', '1.99'):
            for is_short in (False, True):
                with self.subTest(price=price, short=is_short):
                    entry = self.one(is_short, '1.6', price, 140.0)
                    self.assertEqual(entry['outcome'], 'PARTIALLY_FILLED', entry)
                    self.assertGreaterEqual(abs(self.position()) * Decimal(price), BUFFERED_MINIMUM)


class CappedSizingBufferTests(stress.StressBase):
    def test_capped_close_leaves_the_minimum_notional_plus_buffer(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                self.fresh(300); self.open('1.6', is_short=is_short); self.mark('2.0')  # $3 order cap
                close = capped_exit_quantity(self.book, stress.IID, Decimal('1.6'))
                self.assertGreater(close, 0)
                self.assertGreaterEqual((Decimal('1.6') - close) * Decimal('2.0'), BUFFERED_MINIMUM)


class OpeningDustTests(stress.StressBase):
    def fill(self, result):
        fill = result.get('fill')
        return Decimal(fill['fill_quantity']) if fill else Decimal(0)

    def test_partial_opening_below_the_minimum_notional_is_not_filled(self):
        for side in ('BUY', 'SELL'):
            with self.subTest(side=side):
                self.fresh(1000); self.mark('2.0')
                result = self.submit(Decimal('1.0'), side, Decimal('2.0'), 20.0)  # eligible 0.2 = $0.40 < $0.50
                self.assertEqual(self.fill(result), 0, result['order'])
                self.assertEqual(self.position(), 0)

    def test_partial_opening_at_or_above_the_minimum_notional_still_fills(self):
        for side in ('BUY', 'SELL'):
            with self.subTest(side=side):
                self.fresh(1000); self.mark('2.0')
                result = self.submit(Decimal('1.0'), side, Decimal('2.0'), 30.0)  # eligible 0.3 = $0.60
                self.assertEqual(self.fill(result), Decimal('0.3'), result['order'])

    def test_small_partial_add_to_a_legal_position_still_fills(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                self.fresh(1000); self.open('1.0', is_short=is_short, price='2.0'); self.mark('2.0')
                result = self.submit(Decimal('1.0'), 'SELL' if is_short else 'BUY', Decimal('2.0'), 20.0)
                self.assertEqual(self.fill(result), Decimal('0.2'), result['order'])
                self.assertEqual(abs(self.position()), Decimal('1.2'))


class CarryScopeTests(unittest.TestCase):
    pending = dict(carry=dict(pending={'RCL': dict(quantity=-1, entry_ns=1, session_date='2026-10-28')}))

    def test_equity_session_entries_wait_for_the_carry(self):
        for label in ('REGULAR', 'PRE_MARKET', 'POST_MARKET', 'CLOSED'):
            with self.subTest(label=label):
                self.assertTrue(controller.PaperAutomationService._carry_blocks_entries(self.pending, dict(label=label)))

    def test_continuous_crypto_scope_is_not_blocked_by_an_equity_carry(self):
        self.assertFalse(controller.PaperAutomationService._carry_blocks_entries(self.pending, dict(label='CONTINUOUS')))

    def test_no_carry_blocks_nothing(self):
        for work in ({}, dict(carry=None), dict(carry=dict(pending={}))):
            with self.subTest(work=work):
                self.assertFalse(controller.PaperAutomationService._carry_blocks_entries(work, dict(label='REGULAR')))


class CloseSizingFaultTests(unittest.TestCase):
    def test_bad_instrument_field_blocks_only_that_close(self):
        from types import SimpleNamespace

        class Ledger:
            def instrument_for(self, iid):
                raise KeyError('quantity_step')

        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        service.store = SimpleNamespace(paper_ledger=Ledger())
        events = []
        service._event = lambda kind, **payload: events.append((kind, payload))
        summary = dict(actions=[])
        outcome = service._close_position(dict(arming=dict(arming_id='A')), dict(policy_id='P'), summary, 1.0, iid='XA01:BAD',
                                          held=Decimal('1.5'), key='PAI-EOD-x-1', action='EOD_FLATTEN',
                                          event='PAPER_EOD_FLATTEN', headline='h', reason=dict(code='C', label='L'))
        self.assertEqual(outcome['outcome'], 'BLOCKED')
        self.assertEqual(outcome['reason_codes'], ['PAPER_CLOSE_SIZING_KeyError'])
        self.assertEqual(summary['actions'], [outcome])
        self.assertEqual(events[0][0], 'PAPER_EOD_FLATTEN')


class CloseEventReasonCodeTests(unittest.TestCase):
    def test_close_outcome_keeps_the_order_reason_codes(self):
        import contextlib
        from types import SimpleNamespace
        from unittest.mock import patch

        class Ledger:
            def instrument_for(self, iid):
                return dict(instrument_kind='TRADABLE_SECURITY')

            def lookup_order(self, order_id):
                return dict(state='PARTIALLY_FILLED', reason_codes=[TRIMMED], cumulative_filled_quantity='1.345')

        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        service.store = SimpleNamespace(paper_ledger=Ledger())
        service.submit_lock = contextlib.nullcontext
        service._still_permitted = lambda work: True
        service._submit = lambda body: dict(order_id='O-1')
        service._cancel_order = lambda order_id, reason: True
        service._event = lambda kind, **payload: None
        summary = dict(actions=[])
        with patch('market_platform_foundation.ui_api.paper_projections.preview_paper_order',
                   return_value=dict(preview=dict(risk_status='PASS', preview_id='P-1'))):
            outcome = service._close_position(dict(arming=dict(arming_id='A')), dict(policy_id='P'), summary, 1.0, iid='RCL',
                                              held=Decimal(-1), key='PAI-COVER-x-1', action='MARGIN_COVER',
                                              event='PAPER_MARGIN_COVER', headline='h', reason=dict(code='C', label='L'))
        self.assertEqual(outcome['reason_codes'], ['PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION', TRIMMED])


if __name__ == '__main__':
    unittest.main()
