"""Real failed SQLite writes stop background retrying at the declared budget."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.persistence import MarketStreamWriter

class WriterRetryLimitTests(unittest.TestCase):
    def test_six_failed_transactions_stop_worker_without_checkpoint_or_data_loss_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'imp-state.sqlite3'
            with LocalStateConnection(path) as state:
                writer=MarketStreamWriter(path,sources=('moomoo',),symbols=('AAPL',))
                writer.submit({'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL',
                    'capability':'US_EQUITY_TICKS','clocks':{'received_time_ns':1700000000000000000},
                    'raw_payload':{'price':10,'volume':1,'sequence':1}})
                # A real held write lock: the recoverable class the retry budget exists for.
                blocker=sqlite3.connect(path,isolation_level=None); blocker.execute('BEGIN IMMEDIATE')
                targets=[]
                def thread(**kwargs):
                    targets.append(kwargs['target']); value=MagicMock(); value.is_alive.return_value=False; return value
                with patch('market_platform_foundation.market_data.persistence.threading.Thread',side_effect=thread), \
                     patch.object(writer._wake,'wait'),patch.object(writer._stop,'wait') as wait:
                    writer.start(); targets[0]()
                    self.assertEqual(wait.call_count,5)
                    self.assertEqual([call.args[0] for call in wait.call_args_list],[1,2,4,8,16])
                status=writer.status()
                self.assertEqual(status['consecutive_failures'],6)
                self.assertEqual(status['error'],'WRITER_RETRY_LIMIT_EXCEEDED')
                self.assertFalse(status['accepting']); self.assertEqual(status['backlog'],1)
                self.assertEqual(writer.checkpoints(),[])
                self.assertEqual(state.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0],0)
                self.assertEqual(status['transient_failures'],6)
                blocker.execute('ROLLBACK'); blocker.close()
                writer._thread=None; writer.stop()
                self.assertEqual(state.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0],1)
                self.assertTrue(state.execute("SELECT 1 FROM market_stream_gaps WHERE reason='WRITER_RETRY_LIMIT_EXCEEDED'").fetchone())

    def test_unrecoverable_write_failure_stops_worker_on_first_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'imp-state.sqlite3'
            with LocalStateConnection(path) as state:
                writer=MarketStreamWriter(path,sources=('moomoo',),symbols=('AAPL',))
                writer.submit({'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL',
                    'capability':'US_EQUITY_TICKS','clocks':{'received_time_ns':1700000000000000000},
                    'raw_payload':{'price':10,'volume':1,'sequence':1}})
                writer.connection.execute("CREATE TRIGGER reject_pf01 BEFORE INSERT ON market_stream_records BEGIN SELECT RAISE(ABORT,'fixture'); END")
                targets=[]
                def thread(**kwargs):
                    targets.append(kwargs['target']); value=MagicMock(); value.is_alive.return_value=False; return value
                with patch('market_platform_foundation.market_data.persistence.threading.Thread',side_effect=thread), \
                     patch.object(writer._wake,'wait'),patch.object(writer._stop,'wait') as wait:
                    writer.start(); targets[0]()
                    wait.assert_not_called()
                status=writer.status()
                self.assertEqual((status['state'],status['consecutive_failures'],status['transient_failures']),('FAILED',1,0))
                self.assertFalse(status['accepting']); self.assertEqual(status['backlog'],1)
                self.assertEqual(state.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0],0)
                writer._thread=None; writer.stop()
                self.assertEqual(writer.status()['state'],'FAILED')
