"""Execution evidence must retain venue clocks, source identity and availability."""
from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from market_platform_foundation.crypto_market.kraken_book import BookLevel, book_checksum
from market_platform_foundation.crypto_market.kraken_stream import BOOK, TRADES, KrakenStreamRuntime
from market_platform_foundation.ui_api.screener_crypto import project_ohlc

try:
    from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
except ImportError:
    PaperMarketEvidence = None

NOW = 1790510525  # Sunday 2026-09-27 12:02:05 UTC.
NS = 1_000_000_000
ID = 'XA01:1234567890ABCDEF'
INSTRUMENT = dict(instrument_id=ID, symbol='BTC/USD', provider_symbol='BTC/USD',
                  venue='KRAKEN', base_asset='BTC', quote_asset='USD', product_type='SPOT',
                  status='ONLINE', price_increment='0.0001', price_scale=10000)


def iso(epoch):
    return datetime.fromtimestamp(epoch, UTC).isoformat().replace('+00:00', 'Z')


def runtime():
    stream = KrakenStreamRuntime(resolve=lambda _id: ('BTC/USD', 4, 8), start_worker=False)
    stream.subscribe(instrument_id=ID, capabilities=[TRADES, BOOK], consumer_id='test')
    stream.lifecycle.connection_state = 'CONNECTED'
    stream.lifecycle.connected_ns = (NOW - 10) * NS
    stream._sent = {('trade', 'BTC/USD'), ('book', 'BTC/USD')}
    stream._acked = {key: (NOW - 9) * NS for key in stream._sent}
    bids = [BookLevel(Decimal('100.1234'), Decimal('2'))]
    asks = [BookLevel(Decimal('100.1236'), Decimal('3'))]
    checksum = book_checksum(bids, asks, price_decimals=4, qty_decimals=8)
    stream.handle(json.dumps(dict(channel='book', type='snapshot', data=[dict(
        symbol='BTC/USD', bids=[dict(price=100.1234, qty=2)], asks=[dict(price=100.1236, qty=3)],
        checksum=checksum, timestamp=iso(NOW - 2))])), received_ns=(NOW - 1) * NS)
    stream.handle(json.dumps(dict(channel='trade', type='update', data=[dict(
        symbol='BTC/USD', price='100.1235', qty='0.002', side='buy', trade_id=1,
        timestamp=iso(NOW - 2))])), received_ns=(NOW - 1) * NS)
    return stream


class CryptoSource:
    def __init__(self):
        self.calls = 0
        self.result = project_ohlc(dict(error=[], result={'BTC/USD': [
            [NOW - 125, '100', '102', '99', '101', '100.5', '3', 8],
            [NOW - 65, '101', '103', '100', '102', '101.5', '2', 5],
            [NOW - 5, '102', '104', '101', '103', '102.5', '1', 3],
        ]}), pair='BTC/USD', timeframe='1m', received_at=iso(NOW - 1))

    def row_for(self, key):
        assert key == ID
        return dict(INSTRUMENT, instrument={'instrument_id': ID}), None

    def bars(self, key, timeframe):
        assert key == ID and timeframe == '1m'
        self.calls += 1
        return self.result


class PaperMarketEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(PaperMarketEvidence, 'asset-aware Paper market adapter is missing')
        self.stream, self.source = runtime(), CryptoSource()
        self.adapter = PaperMarketEvidence(crypto=self.source, kraken_runtime=self.stream, clock=lambda: NOW)

    def read(self):
        return self.adapter.read(ID, universe='CRYPTO', instrument=INSTRUMENT)

    def test_weekend_crypto_uses_event_quotes_and_receipt_available_completed_bars(self):
        result = self.read()
        self.assertEqual((result['state'], result['session']['label']), ('READY', 'CONTINUOUS'))
        self.assertIsNone(result['session']['minutes_to_close'])
        self.assertEqual(result['observation_time'], NOW * NS)
        quote = result['quote']
        self.assertEqual((quote['last_price_minor'], quote['bid_price_minor'], quote['ask_price_minor']),
                         (1001235, 1001234, 1001236))
        self.assertEqual((quote['last_price'], quote['price_scale']), ('100.1235', 10000))
        self.assertEqual((quote['event_time_ns'], quote['received_time_ns']), ((NOW - 2) * NS, (NOW - 1) * NS))
        bars = result['bars']['bars']
        self.assertEqual([b['close'] for b in bars], [1010000, 1020000])
        self.assertEqual(bars[-1]['available_time'], (NOW - 1) * NS)
        self.assertEqual(bars[-1]['end_time'], (NOW - 5) * NS)
        self.assertEqual(self.source.calls, 1)

    def test_rest_snapshot_never_substitutes_for_missing_exchange_book(self):
        self.stream._books.clear()
        result = self.read()
        self.assertEqual(result['state'], 'BLOCKED')
        self.assertIn('CRYPTO_BOOK_UNAVAILABLE', result['blockers'])
        self.assertIsNone(result['quote'].get('event_time_ns'))

    def test_checksum_failure_withholds_execution_quote(self):
        self.stream._books[ID]._verify(-1)
        self.assertIn('CRYPTO_BOOK_INVALID', self.read()['blockers'])

    def test_disconnect_maintenance_and_reconnect_cannot_reuse_old_book(self):
        for state in ('RECONNECTING', 'MAINTENANCE', 'DISCONNECTED'):
            self.stream.lifecycle.connection_state = state
            with self.subTest(state=state):
                result = self.read()
                self.assertEqual(result['state'], 'BLOCKED')
                self.assertFalse(result['quote']['admissible'])
        self.stream.lifecycle.connection_state = 'CONNECTED'
        self.stream.lifecycle.connected_ns = NOW * NS
        self.assertIn('CRYPTO_PREVIOUS_CONNECTION_EVIDENCE', self.read()['blockers'])

    def test_old_event_time_is_stale_even_if_receipt_and_heartbeat_are_current(self):
        self.stream._trades[ID][-1]['event_time_ns'] = (NOW - 60) * NS
        self.stream._trades[ID][-1]['received_ns'] = NOW * NS
        self.stream._books[ID].confirm_continuity(NOW * NS)
        self.assertIn('QUOTE_STALE', self.read()['blockers'])

    def test_future_and_missing_event_clocks_fail_closed(self):
        for field, value in [('event_time_ns', (NOW + 1) * NS), ('event_time_ns', None),
                             ('received_ns', (NOW + 1) * NS)]:
            self.stream = runtime()
            self.adapter = PaperMarketEvidence(crypto=self.source, kraken_runtime=self.stream, clock=lambda: NOW)
            self.stream._trades[ID][-1][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(self.read()['quote']['admissible'])

    def test_unacknowledged_book_is_not_usable(self):
        self.stream._acked.pop(('book', 'BTC/USD'))
        self.assertIn('CRYPTO_SUBSCRIPTION_UNVERIFIED', self.read()['blockers'])

    def test_forming_future_and_receipt_future_bars_cannot_be_filled(self):
        self.source.result['bars'].append(self.source.result['forming'])
        result = self.read()
        self.assertEqual(result['bars']['state'], 'UNAVAILABLE')
        self.assertEqual(result['bars']['bars'], [])
        self.source = CryptoSource()
        self.source.result['received_at'] = iso(NOW + 1)
        self.adapter = PaperMarketEvidence(crypto=self.source, kraken_runtime=self.stream, clock=lambda: NOW)
        self.assertEqual(self.read()['bars']['bars'], [])

    def test_unavailable_source_never_blocks_another_provider_by_shared_health(self):
        bad_equity = lambda _key: (_ for _ in ()).throw(ConnectionError('offline'))
        self.adapter = PaperMarketEvidence(crypto=self.source, kraken_runtime=self.stream,
                                           equity_quote=bad_equity, clock=lambda: NOW)
        equity = self.adapter.quote('AAPL', universe='US_EQUITIES')
        self.assertFalse(equity['admissible'])
        self.assertEqual(self.read()['state'], 'READY')

    def test_dated_futures_quote_keeps_provider_session_but_bars_remain_unverified(self):
        row = dict(instrument_id='ES202612', symbol='ES202612', root='ES', expiry='2026-12-18',
                   provider_symbol='US.ES2612', contract_multiplier='50', price_increment='0.25', price_scale=100)
        class Futures:
            def quote_for(inner, key, *, universe):
                self.assertEqual((key, universe), ('ES202612', 'FUTURES'))
                return dict(state='LIVE', session_state='TRADING', fields={name: dict(value=value,
                    as_of=iso(NOW - 1), source='MOOMOO_OPEND') for name, value in
                    [('price', 6000.25), ('bid', 6000), ('ask', 6000.5)]})
        evidence = PaperMarketEvidence(multi=Futures(), clock=lambda: NOW).read('ES202612', universe='FUTURES', instrument=row)
        self.assertEqual((evidence['session']['label'], evidence['quote']['last_price_minor']), ('TRADING', 600025))
        self.assertIsNone(evidence['session']['minutes_to_close'])
        self.assertEqual(evidence['blockers'], ['FUTURES_BARS_UNVERIFIED'])
        self.assertEqual(evidence['bars']['bars'], [])

    def test_expired_or_undated_futures_and_reference_universes_fail_closed(self):
        for universe, row, code in [('FUTURES', {'expiry': '2020-01-01'}, 'FUTURES_CONTRACT_EXPIRED'),
                                     ('FUTURES', {}, 'FUTURES_DATED_CONTRACT_REQUIRED'),
                                     ('BONDS', {}, 'REFERENCE_ONLY_UNIVERSE'),
                                     ('FOREX', {}, 'UNSUPPORTED_UNIVERSE')]:
            with self.subTest(universe=universe):
                evidence = self.adapter.read('X', universe=universe, instrument=row)
                self.assertIn(code, evidence['blockers'])
                self.assertEqual(evidence['state'], 'BLOCKED')

    def test_equity_quotes_and_bars_delegate_without_crypto_identity(self):
        calls = []
        def quote(key):
            calls.append(('quote', key))
            return dict(state='LIVE', fields={name: dict(value=value, source='MOOMOO_OPEND', as_of_ns=(NOW - 1) * NS)
                for name, value in [('price', 200.25), ('bid', 200), ('ask', 200.5)]})
        series = SimpleNamespace(state='SESSION_CLOSED', reason='SESSION_CLOSED', provider_reason=None,
            received_ns=(NOW - 1) * NS, bars=(SimpleNamespace(start_ns=(NOW - 125) * NS, end_ns=(NOW - 65) * NS,
                open=200, high=201, low=199, close=200.25, volume=100),), forming=None)
        def bars(key, *, timeframe, scope):
            calls.append(('bars', key, timeframe, scope))
            return series
        adapter = PaperMarketEvidence(equity_quote=quote, equity_bars=bars, clock=lambda: NOW)
        result = adapter.read('XA01:EQUITY', universe='US_ETFS', instrument={'symbol': 'SPY'})
        self.assertEqual(result['quote']['last_price_minor'], 20025)
        self.assertEqual(result['bars']['bars'][0]['close'], 20025)
        self.assertEqual(calls, [('quote', 'SPY'), ('bars', 'SPY', '1m', 'EXTENDED')])
        self.assertEqual(result['session']['label'], 'CLOSED')


if __name__ == '__main__':
    unittest.main()
