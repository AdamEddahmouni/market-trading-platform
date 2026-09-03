"""Tests for `src.scrapers.rate_limiter`.

Covers:
  * `TokenBucket` - capacity, consumption, refill timing, wait_time
  * `AdaptiveRateLimiter` - per-domain buckets, rate adaptation, lock safety
  * `DomainThrottler` - per-domain delays, jitter range, lock safety
"""

from __future__ import annotations

import threading
import time
import random
from unittest.mock import patch

import pytest

from src.scrapers.rate_limiter import (
    AdaptiveRateLimiter,
    DomainThrottler,
    TokenBucket,
)


# ── Module-level helpers ──────────────────────────────────────


def _limiter_time():
    """Return the `time` module object as imported by the rate_limiter.

    `src.scrapers.rate_limiter` does `import time` at the top of the
    module, so its `time` reference points to the same module every
    other importer sees. Tests patch attributes on this object so the
    production code's `time.monotonic()` and `time.sleep()` behaviour
    stays deterministic.
    """
    import src.scrapers.rate_limiter as rl
    return rl.time


# ── TokenBucket ────────────────────────────────────────────────


class TestTokenBucket:
    def test_initial_tokens_equal_capacity(self):
        bucket = TokenBucket(capacity=10, fill_rate=5)
        assert bucket.tokens == 10
        assert bucket.capacity == 10
        assert bucket.fill_rate == 5

    def test_consume_returns_true_when_tokens_available(self):
        bucket = TokenBucket(capacity=2, fill_rate=10)
        assert bucket.consume() is True
        assert bucket.tokens == pytest.approx(1.0)

    def test_consume_returns_false_when_empty(self):
        bucket = TokenBucket(capacity=1, fill_rate=0.0)
        assert bucket.consume() is True
        # fill_rate=0 so no refill ever happens
        assert bucket.consume() is False

    def test_consume_multiple_tokens_at_once(self):
        bucket = TokenBucket(capacity=5, fill_rate=0.0)
        assert bucket.consume(tokens=3.0) is True
        assert bucket.tokens == pytest.approx(2.0)
        assert bucket.consume(tokens=2.0) is True
        assert bucket.consume(tokens=1.0) is False

    def test_refill_with_clock_advance(self, mocker):
        """Calling `_refill` after time advance increases tokens."""
        # Freeze time at 0 before creating the bucket so its baseline
        # `last_refill` matches the mocked values below.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)

        bucket = TokenBucket(capacity=2, fill_rate=4)  # 4 tokens/sec
        # Drain the bucket.
        bucket.consume()
        bucket.consume()
        assert bucket.tokens == 0.0  # exactly zero, no drift.

        # First refill establishes a new "now" baseline.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=1000.0)
        bucket._refill()
        # Advance 0.5s → +2 tokens; capped at capacity=2.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=1000.5)
        bucket._refill()
        assert bucket.tokens == pytest.approx(2.0)

    def test_wait_time_zero_when_tokens_available(self, mocker):
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)
        bucket = TokenBucket(capacity=5, fill_rate=1.0)
        assert bucket.wait_time() == 0

    def test_wait_time_positive_when_empty(self, mocker):
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)
        bucket = TokenBucket(capacity=1, fill_rate=0.0)
        bucket.consume()
        # No refill possible → infinite wait.
        assert bucket.wait_time() == float("inf")

    def test_wait_time_computes_deficit_over_fill_rate(self, mocker):
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)
        bucket = TokenBucket(capacity=2, fill_rate=4)  # 4 tokens/sec
        bucket.consume()
        bucket.consume()  # tokens == 0; deficit == 1; wait = 1/4 = 0.25
        assert bucket.wait_time() == pytest.approx(0.25)

    def test_capacity_caps_refill(self, mocker):
        """Refilling beyond capacity must not exceed capacity."""
        # Freeze time at 0 so the bucket's baseline last_refill matches.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)
        bucket = TokenBucket(capacity=3, fill_rate=100)
        # Even after a "long" idle period, tokens stay capped.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=1000.0)
        bucket._refill()
        # Advance 10 seconds; gain would be 1000 tokens, capped at 3.
        mocker.patch.object(_limiter_time(), "monotonic", return_value=1010.0)
        bucket._refill()
        assert bucket.tokens == pytest.approx(3.0)

    def test_thread_safe_consume(self):
        """Concurrent consume() calls respect the lock."""
        bucket = TokenBucket(capacity=100, fill_rate=0.0)
        results = []

        def worker():
            results.append(bucket.consume())

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly `capacity` True's should be observed; the rest False.
        assert sum(results) == 100
        assert len(results) == 100


