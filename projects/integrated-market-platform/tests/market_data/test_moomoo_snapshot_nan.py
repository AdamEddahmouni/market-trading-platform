"""OpenD snapshot frames carry NaN for absent numbers; the L1 observation (with bid/ask) must still be stored."""
import math
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
if str(ROOT / 'tools/moomoo') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools/moomoo'))

import pandas as pd  # noqa: E402
import push_feed  # noqa: E402
from market_platform_foundation.local_state.connection import LocalStateConnection  # noqa: E402
from market_platform_foundation.market_data.persistence import MarketStreamWriter  # noqa: E402
from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager  # noqa: E402

# Shape of a real overnight get_market_snapshot row (2026-10-14): BBO present, fundamentals NaN.
SNAPSHOT = {'code': 'US.AAPL', 'update_time': '2026-10-14 01:57:00.699', 'last_price': 341.27, 'bid_price': 341.1,
            'ask_price': 341.2, 'bid_vol': 80.0, 'ask_vol': 200.0, 'pe_ratio': float('nan'),
            'short_sell_rate': float('nan'), 'enable_margin': float('inf')}


class SnapshotNaNTests(unittest.TestCase):
    def test_payload_rows_turns_non_finite_numbers_into_none(self):
        for data in (pd.DataFrame([SNAPSHOT]), [SNAPSHOT], SNAPSHOT):
            row = push_feed.payload_rows(data)[0]
            self.assertIsNone(row['pe_ratio'])
            self.assertIsNone(row['enable_margin'])
            self.assertEqual((row['bid_price'], row['ask_price'], row['last_price']), (341.1, 341.2, 341.27))
            self.assertFalse(any(isinstance(v, float) and not math.isfinite(v) for v in row.values()))

    def _store(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            LocalStateConnection(path).close()
            writer = MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',))
            records = []
            feed = push_feed.MoomooPushFeed(subscriptions=LiveSubscriptionManager(), on_record=records.append)
            feed._enqueue_from_payload(capability='US_EQUITY_L1', generation=1, payload=payload)
            feed._process_envelope(feed.queue.dequeue_batch(timeout=0)[0])
            with patch('market_platform_foundation.market_data.persistence._WRITER', writer):
                accepted = writer.submit(records[0], {})
                writer.stop()
            with closing(sqlite3.connect(path)) as db:
                stored = db.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0]
                invalid = db.execute("SELECT COALESCE(SUM(observations),0) FROM market_stream_gaps "
                                     "WHERE reason='INVALID_OBSERVATION'").fetchone()[0]
        return accepted, stored, invalid

    def test_snapshot_l1_with_bbo_is_stored_after_normalization(self):
        self.assertEqual(self._store(push_feed.payload_rows(pd.DataFrame([SNAPSHOT]))[0]), (True, 1, 0))

    def test_raw_nan_row_is_what_the_writer_refused(self):
        self.assertEqual(self._store(dict(SNAPSHOT)), (False, 0, 1))


if __name__ == '__main__':
    unittest.main()
