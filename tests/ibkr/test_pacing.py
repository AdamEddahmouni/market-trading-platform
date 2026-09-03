from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from tools.ibkr.client import IbkrClient, RateLimitError, TransportResponse
from tools.ibkr.config import IbkrConfig
from tools.ibkr.pacing import HistoricalLimiter, PenaltyBox, RequestPacer, TokenBucket


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TokenBucketTests(unittest.TestCase):
    def test_capacity_burst_then_refills_at_configured_rate(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(
            rate_per_second=2.0,
            capacity=2.0,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        bucket.acquire()
        bucket.acquire()
        self.assertEqual(clock.sleeps, [])
        bucket.acquire()
        self.assertEqual(clock.sleeps, [0.5])


class HistoricalLimiterTests(unittest.TestCase):
    def test_identical_query_is_spaced_by_at_least_fifteen_seconds(self) -> None:
        clock = FakeClock()
        limiter = HistoricalLimiter(
            min_spacing_seconds=15,
            window_max=50,
            window_seconds=600,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        limiter.acquire("conid=265598&period=1d&bar=1min")
        limiter.acquire("conid=265598&period=1d&bar=1min")
        self.assertEqual(clock.sleeps, [15.0])

    def test_rolling_window_waits_until_oldest_request_expires(self) -> None:
        clock = FakeClock()
        limiter = HistoricalLimiter(
            min_spacing_seconds=15,
            window_max=2,
            window_seconds=600,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        limiter.acquire("query-a")
        limiter.acquire("query-b")
        limiter.acquire("query-c")
        self.assertEqual(clock.sleeps, [600.0])


class RequestPacerTests(unittest.TestCase):
    def test_history_slot_is_single_flight_for_entire_request(self) -> None:
        entered_first = threading.Event()
        release_first = threading.Event()
        entered_second = threading.Event()
        pacer = RequestPacer(
            requests_per_second=10,
            history_min_spacing_seconds=15,
            history_window_max=50,
            history_window_seconds=600,
            penalty_box_seconds=900,
            journal=lambda record: None,
        )

        def first() -> None:
            with pacer.slot("/hmds/history", "query-a"):
                entered_first.set()
                release_first.wait(timeout=2)

        def second() -> None:
            entered_first.wait(timeout=2)
            with pacer.slot("/hmds/history", "query-b"):
                entered_second.set()

        first_thread = threading.Thread(target=first)
        second_thread = threading.Thread(target=second)
        first_thread.start()
        second_thread.start()
        self.assertTrue(entered_first.wait(timeout=1))
        self.assertFalse(entered_second.wait(timeout=0.05))
        release_first.set()
        first_thread.join(timeout=1)
        second_thread.join(timeout=1)
        self.assertTrue(entered_second.is_set())

    def test_penalty_is_journaled_before_subsequent_traffic_backs_off(self) -> None:
        clock = FakeClock(now=100.0)
        journal: list[dict[str, object]] = []
        box = PenaltyBox(
            duration_seconds=900,
            journal=journal.append,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        box.enter(status=429, method="GET", path="/iserver/auth/status")
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(journal[0]["event"], "IBKR_429_PENALTY_BOX_ENTERED")
        self.assertEqual(journal[0]["blocked_until_monotonic"], 1000.0)
        self.assertRegex(str(journal[0]["observed_at"]), r"^\d{4}-\d{2}-\d{2}T.*Z$")
        box.wait_if_active()
        self.assertEqual(clock.sleeps, [900.0])

    def test_client_does_not_retry_429_and_next_request_waits_full_penalty(self) -> None:
        clock = FakeClock()
        journal: list[dict[str, object]] = []
        responses = [
            TransportResponse(429, {"retry-after": "900"}, b'{"error":"rate limit"}'),
            TransportResponse(200, {}, b'{"authenticated":true}'),
        ]
        calls: list[str] = []

        def transport(request, *, ssl_context, timeout: float) -> TransportResponse:
            calls.append(request.full_url)
            return responses.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            config = IbkrConfig.from_env({"IMP_IBKR_LIVE": "1"}, root=Path(tmp))
            pacer = RequestPacer(
                requests_per_second=10,
                history_min_spacing_seconds=15,
                history_window_max=50,
                history_window_seconds=600,
                penalty_box_seconds=900,
                journal=journal.append,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            )
            client = IbkrClient(config, transport=transport, pacer=pacer)
            with self.assertRaises(RateLimitError):
                client.request_json("GET", "/iserver/auth/status")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(journal), 1)
            result = client.request_json("GET", "/iserver/auth/status")
        self.assertEqual(result, {"authenticated": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(clock.sleeps, [900.0])


if __name__ == "__main__":
    unittest.main()