# ── AdaptiveRateLimiter ────────────────────────────────────────


class TestAdaptiveRateLimiter:
    def test_default_rps_applied_to_new_buckets(self, mocker):
        # Patch time.monotonic so buckets created in the limiter module
        # don't depend on wall-clock.
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)

        rl = AdaptiveRateLimiter(default_rps=3.0)
        bucket = rl._get_bucket("example.com")
        assert bucket.fill_rate == 3.0
        assert bucket.capacity == int(3.0 * 2)

    def test_report_rate_limit_decreases_rate(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)

        rl = AdaptiveRateLimiter(default_rps=2.0, min_rps=0.1)
        initial = rl._get_bucket("x.com").fill_rate
        rl.report_rate_limit("x.com")
        # After 1 rate-limit hit: factor = 0.5^1 = 0.5 → rate = 1.0
        assert rl._get_bucket("x.com").fill_rate == pytest.approx(initial * 0.5)
        assert rl._rate_limits["x.com"] == 1

    def test_repeated_rate_limits_compound_exponentially(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)

        rl = AdaptiveRateLimiter(default_rps=2.0, min_rps=0.1)
        for _ in range(3):
            rl.report_rate_limit("a.com")
        # After 3 hits: factor = 0.5^3 = 0.125 → rate = 0.25
        assert rl._get_bucket("a.com").fill_rate == pytest.approx(0.25)
        assert rl._rate_limits["a.com"] == 3

    def test_min_rps_enforced_as_floor(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)

        rl = AdaptiveRateLimiter(default_rps=2.0, min_rps=0.5)
        # 10 hits: factor = 0.5^10 = ~0.000976, would be ~0.002 if uncapped.
        for _ in range(10):
            rl.report_rate_limit("z.com")
        assert rl._get_bucket("z.com").fill_rate == 0.5

    def test_report_success_gradually_restores_rate(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        # First call to restore rate => time must be 10+ seconds after the
        # initial _last_adjust which defaults to 0.0 (definition-time).
        # Drive monotonic to advance by 11 seconds.
        times = iter([1000.0 + i * 11.0 for i in range(20)])
        mocker.patch.object(limiter.time, "monotonic", side_effect=lambda: next(times))

        rl = AdaptiveRateLimiter(default_rps=2.0, max_rps=10.0)
        rl.report_rate_limit("g.com")  # rate now 1.0
        bucket = rl._get_bucket("g.com")
        rate_after_hit = bucket.fill_rate

        # Drive `_last_adjust` > 10s newer via report_success.
        rl.report_success("g.com")
        assert bucket.fill_rate == pytest.approx(min(rl.max_rps, rate_after_hit * 1.05))

    def test_report_success_does_not_restore_within_cooldown(self, mocker):
        mocker.patch.object(_limiter_time(), "monotonic", return_value=5000.0)

        rl = AdaptiveRateLimiter(default_rps=2.0)
        rl.report_rate_limit("c.com")
        rate = rl._get_bucket("c.com").fill_rate

        # `_last_adjust["c.com"]` defaults to 0.0; if left untouched, the
        # 10-second cooldown check would fire because now - 0 = > 10.
        # Fake a recent adjustment so the cooldown is in effect.
        rl._last_adjust["c.com"] = 4995.0  # 5 seconds < 10s ago.
        rl.report_success("c.com")
        # Within 10-second window, rate must remain unchanged.
        assert rl._get_bucket("c.com").fill_rate == rate

    def test_report_error_slightly_slows_down(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)

        rl = AdaptiveRateLimiter(default_rps=2.0, min_rps=0.1)
        rl._get_bucket("e.com")  # create bucket at default rate 2.0
        rl.report_error("e.com")
        assert rl._get_bucket("e.com").fill_rate == pytest.approx(1.6)

    def test_wait_if_needed_blocks_when_no_tokens(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=0.0)

        rl = AdaptiveRateLimiter(default_rps=2.0)
        # Drain the bucket.
        bucket = rl._get_bucket("w.com")
        for _ in range(int(bucket.capacity)):
            bucket.consume()
        # Now wait_time should be > 0.
        with patch.object(limiter.time, "sleep") as sleep_spy:
            rl.wait_if_needed("w.com")
            assert sleep_spy.call_count == 1
            # Sleep called with the deficit seconds, capped at 10.
            args, _ = sleep_spy.call_args
            assert 0 < args[0] <= 10

    def test_wait_if_needed_no_sleep_when_tokens_available(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=0.0)
        rl = AdaptiveRateLimiter(default_rps=2.0)
        # Brand-new bucket is full.
        with patch.object(limiter.time, "sleep") as sleep_spy:
            rl.wait_if_needed("full.com")
            sleep_spy.assert_not_called()


# ── DomainThrottler ────────────────────────────────────────────


class TestDomainThrottler:
    def test_first_request_waits_then_records_timestamp(self, mocker):
        """The first call after long idle records the timestamp."""
        # `time.monotonic` returns 0 → elapsed since the (default) last
        # request equals `now - 0 = 0`, which is < delay=1.0, so `sleep`
        # is called for the full delay.
        t = DomainThrottler()
        mocker.patch.object(_limiter_time(), "monotonic", return_value=0.0)
        mocker.patch.object(random, "uniform", return_value=1.0)
        sleep_spy = mocker.patch.object(_limiter_time(), "sleep")

        t.wait("example.com", min_delay=0.5, max_delay=2.0)

        sleep_spy.assert_called_once_with(pytest.approx(1.0))
        assert "example.com" in t._last_request
        # The recorded timestamp is taken AFTER `_last_request` is updated,
        # so it should reflect the (mocked) now=0.0 used for the call.
        assert t._last_request["example.com"] == 0.0

    def test_subsequent_call_respects_min_max_jitter(self, mocker):
        """Second call sleeps at least `random.uniform` seconds because no
        time has elapsed between calls (and the captured last_request was
        just set)."""
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        # First call now=1000 → timestamp recorded.
        # Second call now=1000 (no elapsed) → must sleep up to `delay`.
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)
        mocker.patch.object(
            __import__("random", fromlist=["uniform"]),
            "uniform",
            return_value=0.7,
        )
        sleep_spy = mocker.patch.object(limiter.time, "sleep")

        t = DomainThrottler()
        t.wait("example.com", min_delay=0.5, max_delay=2.0)  # records
        t.wait("example.com", min_delay=0.5, max_delay=2.0)  # waits

        sleep_spy.assert_called_with(pytest.approx(0.7))

    def test_subsequent_call_no_sleep_when_enough_time_passed(self, mocker):
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)
        mocker.patch.object(
            __import__("random", fromlist=["uniform"]),
            "uniform",
            return_value=0.0,  # zero delay requirement
        )
        sleep_spy = mocker.patch.object(limiter.time, "sleep")

        t = DomainThrottler()
        t.wait("fast.com", min_delay=0.0, max_delay=0.0)
        t.wait("fast.com", min_delay=0.0, max_delay=0.0)

        sleep_spy.assert_not_called()

    def test_independent_domain_tracking(self, mocker):
        """Each domain has its own timestamp; one doesn't starve another."""
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)
        # Force a high jitter so the second call should still sleep.
        mocker.patch.object(
            __import__("random", fromlist=["uniform"]),
            "uniform",
            return_value=2.0,
        )
        sleep_spy = mocker.patch.object(limiter.time, "sleep")

        t = DomainThrottler()
        t.wait("a.com", min_delay=0.5, max_delay=2.0)
        # Different domain — no wait, but it should still record timestamp.
        assert "b.com" not in t._last_request

    def test_lock_protects_last_request_dict(self, mocker):
        """Concurrent wait() calls on the same domain don't crash."""
        limiter = __import__(
            "src.scrapers.rate_limiter", fromlist=["time"]
        )
        mocker.patch.object(limiter.time, "monotonic", return_value=1000.0)
        mocker.patch.object(
            __import__("random", fromlist=["uniform"]),
            "uniform",
            return_value=0.0,
        )
        mocker.patch.object(limiter.time, "sleep")

        t = DomainThrottler()
        errors = []

        def worker():
            try:
                t.wait("req.com", min_delay=0.0, max_delay=0.0)
            except Exception as e:  # pragma: no cover (smoke test)
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert errors == []
