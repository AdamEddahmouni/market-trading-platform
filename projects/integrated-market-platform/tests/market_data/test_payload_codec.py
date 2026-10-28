"""Lossless payload codec: byte-exact round trips, plain text untouched, fail closed on damage (2026-10-27)."""
import json
import sqlite3
import unittest

from market_platform_foundation.local_state import payload_codec as codec


def sample(i):
    return json.dumps({'capability': 'US_EQUITY_L1', 'provider': 'moomoo', 'raw_payload': {
        'code': 'US.NVDA', 'last_price': 217.9 + i / 100, 'delta': 'N/A', 'gamma': 'N/A', 'data_time': f'16:00:{i:02d}'}},
        sort_keys=True, separators=(',', ':'))


class PayloadCodecTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.codec = codec.PayloadCodec(self.conn)
        self.scope = codec.stream_scope('moomoo', 'US_EQUITY_L1')

    def test_no_dictionary_keeps_plain_text(self):
        self.assertEqual(self.codec.encode(self.scope, sample(1)), sample(1))
        self.assertIsNone(self.codec.create(self.scope, [sample(i) for i in range(5)]))  # too few samples

    def test_round_trip_is_byte_exact_and_smaller(self):
        self.assertIsNotNone(self.codec.create(self.scope, [sample(i) for i in range(40)]))
        for i in range(40, 60):
            blob = self.codec.encode(self.scope, sample(i))
            self.assertTrue(codec.is_encoded(blob))
            self.assertLess(len(blob), len(sample(i)))
            self.assertEqual(codec.PayloadCodec(self.conn).decode(blob), sample(i))  # fresh cache reads the table

    def test_first_dictionary_wins_and_text_passes_through(self):
        first = self.codec.create(self.scope, [sample(i) for i in range(40)])
        self.assertEqual(self.codec.create(self.scope, [sample(i) for i in range(40, 80)]), first)
        self.assertEqual(self.codec.decode(sample(3)), sample(3))

    def test_damage_and_unknown_dictionaries_fail_closed(self):
        self.codec.create(self.scope, [sample(i) for i in range(40)])
        blob = self.codec.encode(self.scope, sample(50))
        with self.assertRaises(codec.PayloadCodecError):
            self.codec.decode(blob[:-3] + b'xyz')
        with self.assertRaises(codec.PayloadCodecError):
            codec.PayloadCodec(sqlite3.connect(':memory:')).decode(blob)
        with self.assertRaises(codec.PayloadCodecError):
            self.codec.decode(b'not-a-codec-value')


if __name__ == '__main__':
    unittest.main()
