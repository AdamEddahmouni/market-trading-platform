"""Integration check: writer health exposes bounded storage without mutating it."""
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.persistence import MarketStreamWriter


class CapacityHealthTests(unittest.TestCase):
    def test_health_warns_before_shared_bound_without_writing_or_lifting_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "imp-state.sqlite3"
            LocalStateConnection(path).close()
            writer = MarketStreamWriter(path, sources=("moomoo",), symbols=("AAPL",),
                                        max_database_bytes=16 * 1024**2)
            connection = writer.connection
            try:
                connection.execute("CREATE TABLE capacity_health_fixture (payload BLOB)")
                connection.execute("INSERT INTO capacity_health_fixture VALUES (zeroblob(?))", (5 * 1024**2,))
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                before = connection.execute("SELECT total_changes()").fetchone()[0]
                status = writer.status()
                self.assertIn("capacity", status)
                capacity = status["capacity"]
                self.assertEqual(capacity["state"], "WARNING")
                self.assertEqual(capacity["max_database_bytes"], 16 * 1024**2)
                self.assertEqual(capacity["used_bytes"], path.stat().st_size)
                self.assertEqual(capacity["retention_action"], "PRESERVE_ALL_STOP_BEFORE_BOUND")
                self.assertGreater(capacity["remaining_bytes"], 0)
                self.assertEqual(connection.execute("SELECT total_changes()").fetchone()[0], before)
            finally:
                writer.stop()
                connection.close()

    def test_missing_drive_capacity_is_unavailable_without_replacement_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "imp-state.sqlite3"
            LocalStateConnection(path).close()
            writer = MarketStreamWriter(path, sources=("moomoo",), symbols=("AAPL",))
            connection = writer.connection
            try:
                original = writer.connection.path
                absent = Path(directory) / "absent" / "imp-state.sqlite3"
                writer.connection.path = absent
                status = writer.status()
                self.assertIn("capacity", status)
                self.assertEqual(status["capacity"]["state"], "UNAVAILABLE")
                self.assertFalse(absent.exists())
            finally:
                writer.connection.path = original
                writer.stop()
                connection.close()
