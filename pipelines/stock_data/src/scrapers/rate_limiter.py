"""
Intelligent Rate Limiter - Per-domain rate limiting with token bucket algorithm,
adaptive delays, and automatic backoff on rate-limit detection.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta


class TokenBucket:
    """
    Token bucket rate limiter.
    Allows bursts up to capacity, then throttles to fill_rate tokens/sec.
    """

    def __init__(self, capacity: int, fill_rate: float):
        self.capacity = float(capacity)
        self.fill_rate = fill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens. Returns True if allowed, False if rate limited.
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self) -> float:
        """
        Calculate how long until we can consume 1 token.
        """
        with self.lock:
            self._refill()
            if self.tokens >= 1:
                return 0
            deficit = 1 - self.tokens
            return deficit / self.fill_rate if self.fill_rate > 0 else float('inf')


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts speed based on server responses.
    Detects rate limiting (429) and slows down automatically.
    """

    def __init__(self, default_rps: float = 2.0, max_rps: float = 10.0, min_rps: float = 0.1):
        self.default_rps = default_rps
        self.max_rps = max_rps
        self.min_rps = min_rps
        self._buckets: Dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=int(default_rps * 2), fill_rate=default_rps)
        )
        self._rate_limits: Dict[str, int] = defaultdict(int)  # domain -> count of 429s
        self._last_adjust: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def _get_bucket(self, domain: str) -> TokenBucket:
        """Get or create a token bucket for a domain."""
        return self._buckets[domain]

    def wait_if_needed(self, domain: str):
        """
        Block until a request to the domain is allowed.
        """
        bucket = self._get_bucket(domain)
        wait = bucket.wait_time()
        if wait > 0:
            time.sleep(min(wait, 10))  # Cap max wait at 10 seconds

    def report_success(self, domain: str):
        """
        Report a successful request - may increase rate slightly.
        """
        with self._lock:
            self._rate_limits[domain] = max(0, self._rate_limits[domain] - 1)

            # Gradually increase rate back toward default
            now = time.monotonic()
            if now - self._last_adjust[domain] > 10:
                bucket = self._get_bucket(domain)
                current_rate = bucket.fill_rate
                new_rate = min(self.max_rps, current_rate * 1.05)
                bucket.fill_rate = new_rate
                bucket.capacity = int(new_rate * 2)
                self._last_adjust[domain] = now

    def report_rate_limit(self, domain: str):
        """
        Report a rate limit hit - drastically reduces rate.
        """
        with self._lock:
            self._rate_limits[domain] += 1
            bucket = self._get_bucket(domain)

            # Exponential decrease on repeated rate limits
            factor = 0.5 ** self._rate_limits[domain]
            new_rate = max(self.min_rps, self.default_rps * factor)
            bucket.fill_rate = new_rate
            bucket.capacity = int(new_rate * 2)

            print(f"  [RATE] Rate limited on {domain}, reducing to {new_rate:.2f} req/s "
                  f"(hit #{self._rate_limits[domain]})")

    def report_error(self, domain: str):
        """
        Report a non-rate-limit error - slight slowdown.
        """
        with self._lock:
            bucket = self._get_bucket(domain)
            bucket.fill_rate = max(self.min_rps, bucket.fill_rate * 0.8)


class DomainThrottler:
    """
    Simple domain-based throttler with min/max delays and jitter.
    Good for scraping multiple domains at different rates.
    """

    def __init__(self):
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, domain: str, min_delay: float = 0.5, max_delay: float = 2.0):
        """
        Wait an appropriate amount of time before sending the next request
        to a domain. Adds random jitter within [min_delay, max_delay].
        """
        import random
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0.0)
            elapsed = now - last

            delay = random.uniform(min_delay, max_delay)

            if elapsed < delay:
                time.sleep(delay - elapsed)

            self._last_request[domain] = time.monotonic()
