from collections import Counter, defaultdict
from datetime import datetime, timezone
from threading import Lock
import time

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.models import (
    ClassifiedResult,
    CollectorProvenance,
    ProviderCallResult,
    Selection,
    TickerRef,
    WriteReceipt,
)
from src.ticker_metadata.runner import MetadataRunner, StartRateLimiter


NOW = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
PROVENANCE = CollectorProvenance("abc", False, "3.11.15", "yfinance", "1.6.0")


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class NoopLimiter:
    def wait(self):
        return None


class FakeStore:
    def __init__(self, write_delay=0.0):
        self.records = []
        self._lock = Lock()
        self._active_writes = 0
        self.max_active_writes = 0
        self.write_delay = write_delay

    def record_attempt(self, attempt, observation):
        with self._lock:
            self._active_writes += 1
            self.max_active_writes = max(self.max_active_writes, self._active_writes)
        try:
            if self.write_delay:
                time.sleep(self.write_delay)
            self.records.append((attempt, observation))
            attempt_id = len(self.records)
            return WriteReceipt(attempt_id, attempt_id if observation else None)
        finally:
            with self._lock:
                self._active_writes -= 1


def call_result(ordinal, outcome, fields=()):
    projected = {field: f"value-{field}" for field in fields}
    if "market_cap" in projected:
        projected["market_cap"] = 1
    return ProviderCallResult(
        ordinal=ordinal,
        started_at_utc=NOW,
        completed_at_utc=NOW,
        classified=ClassifiedResult(
            outcome,
            f"reason_{outcome.value}",
            projected=projected,
            observed_fields=tuple(sorted(fields)),
        ),
    )


def selection(count):
    return Selection(
        tickers=tuple(TickerRef(index, f"T{index}") for index in range(1, count + 1)),
        skipped_terminal=2,
        filter_description="(test filter)",
    )


def test_start_limiter_allows_burst_one_and_two_starts_per_second():
    clock = FakeClock()
    limiter = StartRateLimiter(
        rate_per_second=2.0,
        burst_capacity=1,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.wait()
    limiter.wait()
    limiter.wait()

    assert clock.sleeps == [0.5, 0.5]


def test_transient_and_throttled_retry_with_exact_delays_and_terminal_does_not():
    outcomes = {
        "T1": [AcquisitionOutcome.TRANSIENT, AcquisitionOutcome.THROTTLED, AcquisitionOutcome.COMPLETE],
        "T2": [AcquisitionOutcome.PARTIAL_RESPONSE],
    }
    ordinals = defaultdict(list)

    class Adapter:
        def call(self, symbol, ordinal):
            ordinals[symbol].append(ordinal)
            return call_result(ordinal, outcomes[symbol].pop(0), ("provider_symbol", "short_name"))

    sleeps = []
    store = FakeStore()
    report = MetadataRunner(
        store,
        Adapter(),
        PROVENANCE,
        limiter=NoopLimiter(),
        sleep=sleeps.append,
        workers=1,
    ).run(selection(2))

    assert ordinals == {"T1": [1, 2, 3], "T2": [1]}
    assert sleeps == [2.0, 4.0]
    assert report.calls == 4
    assert report.retries == 2
    assert report.committed_attempts == 4
    assert report.committed_observations == 2
    assert report.outcome_counts == {
        "complete": 1,
        "partial_response": 1,
        "throttled": 1,
        "transient": 1,
    }


def test_four_worker_bound_and_dedicated_writer_serialization():
    active = 0
    maximum = 0
    lock = Lock()

    class Adapter:
        def call(self, symbol, ordinal):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                time.sleep(0.03)
                return call_result(ordinal, AcquisitionOutcome.NO_DATA)
            finally:
                with lock:
                    active -= 1

    store = FakeStore(write_delay=0.005)
    MetadataRunner(
        store,
        Adapter(),
        PROVENANCE,
        limiter=NoopLimiter(),
        sleep=lambda seconds: None,
        workers=4,
    ).run(selection(12))

    assert 2 <= maximum <= 4
    assert store.max_active_writes == 1


def test_three_consecutive_schema_drift_outcomes_trip_circuit_and_stop_scheduling():
    calls = []

    class Adapter:
        def call(self, symbol, ordinal):
            calls.append(symbol)
            return call_result(ordinal, AcquisitionOutcome.SCHEMA_DRIFT)

    report = MetadataRunner(
        FakeStore(), Adapter(), PROVENANCE, limiter=NoopLimiter(), workers=1
    ).run(selection(8))

    assert calls == ["T1", "T2", "T3"]
    assert report.circuit_reason == "consecutive_schema_drift"
    assert report.exit_code != 0
    assert report.selected_tickers == 8


def test_five_final_throttled_outcomes_trip_after_bounded_retries():
    calls = Counter()

    class Adapter:
        def call(self, symbol, ordinal):
            calls[symbol] += 1
            return call_result(ordinal, AcquisitionOutcome.THROTTLED)

    report = MetadataRunner(
        FakeStore(),
        Adapter(),
        PROVENANCE,
        limiter=NoopLimiter(),
        sleep=lambda seconds: None,
        workers=1,
    ).run(selection(9))

    assert calls == Counter({f"T{index}": 3 for index in range(1, 6)})
    assert report.circuit_reason == "consecutive_throttled"
    assert report.calls == 15


def test_intervening_outcomes_reset_only_matching_circuit_counter():
    finals = iter(
        [
            AcquisitionOutcome.SCHEMA_DRIFT,
            AcquisitionOutcome.SCHEMA_DRIFT,
            AcquisitionOutcome.NO_DATA,
            AcquisitionOutcome.SCHEMA_DRIFT,
            AcquisitionOutcome.SCHEMA_DRIFT,
            AcquisitionOutcome.SCHEMA_DRIFT,
        ]
    )

    class Adapter:
        def call(self, symbol, ordinal):
            return call_result(ordinal, next(finals))

    report = MetadataRunner(
        FakeStore(), Adapter(), PROVENANCE, limiter=NoopLimiter(), workers=1
    ).run(selection(8))
    assert report.calls == 6
    assert report.circuit_reason == "consecutive_schema_drift"
