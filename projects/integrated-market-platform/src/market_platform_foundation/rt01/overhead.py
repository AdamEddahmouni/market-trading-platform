"""RT-01 tracing overhead measurement."""

from __future__ import annotations

import time
from typing import Any, Callable


def measure_overhead(
    workload_fn: Callable[[], Any],
    *,
    iterations: int = 10,
    warmup: int = 2,
) -> dict[str, Any]:
    from .enums import SamplingMode
    from .tracer import Tracer, configure_tracer

    for _ in range(warmup):
        configure_tracer(Tracer(mode=SamplingMode.OFF))
        workload_fn()
    off_start = time.perf_counter_ns()
    off_tracer = Tracer(mode=SamplingMode.OFF)
    configure_tracer(off_tracer)
    for _ in range(iterations):
        workload_fn()
    off_elapsed = time.perf_counter_ns() - off_start
    off_spans = off_tracer.collector.counts.written

    for _ in range(warmup):
        configure_tracer(Tracer(mode=SamplingMode.FULL))
        workload_fn()
    full_start = time.perf_counter_ns()
    full_tracer = Tracer(mode=SamplingMode.FULL)
    configure_tracer(full_tracer)
    for _ in range(iterations):
        workload_fn()
    full_elapsed = time.perf_counter_ns() - full_start
    full_spans = full_tracer.collector.counts.written

    delta = full_elapsed - off_elapsed
    relative = (delta / off_elapsed) if off_elapsed > 0 else None
    return {
        "iterations": iterations,
        "warmup": warmup,
        "off_elapsed_ns": off_elapsed,
        "full_elapsed_ns": full_elapsed,
        "elapsed_delta_ns": delta,
        "relative_overhead": relative,
        "off_span_count": off_spans,
        "full_span_count": full_spans,
        "full_collector_dropped": full_tracer.collector.counts.dropped,
        "full_collector_failed": full_tracer.collector.counts.failed,
    }


__all__ = ["measure_overhead"]
