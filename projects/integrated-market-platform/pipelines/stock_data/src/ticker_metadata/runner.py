from __future__ import annotations

from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from queue import Queue
import threading
import time
from typing import Callable
from uuid import uuid4

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.contract import (
    ALLOWLIST,
    REQUEST_CONTRACT_JSON,
    REQUEST_CONTRACT_SHA256,
    REQUEST_CONTRACT_VERSION,
)
from src.ticker_metadata.models import (
    AttemptRecord,
    CollectorProvenance,
    ObservationRecord,
    RunReport,
    Selection,
    TickerRef,
    WriteReceipt,
)


_RETRYABLE = {AcquisitionOutcome.TRANSIENT, AcquisitionOutcome.THROTTLED}


class StartRateLimiter:
    def __init__(
        self,
        rate_per_second: float = 2.0,
        burst_capacity: int = 1,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if rate_per_second <= 0 or burst_capacity < 1:
            raise ValueError("rate and burst capacity must be positive")
        self._rate = float(rate_per_second)
        self._capacity = float(burst_capacity)
        self._tokens = float(burst_capacity)
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_refill = monotonic()
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = self._monotonic()
                elapsed = max(0.0, now - self._last_refill)
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._rate
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                delay = (1.0 - self._tokens) / self._rate
            self._sleep(delay)


@dataclass(frozen=True)
class _TickerResult:
    final_outcome: AcquisitionOutcome
    attempts: tuple[tuple[AcquisitionOutcome, WriteReceipt], ...]
    observed_fields: tuple[tuple[str, ...], ...]
    observation_times: tuple[object, ...]


class _SerializedWriter:
    def __init__(self, store):
        self._store = store
        self._queue: Queue[object] = Queue()
        self._thread = threading.Thread(
            target=self._run,
            name="ticker-metadata-writer",
            daemon=True,
        )
        self._thread.start()

    def write(
        self, attempt: AttemptRecord, observation: ObservationRecord | None
    ) -> WriteReceipt:
        future: Future[WriteReceipt] = Future()
        self._queue.put((attempt, observation, future))
        return future.result()

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                attempt, observation, future = item
                try:
                    receipt = self._store.record_attempt(attempt, observation)
                except BaseException as exc:
                    future.set_exception(exc)
                else:
                    future.set_result(receipt)
            finally:
                self._queue.task_done()


class MetadataRunner:
    def __init__(
        self,
        store,
        adapter,
        provenance: CollectorProvenance,
        *,
        limiter=None,
        sleep: Callable[[float], None] = time.sleep,
        workers: int = 4,
    ):
        if workers < 1 or workers > 4:
            raise ValueError("metadata workers must be between one and four")
        self._store = store
        self._adapter = adapter
        self._provenance = provenance
        self._limiter = limiter or StartRateLimiter()
        self._sleep = sleep
        self._workers = workers

    def run(self, selection: Selection) -> RunReport:
        run_id = str(uuid4())
        writer = _SerializedWriter(self._store)
        completed_results: list[_TickerResult] = []
        circuit_reason: str | None = None
        schema_drift_streak = 0
        throttled_streak = 0
        ticker_iterator = iter(selection.tickers)
        next_submission_sequence = 0
        next_processing_sequence = 0
        completed_by_sequence: dict[int, _TickerResult] = {}

        def submit_next(executor, futures) -> bool:
            nonlocal next_submission_sequence
            try:
                ticker = next(ticker_iterator)
            except StopIteration:
                return False
            future = executor.submit(self._run_ticker, ticker, run_id, writer)
            futures[future] = next_submission_sequence
            next_submission_sequence += 1
            return True

        try:
            with ThreadPoolExecutor(
                max_workers=self._workers,
                thread_name_prefix="ticker-metadata-provider",
            ) as executor:
                futures: dict[Future[_TickerResult], int] = {}
                for _ in range(self._workers):
                    if not submit_next(executor, futures):
                        break
                while futures:
                    done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
                    for future in done:
                        sequence = futures.pop(future)
                        completed_by_sequence[sequence] = future.result()
                    while next_processing_sequence in completed_by_sequence:
                        result = completed_by_sequence.pop(next_processing_sequence)
                        next_processing_sequence += 1
                        completed_results.append(result)
                        if circuit_reason is not None:
                            continue
                        if result.final_outcome is AcquisitionOutcome.SCHEMA_DRIFT:
                            schema_drift_streak += 1
                        else:
                            schema_drift_streak = 0
                        if result.final_outcome is AcquisitionOutcome.THROTTLED:
                            throttled_streak += 1
                        else:
                            throttled_streak = 0
                        if schema_drift_streak >= 3:
                            circuit_reason = "consecutive_schema_drift"
                        elif throttled_streak >= 5:
                            circuit_reason = "consecutive_throttled"
                    while (
                        circuit_reason is None
                        and len(futures) + len(completed_by_sequence) < self._workers
                        and submit_next(executor, futures)
                    ):
                        pass
        finally:
            writer.close()

        outcomes: Counter[str] = Counter()
        fields: Counter[str] = Counter()
        observation_times = []
        calls = 0
        observations = 0
        retries = 0
        for result in completed_results:
            calls += len(result.attempts)
            retries += max(0, len(result.attempts) - 1)
            for outcome, receipt in result.attempts:
                outcomes[outcome.value] += 1
                if receipt.observation_id is not None:
                    observations += 1
            for present in result.observed_fields:
                fields.update(present)
            observation_times.extend(result.observation_times)
        return RunReport(
            run_id=run_id,
            selected_tickers=len(selection.tickers),
            skipped_tickers=selection.skipped_terminal,
            calls=calls,
            retries=retries,
            committed_attempts=calls,
            committed_observations=observations,
            outcome_counts=dict(sorted(outcomes.items())),
            field_presence_counts=dict(sorted(fields.items())),
            earliest_observation_at_utc=(min(observation_times) if observation_times else None),
            latest_observation_at_utc=(max(observation_times) if observation_times else None),
            circuit_reason=circuit_reason,
            exit_code=20 if circuit_reason else 0,
        )

    def _run_ticker(
        self,
        ticker: TickerRef,
        run_id: str,
        writer: _SerializedWriter,
    ) -> _TickerResult:
        attempts: list[tuple[AcquisitionOutcome, WriteReceipt]] = []
        observed_fields: list[tuple[str, ...]] = []
        observation_times = []
        final_outcome = AcquisitionOutcome.TRANSIENT
        for ordinal in range(1, 4):
            self._limiter.wait()
            provider_result = self._adapter.call(ticker.requested_symbol, ordinal)
            classified = provider_result.classified
            attempt = AttemptRecord(
                run_id=run_id,
                raw_ticker_id=ticker.raw_ticker_id,
                requested_symbol=ticker.requested_symbol,
                provider="yfinance",
                method="get_info",
                request_contract_json=REQUEST_CONTRACT_JSON,
                request_contract_version=REQUEST_CONTRACT_VERSION,
                request_contract_sha256=REQUEST_CONTRACT_SHA256,
                retry_ordinal=ordinal,
                started_at_utc=provider_result.started_at_utc,
                completed_at_utc=provider_result.completed_at_utc,
                requested_fields=ALLOWLIST,
                observed_fields=classified.observed_provider_fields,
                outcome=classified.outcome,
                reason_code=classified.reason_code,
                detail=classified.detail,
                collector_git_revision=self._provenance.collector_git_revision,
                collector_dirty=self._provenance.collector_dirty,
                python_version=self._provenance.python_version,
                provider_library_name=self._provenance.provider_library_name,
                provider_library_version=self._provenance.provider_library_version,
            )
            observation = None
            if classified.outcome in {
                AcquisitionOutcome.COMPLETE,
                AcquisitionOutcome.PARTIAL_RESPONSE,
            }:
                observation = ObservationRecord(
                    run_id=run_id,
                    raw_ticker_id=ticker.raw_ticker_id,
                    requested_symbol=ticker.requested_symbol,
                    provider="yfinance",
                    method="get_info",
                    request_contract_json=REQUEST_CONTRACT_JSON,
                    request_contract_version=REQUEST_CONTRACT_VERSION,
                    request_contract_sha256=REQUEST_CONTRACT_SHA256,
                    provider_observed_at_utc=provider_result.completed_at_utc,
                    projected=classified.projected,
                    present_fields=classified.observed_fields,
                    collector_git_revision=self._provenance.collector_git_revision,
                    collector_dirty=self._provenance.collector_dirty,
                    python_version=self._provenance.python_version,
                    provider_library_name=self._provenance.provider_library_name,
                    provider_library_version=self._provenance.provider_library_version,
                )
            receipt = writer.write(attempt, observation)
            attempts.append((classified.outcome, receipt))
            if observation is not None:
                observed_fields.append(classified.observed_fields)
                observation_times.append(provider_result.completed_at_utc)
            final_outcome = classified.outcome
            if classified.outcome not in _RETRYABLE or ordinal == 3:
                break
            self._sleep(float(2**ordinal))
        return _TickerResult(
            final_outcome=final_outcome,
            attempts=tuple(attempts),
            observed_fields=tuple(observed_fields),
            observation_times=tuple(observation_times),
        )
