"""RT-01 context propagation across queues and threads."""

from __future__ import annotations

from typing import Any

from .context import TraceContext


TRACE_CARRIER_KEY = "rt01_trace_carrier"


def inject_carrier(payload: dict[str, Any], ctx: TraceContext | None) -> dict[str, Any]:
    if ctx is None:
        return payload
    out = dict(payload)
    out[TRACE_CARRIER_KEY] = ctx.to_carrier()
    return out


def extract_carrier(payload: dict[str, Any]) -> TraceContext | None:
    carrier = payload.get(TRACE_CARRIER_KEY)
    if not isinstance(carrier, dict):
        return None
    return TraceContext.from_carrier(carrier)


def queue_wait_ns(enqueue_mono_ns: int | None, dequeue_mono_ns: int | None) -> int | None:
    if enqueue_mono_ns is None or dequeue_mono_ns is None:
        return None
    return dequeue_mono_ns - enqueue_mono_ns


__all__ = [
    "TRACE_CARRIER_KEY",
    "extract_carrier",
    "inject_carrier",
    "queue_wait_ns",
]
