"""AUD-044: a write waiting on another process's SQLite write lock must not stall the API's reads.

On 2026-10-29 one shared ``LocalStateConnection`` served every API thread. A write that met the collector's
write lock waited out SQLite's busy timeout while holding the connection's lock, and every read queued behind
it: 15.7 s behind one waiting write, 39.3 s behind three (audit repro R1). The keeper's /context probe was one of
those reads, so the platform was restarted again and again. These tests use temporary stores only.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.local_state.connection import LocalStateConnection


class ForeignWriteLockCase(unittest.TestCase):
    BUSY_MS = "2000"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.env = mock.patch.dict(os.environ, {"IMP_STATE_BUSY_TIMEOUT_MS": self.BUSY_MS})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.state = self.open_state()
        self.state.execute("CREATE TABLE t(x INTEGER NOT NULL)")
        self.state.executemany("INSERT INTO t VALUES (?)", [(index,) for index in range(10)])

    def open_state(self) -> LocalStateConnection:
        state = LocalStateConnection(self.path, verify=False)
        self.addCleanup(state.close)
        return state

    def hold_foreign_write_lock(self) -> sqlite3.Connection:
        """Another process (the collector child) holding the store's write lock."""
        blocker = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        blocker.execute("INSERT INTO t VALUES (-1)")
        self.addCleanup(blocker.close)
        return blocker

    def start_waiting_writers(self, count: int, retry_seconds: float | None) -> tuple[list[threading.Thread], list]:
        outcomes: list = []

        def write(value: int) -> None:
            try:
                with self.state.transaction(retry_seconds=retry_seconds):
                    self.state.execute("INSERT INTO t VALUES (?)", (value,))
                outcomes.append("COMMITTED")
            except sqlite3.OperationalError as exc:
                outcomes.append(str(exc))

        threads = [threading.Thread(target=write, args=(1000 + index,), daemon=True) for index in range(count)]
        [thread.start() for thread in threads]
        time.sleep(0.3)  # every writer is now waiting on the foreign lock
        return threads, outcomes

    def timed_read(self) -> tuple[float, int]:
        started = time.monotonic()
        value = int(self.state.execute("SELECT COUNT(*) FROM t").fetchone()[0])
        return time.monotonic() - started, value


class ReadIsolationTests(ForeignWriteLockCase):
    def test_a_read_answers_at_once_while_one_write_waits_on_a_foreign_lock(self):
        blocker = self.hold_foreign_write_lock()
        threads, outcomes = self.start_waiting_writers(1, retry_seconds=None)
        elapsed, value = self.timed_read()
        self.assertLess(elapsed, 1.0)
        self.assertEqual(value, 10)  # the foreign transaction is not committed, so its row is not visible
        blocker.execute("ROLLBACK")
        [thread.join(10) for thread in threads]
        self.assertEqual(outcomes, ["COMMITTED"])

    def test_three_waiting_writes_do_not_stack_up_in_front_of_a_read(self):
        blocker = self.hold_foreign_write_lock()
        threads, outcomes = self.start_waiting_writers(3, retry_seconds=None)
        for _ in range(5):
            elapsed, _ = self.timed_read()
            self.assertLess(elapsed, 1.0)
        blocker.execute("ROLLBACK")
        [thread.join(15) for thread in threads]
        self.assertEqual(outcomes, ["COMMITTED"] * 3)
        self.assertEqual(self.timed_read()[1], 13)

    def test_a_committed_write_is_visible_to_the_next_read_from_any_thread(self):
        self.state.execute("INSERT INTO t VALUES (500)")
        seen: list[int] = []
        thread = threading.Thread(target=lambda: seen.append(self.timed_read()[1]))
        thread.start()
        thread.join(5)
        self.assertEqual(seen, [11])
        with self.state.transaction():
            self.state.execute("INSERT INTO t VALUES (501)")
            # Inside its own transaction a thread reads its own uncommitted write on the shared connection.
            self.assertEqual(int(self.state.execute("SELECT COUNT(*) FROM t").fetchone()[0]), 12)
        self.assertEqual(self.timed_read()[1], 12)

    def test_a_writer_still_gives_up_visibly_within_its_bounded_window(self):
        blocker = self.hold_foreign_write_lock()
        started = time.monotonic()
        with self.assertRaises(sqlite3.OperationalError) as caught:
            with self.state.transaction(retry_seconds=0.5):
                self.state.execute("INSERT INTO t VALUES (7)")
        waited = time.monotonic() - started
        self.assertIn("locked", str(caught.exception))
        self.assertGreaterEqual(waited, 2.0)  # busy timeout (2 s) + retry window (0.5 s), as before
        self.assertLess(waited, 4.0)
        self.assertFalse(self.state.in_transaction)
        self.assertEqual(self.state.lock_waits["slow"], 1)
        self.assertEqual(self.state.lock_waits["last_slow"]["what"], "BEGIN_IMMEDIATE:GAVE_UP")
        blocker.execute("ROLLBACK")

    def test_an_autocommit_write_waits_out_a_short_foreign_hold_and_applies_once(self):
        blocker = self.hold_foreign_write_lock()
        threading.Timer(0.4, lambda: blocker.execute("ROLLBACK")).start()
        started = time.monotonic()
        self.state.execute("INSERT INTO t VALUES (42)")
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertEqual(self.timed_read()[1], 11)
        self.assertEqual(self.state.lock_waits["count"], 1)

    def test_a_query_only_reader_cannot_write(self):
        pool = self.state._read_pool
        self.assertIsNotNone(pool)
        with self.assertRaises(sqlite3.OperationalError):
            pool.execute("INSERT INTO t VALUES (1)", ())  # never routed there; the guard holds even if it were

    def test_a_locked_section_keeps_reading_on_the_shared_connection(self):
        # Repositories that read-then-write under the connection lock keep seeing their own uncommitted work.
        with self.state._lock, self.state.transaction():
            self.state.execute("INSERT INTO t VALUES (77)")
            self.assertTrue(self.state.execute("SELECT 1 FROM t WHERE x=77").fetchone())
        self.assertTrue(self.state.execute("SELECT 1 FROM t WHERE x=77").fetchone())


class LegacyBehaviourTests(ForeignWriteLockCase):
    """The rollback switch restores the old shared-lock path, and with it the audit's stall (R1)."""

    def open_state(self) -> LocalStateConnection:
        with mock.patch.dict(os.environ, {"IMP_STATE_LEGACY_SHARED_LOCK": "1"}):
            return super().open_state()

    def test_the_legacy_path_reproduces_the_stall(self):
        with mock.patch.dict(os.environ, {"IMP_STATE_LEGACY_SHARED_LOCK": "1"}):
            self.assertIsNone(self.state._read_pool)
            blocker = self.hold_foreign_write_lock()
            threads, outcomes = self.start_waiting_writers(1, retry_seconds=None)
            elapsed, _ = self.timed_read()
            [thread.join(10) for thread in threads]
            blocker.execute("ROLLBACK")
        self.assertGreater(elapsed, 1.0)  # the read queued behind the waiting write
        self.assertEqual(len(outcomes), 1)
        self.assertIn("locked", outcomes[0])


if __name__ == "__main__":
    unittest.main()
