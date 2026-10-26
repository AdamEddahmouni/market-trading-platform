"""Shared SQLite state: cursor isolation, thread-owned transactions and bounded lock retry.

The 2026-10-26 automation receipts showed ``database is locked`` and the cursor-lifecycle messages
``another row available`` / ``no more rows available`` at ``BEGIN IMMEDIATE``. The first is real cross-process
contention; the second is one shared connection stepped from two threads. These tests use temporary stores
only and never touch the deployed state database.
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from market_platform_foundation.local_state.connection import (
    LocalStateConnection, lock_contention_error, transient_storage_error,
)


class StateCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.state = LocalStateConnection(self.path)
        self.addCleanup(self.state.close)
        self.state.execute("CREATE TABLE t(x INTEGER NOT NULL)")
        self.state.executemany("INSERT INTO t VALUES (?)", [(index,) for index in range(100)])

    def count(self) -> int:
        return int(self.state.execute("SELECT COUNT(*) FROM t").fetchone()[0])


class CursorIsolationTests(StateCase):
    def test_each_cursor_keeps_its_own_rows_while_another_thread_writes(self):
        errors: list[str] = []
        barrier = threading.Barrier(6)

        def reader(offset: int) -> None:
            barrier.wait(5)
            for _ in range(80):
                try:
                    first = self.state.execute("SELECT x FROM t WHERE x>=? ORDER BY x LIMIT 1", (offset,)).fetchone()
                    if first is None or int(first[0]) < offset:
                        errors.append(f"reader {offset} saw {first}")
                    rows = self.state.execute("SELECT x FROM t ORDER BY x").fetchall()
                    if [int(row[0]) for row in rows] != sorted(int(row[0]) for row in rows):
                        errors.append(f"reader {offset} saw an unordered page")
                except Exception as exc:  # noqa: BLE001 - the test reports the exact failure
                    errors.append(f"reader {offset}: {type(exc).__name__}: {exc}")

        def writer(start: int) -> None:
            barrier.wait(5)
            for index in range(80):
                try:
                    self.state.execute("INSERT INTO t VALUES (?)", (start + index,))
                    with self.state.transaction(retry_seconds=2):
                        self.state.execute("INSERT INTO t VALUES (?)", (start + 10_000 + index,))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"writer {start}: {type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=reader, args=(offset,)) for offset in (0, 25, 50, 75)]
        threads += [threading.Thread(target=writer, args=(1_000,)), threading.Thread(target=writer, args=(2_000,))]
        [thread.start() for thread in threads]
        [thread.join(30) for thread in threads]
        self.assertEqual(errors, [])
        self.assertEqual(self.count(), 100 + 2 * 80 * 2)

    def test_a_materialized_cursor_is_not_advanced_by_a_later_statement(self):
        cursor = self.state.execute("SELECT x FROM t ORDER BY x")
        self.state.execute("INSERT INTO t VALUES (999)")
        self.assertEqual([int(row[0]) for row in cursor.fetchall()], list(range(100)))
        self.assertEqual(cursor.fetchone(), None)


class TransactionOwnershipTests(StateCase):
    def test_a_transaction_belongs_to_the_thread_that_opened_it(self):
        entered, release = threading.Event(), threading.Event()

        def holder() -> None:
            with self.state.transaction(retry_seconds=2):
                entered.set()
                release.wait(5)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(5))
        # The old connection-wide flag said True here even though this thread owns nothing.
        self.assertFalse(self.state.in_transaction)
        release.set()
        thread.join(5)
        self.assertFalse(self.state.in_transaction)

    def test_a_second_thread_waits_for_the_owner_then_commits_its_own_write(self):
        entered, release = threading.Event(), threading.Event()

        def holder() -> None:
            with self.state.transaction(retry_seconds=2):
                self.state.execute("INSERT INTO t VALUES (1000)")
                entered.set()
                release.wait(5)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(5))
        threading.Timer(0.2, release.set).start()
        with self.state.transaction(retry_seconds=3):
            self.state.execute("INSERT INTO t VALUES (1001)")
        thread.join(5)
        self.assertEqual(self.count(), 102)
        self.assertTrue(self.state.execute("SELECT 1 FROM t WHERE x=1001").fetchone())

    def test_nested_transactions_are_one_atomic_commit(self):
        with self.state.transaction(retry_seconds=2):
            self.state.execute("INSERT INTO t VALUES (1000)")
            with self.state.transaction(retry_seconds=2):
                self.state.execute("INSERT INTO t VALUES (1001)")
        self.assertEqual(self.count(), 102)

    def test_a_raised_body_rolls_back_every_statement(self):
        with self.assertRaises(RuntimeError):
            with self.state.transaction(retry_seconds=2):
                self.state.execute("INSERT INTO t VALUES (1000)")
                self.state.execute("INSERT INTO t VALUES (1001)")
                raise RuntimeError("fixture")
        self.assertEqual(self.count(), 100)
        self.assertFalse(self.state.in_transaction)


class ContentionTests(StateCase):
    def test_a_held_write_lock_is_waited_out_within_the_bounded_window(self):
        blocker = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        self.state.execute("PRAGMA busy_timeout=50")  # force the explicit retry, not only SQLite's busy handler
        released = threading.Event()

        def release() -> None:
            time.sleep(0.2)
            blocker.execute("ROLLBACK")
            blocker.close()
            released.set()

        threading.Thread(target=release).start()
        started = time.monotonic()
        with self.state.transaction(retry_seconds=3):
            self.state.execute("INSERT INTO t VALUES (1000)")
        elapsed = time.monotonic() - started
        self.assertTrue(released.wait(5))
        self.assertGreaterEqual(elapsed, 0.1)
        self.assertLess(elapsed, 3)
        self.assertEqual(self.count(), 101)

    def test_a_programming_error_is_raised_at_once_and_rolled_back(self):
        started = time.monotonic()
        with self.assertRaises(sqlite3.OperationalError):
            with self.state.transaction(retry_seconds=5):
                self.state.execute("INSERT INTO missing_table VALUES (1)")
        self.assertLess(time.monotonic() - started, 1)
        self.assertFalse(self.state.in_transaction)

    def test_cursor_lifecycle_messages_are_not_misread_as_lock_contention(self):
        for message in ("another row available", "no more rows available"):
            error = sqlite3.OperationalError(message)
            self.assertFalse(lock_contention_error(error), message)
            self.assertFalse(transient_storage_error(error), message)
        self.assertTrue(lock_contention_error(sqlite3.OperationalError("database is locked")))
        self.assertTrue(transient_storage_error(sqlite3.OperationalError("database is locked")))


if __name__ == "__main__":
    unittest.main()
