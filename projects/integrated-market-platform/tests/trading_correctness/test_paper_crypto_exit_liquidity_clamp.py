"""SOFTWARE_CONTROLLED: owner decision (b), 2026-10-28 - trim a participation-limited crypto close to a legal residual.

Prints, marks and clocks are fixtures; every fill is a simulated fill. A close already reduced by print participation
is trimmed further, to the largest step-aligned fill whose residual still meets the venue minimum quantity and
minimum notional at the actual fill price. A full-size close with an illegal residual is still rejected, and a trim
below the venue minimum quantity is still a rejection with no financial mutation.
"""
import unittest
from decimal import Decimal

from tests.trading_correctness import test_paper_crypto_exit_completion_stress as stress

REASON = stress.REASON


class LiquidityClampTests(stress.StressBase):
    def one(self, is_short, close, price, volume, *, opened='1.6', open_price='1.0', **fresh):
        self.fresh(1000, **fresh); self.open(opened, is_short=is_short, price=open_price); self.mark('2.0')
        return self.attempt(Decimal(close), 'BUY' if is_short else 'SELL', Decimal(price), volume)

    def test_thin_print_trims_a_full_close_to_a_legal_notional_residual(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.6', '2.0', 140.0)  # eligible 1.4 would leave 0.2 = $0.40 < $0.50
                self.assertEqual((entry['outcome'], entry['filled']), ('PARTIALLY_FILLED', '1.35'), entry)
                self.assertEqual(abs(self.position()), Decimal('0.25'))
                self.assertTrue(entry['remainder_cancelled'])

    def test_trim_uses_the_actual_fill_price(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.6', '1.99', 140.0)  # ceil($0.50 / $1.99 to 0.001) = 0.252
                self.assertEqual((entry['outcome'], entry['filled']), ('PARTIALLY_FILLED', '1.348'), entry)
                self.assertEqual(abs(self.position()), Decimal('0.252'))

    def test_full_size_close_with_an_illegal_residual_is_still_rejected(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.35', '1.99', stress.DEEP)
                self.assertEqual((entry['outcome'], entry['reason_codes'], entry['filled']), ('REJECTED', [REASON], '0'), entry)

    def test_trim_below_the_venue_quantity_minimum_is_rejected_without_mutation(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                # Position 0.3, eligible 0.2: legal residual 0.25 allows only 0.05, below the 0.1 quantity minimum.
                entry = self.one(is_short, '0.3', '2.0', 20.0, opened='0.3', open_price='2.0',
                                 minimum_quantity='0.1')
                self.assertEqual((entry['outcome'], entry['reason_codes'], entry['filled']), ('REJECTED', [REASON], '0'), entry)
                self.assertEqual(abs(self.position()), Decimal('0.3'))

    def test_quantity_only_minimum_keeps_the_existing_partial_remainder_rule(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                entry = self.one(is_short, '1.6', '2.0', 140.0, minimum_quantity='0.3', minimum_notional=None)
                self.assertEqual((entry['outcome'], entry['filled']), ('PARTIALLY_FILLED', '1.3'), entry)

    def test_constant_thin_liquidity_and_repeated_partials_now_complete(self):
        for name, volumes, eligible in (('thin_constant', [140.0], Decimal('1.4')), ('repeated_partial', [30.0], Decimal('0.3'))):
            for is_short in (False, True):
                with self.subTest(case=name, short=is_short):
                    self.fresh(1000); self.open('1.6', is_short=is_short); self.mark('2.0')
                    log = self.drive('BUY' if is_short else 'SELL', ['2.0'], volumes)
                    row = self.classify(dict(case=name, short=is_short, clamp=True), log, Decimal('1.6'), '2.0', eligible)
                    self.assertEqual(row['verdict'], 'COMPLETED', row)
                    self.assertFalse(any(REASON in entry.get('reason_codes', []) for entry in log), log)

    def test_liquidity_below_one_legal_lot_still_stops_safely_at_a_legal_position(self):
        for is_short in (False, True):
            with self.subTest(short=is_short):
                self.fresh(1000); self.open('1.6', is_short=is_short); self.mark('2.0')
                log = self.drive('BUY' if is_short else 'SELL', ['2.0'], [20.0])
                row = self.classify(dict(case='below_one_legal_lot', short=is_short, clamp=True), log, Decimal('1.6'), '2.0',
                                    Decimal('0.2'))
                self.assertEqual(row['verdict'], 'EXPECTED_NON_COMPLETION', row)
                self.assertEqual(abs(self.position()), Decimal('0.25'))  # legal: exactly the $0.50 minimum notional


if __name__ == '__main__':
    unittest.main()
