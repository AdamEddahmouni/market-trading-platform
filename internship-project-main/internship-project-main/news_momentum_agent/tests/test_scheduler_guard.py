"""Unit tests for scheduler job timeout / overlap guard."""

from __future__ import annotations

import threading
import time
import unittest

from agent.scheduler_guard import run_with_timeout, wrap_scheduled_job


class SchedulerGuardTests(unittest.TestCase):
    def test_blocking_timeout_returns_without_blocking_forever(self) -> None:
        def slow() -> str:
            time.sleep(5)
            return "done"

        started = time.monotonic()
        result = run_with_timeout(slow, name="test_timeout", timeout_sec=0.3)
        elapsed = time.monotonic() - started
        self.assertIsNone(result)
        self.assertLess(elapsed, 2.0)

    def test_fire_and_forget_does_not_block_schedule_thread(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocker() -> None:
            entered.set()
            release.wait(timeout=5)

        wrapped = wrap_scheduled_job(blocker, name="test_async", timeout_sec=10)
        started = time.monotonic()
        wrapped()
        # Schedule thread must return immediately (fire-and-forget).
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(entered.wait(timeout=2))
        # Overlap skip while first still running.
        self.assertIsNone(wrapped())
        release.set()

    def test_skip_overlapping(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocker() -> str:
            entered.set()
            release.wait(timeout=5)
            return "ok"

        wrapped = wrap_scheduled_job(blocker, name="test_overlap", timeout_sec=10)
        wrapped()
        self.assertTrue(entered.wait(timeout=2))
        self.assertIsNone(wrapped())
        release.set()


if __name__ == "__main__":
    unittest.main()
