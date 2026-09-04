"""Thread-safe bounded ingest queue with explicit backpressure metrics."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from ..rt01.clock import monotonic_process_ns
from ..rt01.context import TraceContext, bind_context, current_context, reset_context
from ..rt01.enums import TraceStage
from ..rt01.tracer import get_tracer

T = TypeVar("T")


@dataclass
class BoundedIngestQueue(Generic[T]):
    max_size: int = 10_000
    _queue: deque[tuple[T, int, TraceContext | None]] = field(
        default_factory=deque,
        init=False,
    )
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _not_empty: threading.Condition = field(init=False)
    events_enqueued: int = 0
    events_processed: int = 0
    events_dropped: int = 0
    queue_overflows: int = 0
    max_depth_observed: int = 0

    def __post_init__(self) -> None:
        self._not_empty = threading.Condition(self._lock)

    def enqueue(self, item: T) -> bool:
        with self._lock:
            if len(self._queue) >= self.max_size:
                self.events_dropped += 1
                self.queue_overflows += 1
                return False
            self._queue.append((item, monotonic_process_ns(), current_context()))
            self.events_enqueued += 1
            depth = len(self._queue)
            if depth > self.max_depth_observed:
                self.max_depth_observed = depth
            self._not_empty.notify()
            return True

    def dequeue_batch(self, limit: int = 64, *, timeout: float = 0.25) -> list[T]:
        return [item for item, _context in self.dequeue_batch_with_context(limit=limit, timeout=timeout)]

    def dequeue_batch_with_context(
        self,
        limit: int = 64,
        *,
        timeout: float = 0.25,
    ) -> list[tuple[T, TraceContext | None]]:
        with self._not_empty:
            if not self._queue:
                self._not_empty.wait(timeout=timeout)
            if not self._queue:
                return []
            batch: list[tuple[T, TraceContext | None]] = []
            while self._queue and len(batch) < limit:
                item, enqueue_mono_ns, context = self._queue.popleft()
                batch.append((item, context))
                if context is not None:
                    span = get_tracer().start_span(
                        TraceStage.QUEUE,
                        "ingest_queue_wait",
                        parent=context,
                        queue_enqueue_mono_ns=enqueue_mono_ns,
                        queue_dequeue_mono_ns=monotonic_process_ns(),
                        bind=False,
                    )
                    if span is not None:
                        span.end(output_ref="dequeued")
            self.events_processed += len(batch)
            return batch

    def depth(self) -> int:
        with self._lock:
            return len(self._queue)

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "events_dropped": self.events_dropped,
                "events_enqueued": self.events_enqueued,
                "events_processed": self.events_processed,
                "max_depth_observed": self.max_depth_observed,
                "queue_depth": len(self._queue),
                "queue_overflows": self.queue_overflows,
            }


def drain_queue_worker(
    queue: BoundedIngestQueue[dict[str, Any]],
    *,
    stop_event: threading.Event,
    handler: Callable[[dict[str, Any]], None],
    batch_size: int = 64,
) -> None:
    while not stop_event.is_set():
        batch = queue.dequeue_batch_with_context(limit=batch_size, timeout=0.25)
        for item, context in batch:
            token = bind_context(context) if context is not None else None
            try:
                handler(item)
            except Exception:
                continue
            finally:
                if token is not None:
                    reset_context(token)
