"""Live US equity Paper fills: the regular-session price, the touch, and real traded volume (owner, 2026-10-29).

SOFTWARE_CONTROLLED: Moomoo QUOTE pushes and market snapshots are fixture payloads with the live field names. The
admission engine, the execution buffer, the risk engine and the bar-conservative simulator are production code.

Before this, the buffer priced every live bar from ``after_price`` first (the previous session's after-hours price,
which Moomoo keeps in regular-hours quotes) and gave every bar a synthetic volume of 100, so a 1/100 participation
cap filled exactly one share whatever the order and the market.
"""
from __future__ import annotations

import unittest

from market_platform_foundation.market_data.execution_event_buffer import LiveExecutionEventBuffer
from market_platform_foundation.market_data.live_admission import LiveAdmissionEngine
from market_platform_foundation.paper.contracts import build_instrument_ref, build_user_order_intent
from market_platform_foundation.paper.execution import execute_order_intent
from market_platform_foundation.paper.ledger import PaperExecutionLedger

S = 1_000_000_000
T0 = 1_000 * S
IID = 'HBAN'


def push(at_s, *, last, volume=None, after=15.65, clock='11:19:26'):
    """A QUOTE push: last trade, cumulative day volume, the after-hours fields, no bid/ask."""
    payload = dict(code='US.' + IID, data_date='2026-10-29', data_time=clock, last_price=last, after_price=after,
                   overnight_price=after, pre_price=after)
    if volume is not None:
        payload['volume'] = volume
    return payload, at_s


def snapshot(at_s, *, last, bid, ask, volume=None, after=15.65):
    """A get_market_snapshot row: update_time, the touch and its sizes, and the after-hours fields."""
    payload = dict(code='US.' + IID, update_time='2026-10-29 11:19:26.000', last_price=last, bid_price=bid, ask_price=ask,
                   bid_vol=900, ask_vol=700, after_price=after, overnight_price=after, pre_price=after)
    if volume is not None:
        payload['volume'] = volume
    return payload, at_s


def buffer_of(*events):
    buffer, engine = LiveExecutionEventBuffer(), LiveAdmissionEngine()
    for sequence, (payload, at_s) in enumerate(events, start=1):
        at = T0 + int(at_s * S)
        record = dict(capability='US_EQUITY_L1', clocks=dict(event_time_ns=at - 1000, provider_time_ns=at - 1000, received_time_ns=at),
                      instrument_id=IID, provider='moomoo', provider_symbol='US.' + IID, raw_payload=payload, sequence=sequence)
        assert buffer.append_admitted(engine.evaluate_record(record, wall_now_ns=at + 1_000_000), provider_generation=1)
    return buffer


def bars(buffer, at_s=1_000):
    return buffer.bars_for_execution(observation_time_ns=T0 + int(at_s * S), price_scale=100, instrument_id=IID)


def execute(buffer, *, quantity, created_s, side='BUY'):
    ledger = PaperExecutionLedger.open_session(replay_session_id='fill-truth', instrument_id=IID, symbol=IID, data_mode='LIVE_OBSERVATIONAL',
                                               data_provider='MOOMOO', execution_mode='INTERNAL_SIMULATION',
                                               execution_authority='PAPER_ONLY', execution_provider='INTERNAL')
    intent = build_user_order_intent(instrument=build_instrument_ref(instrument_id=IID, symbol=IID), side=side, quantity=quantity,
                                     observation_time=T0 + int(created_s * S), client_order_id='fill-truth', idempotency_key='fill-truth')
    return execute_order_intent(intent=intent, ledger=ledger, bars=bars(buffer))


class RegularSessionPriceTests(unittest.TestCase):
    def test_a_regular_hours_fill_is_priced_at_the_last_trade_never_the_after_hours_price(self):
        buffer = buffer_of(push(0, last=15.97, volume=1_000_000), push(30, last=15.99, volume=1_010_000))
        last = bars(buffer)[-1]['bar_payload']
        self.assertEqual((last['open'], last['high'], last['low'], last['close']), ('15.99', '15.99', '15.99', '15.99'))
        _decision, order, fill = execute(buffer, quantity=62, created_s=20)
        self.assertEqual(fill['fill_price_minor'], 1599)
        self.assertEqual(order['state'], 'FILLED')

    def test_a_buy_pays_the_ask_and_a_sell_receives_the_bid(self):
        buffer = buffer_of(snapshot(0, last=15.99, bid=15.98, ask=16.00, volume=1_000_000))
        last = bars(buffer)[-1]['bar_payload']
        self.assertEqual((last['high'], last['low'], last['close']), ('16.00', '15.98', '15.99'))

    def test_a_recent_snapshot_touch_prices_the_next_push_and_an_old_one_does_not(self):
        buffer = buffer_of(snapshot(0, last=15.99, bid=15.98, ask=16.00, volume=1_000_000),
                           push(1, last=15.99, volume=1_000_100), push(20, last=15.99, volume=1_000_200))
        recent, old = bars(buffer)[1]['bar_payload'], bars(buffer)[2]['bar_payload']
        self.assertEqual((recent['high'], recent['low']), ('16.00', '15.98'))
        self.assertEqual((old['high'], old['low']), ('15.99', '15.99'))

    def test_a_sub_cent_price_rounds_against_the_account(self):
        buffer = buffer_of(snapshot(0, last=15.995, bid=15.9851, ask=16.0049, volume=1_000_000))
        last = bars(buffer)[-1]['bar_payload']
        self.assertEqual((last['high'], last['low']), ('16.01', '15.98'))


class TradedVolumeTests(unittest.TestCase):
    def test_fill_size_follows_the_shares_actually_traded(self):
        liquid = buffer_of(push(0, last=15.99, volume=1_000_000), push(50, last=15.99, volume=1_010_000))
        thin = buffer_of(push(0, last=15.99, volume=1_000_000), push(50, last=15.99, volume=1_000_400))
        self.assertEqual((bars(liquid)[-1]['volume'], bars(thin)[-1]['volume']), (10_000, 400))
        _d, order, fill = execute(liquid, quantity=62, created_s=40)
        self.assertEqual((order['state'], fill['fill_quantity']), ('FILLED', 62))
        _d, order, fill = execute(thin, quantity=14, created_s=40)
        self.assertEqual((order['state'], fill['fill_quantity']), ('PARTIALLY_FILLED', 4))  # 1% of 400 shares

    def test_the_volume_window_is_at_most_sixty_seconds(self):
        buffer = buffer_of(push(0, last=15.99, volume=900_000), push(61, last=15.99, volume=1_000_000),
                           push(120, last=15.99, volume=1_000_400))
        self.assertEqual(bars(buffer)[-1]['volume'], 400)
        self.assertEqual(bars(buffer)[-1]['volume_basis'], 'VENUE_TRADED_VOLUME_60S')

    def test_no_volume_evidence_fills_nothing(self):
        for label, buffer in (('first quote', buffer_of(push(0, last=15.99, volume=1_000_000))),
                              ('no volume field', buffer_of(push(0, last=15.99), push(30, last=15.99))),
                              ('day counter reset', buffer_of(push(0, last=15.99, volume=1_000_000), push(30, last=15.99, volume=5_000)))):
            with self.subTest(label):
                self.assertEqual(bars(buffer)[-1]['volume'], 0)
                _d, order, fill = execute(buffer, quantity=10, created_s=-1 if label == 'first quote' else 10)
                self.assertIsNone(fill)
                self.assertIn('SIM_NO_ELIGIBLE_VOLUME', order['reason_codes'])


if __name__ == '__main__':
    unittest.main()
