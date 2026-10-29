"""SOFTWARE_CONTROLLED: equity and ETF closes never enter the crypto residual guard or its participation trim.

Simulator-level fixtures only. The same participation-limited close that the crypto guard rejects or trims fills
normally, in whole shares, for non-crypto instruments, so the crypto exit changes cannot alter equity execution.
"""
import unittest
from decimal import Decimal

from market_platform_foundation.execution.simulator import BarConservativeSimulator
from market_platform_foundation.numeric import apply_participation_cap
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY

REASON = 'SIM_CRYPTO_CLOSE_RESIDUAL_BELOW_MINIMUM'
POLICY = dict(DEFAULT_RISK_POLICY, participation_cap_numerator=1, participation_cap_denominator=100)
CRYPTO = dict(instrument_kind='CRYPTO_PAIR', minimum_quantity='0.001', quantity_step='0.001', tick_size='0.000001',
              price_scale=1_000_000, minimum_notional='0.5')


def bars(price, volume):
    return [dict(available_time=1000, normalized_event_id='bar-1', bar_payload=dict(high=price, low=price, volume=volume))]


def close(instrument, quantity, position, price, volume, direction='short'):
    intent = dict(created_time=500, direction=direction, instrument_id='CTRL', intent_id=f'ctrl-{direction}-{quantity}',
                  quantity=quantity)
    if instrument is not None:
        intent['instrument'] = instrument
    return BarConservativeSimulator(policy=POLICY).simulate(intent=intent, risk_decision=dict(decision='APPROVE',
        approved_quantity=quantity), bars=bars(price, volume), position_quantity=position)


class EquityGuardControlTests(unittest.TestCase):
    def test_participation_partial_equity_and_etf_closes_fill_whole_shares_without_the_crypto_guard(self):
        self.assertEqual(apply_participation_cap(900, numerator=1, denominator=100), 9)
        for kind in (None, 'EQUITY', 'ETF'):
            for direction, position in (('short', 10), ('long', -10)):
                with self.subTest(kind=kind, direction=direction):
                    order, fill = close(None if kind is None else dict(instrument_kind=kind), 10, position, '101.0000', 900,
                                        direction)
                    self.assertEqual(order['state'], 'PARTIALLY_FILLED', order)
                    self.assertNotIn(REASON, order.get('reason_codes') or [])
                    self.assertEqual(fill['fill_quantity'], 9)  # one-share residual: no crypto venue minimum applies
                    self.assertNotIn('price_scale', fill)

    def test_full_size_equity_close_is_unaffected_by_crypto_residual_rules(self):
        order, fill = close(dict(instrument_kind='EQUITY'), 9, 10, '0.0100', 100_000)
        self.assertEqual((order['state'], fill['fill_quantity']), ('FILLED', 9))

    def test_same_shape_crypto_close_does_enter_the_guard(self):
        # Contrast, so the control is known to exercise the branch: eligible 1.4 of 1.6 would leave $0.40 < $0.50.
        for direction, position in (('short', '1.6'), ('long', '-1.6')):
            with self.subTest(direction=direction):
                order, fill = close(CRYPTO, '1.6', position, '2.000000', '140', direction)
                trimmed = fill is not None and Decimal(fill['fill_quantity']) == Decimal('1.345')  # 2% buffer
                rejected = fill is None and order.get('reason_codes') == [REASON]
                self.assertTrue(trimmed or rejected, (order, fill))


if __name__ == '__main__':
    unittest.main()
