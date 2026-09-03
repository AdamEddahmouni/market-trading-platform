"""Client-enforced IBKR request pacing and 429 penalty-box state."""

from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator, Mapping


Clock = Callable[[], float]
Sleeper = Callable[[float], None]
Journal = Callable[[Mapping[str, object]], None]


class TokenBucket:
    """Thread-safe token bucket used for the documented global request ceiling."""

    def __init__(
        self,
        *,
        rate_per_second: float,
        capacity: float,
        monotonic: Clock = time.monotonic,
        sleep: Sleeper = time.sleep,
    ) -> None:
        if rate_per_second <= 0 or capacity < 1:
            raise ValueError("token bucket rate and capacity must be positive")
        self._rate = rate_per_second
        self._capacity = capacity
        self._tokens = capacity
        self._monotonic = monotonic
        self._sleep = sleep
        self._updated_at = monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = self._monotonic()
                elapsed = max(0.0, now - self._updated_at)
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._updated_at = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                self._sleep((1.0 - self._tokens) / self._rate)


class HistoricalLimiter:
    """Enforce identical-query spacing and a conservative rolling window."""

    def __init__(
        self,
        *,
        min_spacing_seconds: float,
        window_max: int,
        window_seconds: float,
        monotonic: Clock = time.monotonic,
        sleep: Sleeper = time.sleep,
    ) -> None:
        if min_spacing_seconds < 0 or window_max < 1 or window_seconds <= 0:
            raise ValueError("invalid historical pacing configuration")
        self._min_spacing = min_spacing_seconds
        self._window_max = window_max
        self._window_seconds = window_seconds
        self._monotonic = monotonic
        self._sleep = sleep
        self._requests: deque[float] = deque()
        self._last_by_query: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, query_key: str) -> None:
        with self._lock:
            while True:
                now = self._monotonic()
                threshold = now - self._window_seconds
                while self._requests and self._requests[0] <= threshold:
                    self._requests.popleft()
                waits: list[float] = []
                last = self._last_by_query.get(query_key)
                if last is not None:
                    waits.append(last + self._min_spacing - now)
                if len(self._requests) >= self._window_max:
                    waits.append(self._requests[0] + self._window_seconds - now)
                wait_seconds = max((value for value in waits if value > 0), default=0.0)
                if wait_seconds <= 0:
                    self._requests.append(now)
                    self._last_by_query[query_key] = now
                    return
                self._sleep(wait_seconds)


class PenaltyBox:
    """Journal a 429 and block every later request for the configured duration."""

    def __init__(
        self,
        *,
        duration_seconds: float,
        journal: Journal,
        monotonic: Clock = time.monotonic,
        sleep: Sleeper = time.sleep,
    ) -> None:
        if duration_seconds < 900:
            raise ValueError("IBKR penalty box must be at least 900 seconds")
        self._duration = duration_seconds
        self._journal = journal
        self._monotonic = monotonic
        self._sleep = sleep
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def enter(self, *, status: int, method: str, path: str) -> None:
        now = self._monotonic()
        blocked_until = now + self._duration
        with self._lock:
            self._blocked_until = max(self._blocked_until, blocked_until)
            recorded_until = self._blocked_until
        self._journal(
            {
                "event": "IBKR_429_PENALTY_BOX_ENTERED",
                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": status,
                "method": method,
                "path": path,
                "observed_monotonic": now,
                "blocked_until_monotonic": recorded_until,
                "minimum_backoff_seconds": self._duration,
            }
        )

    def wait_if_active(self) -> None:
        while True:
            with self._lock:
                remaining = self._blocked_until - self._monotonic()
            if remaining <= 0:
                return
            self._sleep(remaining)


class RequestPacer:
    """Compose global, historical, single-flight, and penalty-box controls."""

    def __init__(
        self,
        *,
        requests_per_second: float,
        history_min_spacing_seconds: float,
        history_window_max: int,
        history_window_seconds: float,
        penalty_box_seconds: float,
        journal: Journal,
        monotonic: Clock = time.monotonic,
        sleep: Sleeper = time.sleep,
    ) -> None:
        self._global = TokenBucket(
            rate_per_second=requests_per_second,
            capacity=max(1.0, requests_per_second),
            monotonic=monotonic,
            sleep=sleep,
        )
        self._history = HistoricalLimiter(
            min_spacing_seconds=history_min_spacing_seconds,
            window_max=history_window_max,
            window_seconds=history_window_seconds,
            monotonic=monotonic,
            sleep=sleep,
        )
        self._penalty = PenaltyBox(
            duration_seconds=penalty_box_seconds,
            journal=journal,
            monotonic=monotonic,
            sleep=sleep,
        )
        self._history_singleflight = threading.Lock()

    @contextmanager
    def slot(self, path: str, query_key: str) -> Iterator[None]:
        history = path == "/hmds/history"
        if history:
            self._history_singleflight.acquire()
        try:
            self._penalty.wait_if_active()
            self._global.acquire()
            if history:
                self._history.acquire(query_key)
            yield
        finally:
            if history:
                self._history_singleflight.release()

    def penalize(self, *, status: int, method: str, path: str) -> None:
        self._penalty.enter(status=status, method=method, path=path)


__all__ = ["HistoricalLimiter", "PenaltyBox", "RequestPacer", "TokenBucket"]
