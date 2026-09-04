"""RT-01 live pipeline instrumentation hooks."""

from __future__ import annotations

from typing import Any

from ..clock import monotonic_process_ns, monotonic_wall_ns
from ..enums import TraceStage, TraceStatus
from ..propagation import extract_carrier, inject_carrier
from ..tracer import get_tracer


def instrument_provider_receive(
    envelope: dict[str, Any],
    *,
    received_time_ns: int | None = None,
) -> dict[str, Any]:
    tracer = get_tracer()
    clocks = envelope.get("clocks") if isinstance(envelope.get("clocks"), dict) else {}
    event_ns = clocks.get("event_time_ns") or clocks.get("provider_time_ns")
    recv_ns = received_time_ns or clocks.get("received_time_ns") or monotonic_wall_ns()
    parent = extract_carrier(envelope)
    span = tracer.start_span(
        TraceStage.PROVIDER_RECEIVE,
        "provider_receive",
        parent=parent,
        input_ref=str(envelope.get("instrument_id") or envelope.get("capability") or ""),
        provider_event_time_ns=int(event_ns) if event_ns is not None else None,
        provider_received_time_ns=int(recv_ns),
    )
    out = inject_carrier(envelope, span.context if span else parent)
    if span:
        out["_rt01_receive_span"] = span
    return out


def complete_provider_receive(envelope: dict[str, Any], *, output_ref: str | None = None) -> None:
    span = envelope.get("_rt01_receive_span")
    if span is not None and hasattr(span, "end"):
        span.end(output_ref=output_ref)


def instrument_queue_enqueue(item: dict[str, Any]) -> dict[str, Any]:
    tracer = get_tracer()
    parent = extract_carrier(item)
    enqueue_mono = monotonic_process_ns()
    span = tracer.start_span(
        TraceStage.QUEUE,
        "enqueue",
        parent=parent,
        queue_enqueue_mono_ns=enqueue_mono,
    )
    out = inject_carrier(item, span.context if span else parent)
    out["_rt01_enqueue_mono_ns"] = enqueue_mono
    if span:
        out["_rt01_queue_span"] = span
    return out


def instrument_queue_dequeue(item: dict[str, Any]) -> dict[str, Any]:
    dequeue_mono = monotonic_process_ns()
    span = item.get("_rt01_queue_span")
    enqueue_mono = item.get("_rt01_enqueue_mono_ns")
    if span is not None and hasattr(span, "end"):
        if isinstance(enqueue_mono, int):
            span.queue_enqueue_mono_ns = enqueue_mono
        span.queue_dequeue_mono_ns = dequeue_mono
        span.end(output_ref="dequeued")
    tracer = get_tracer()
    parent = extract_carrier(item)
    process_span = tracer.start_span(
        TraceStage.QUEUE,
        "dequeue_process",
        parent=parent,
        queue_enqueue_mono_ns=int(enqueue_mono) if isinstance(enqueue_mono, int) else None,
        queue_dequeue_mono_ns=dequeue_mono,
    )
    out = inject_carrier(item, process_span.context if process_span else parent)
    if process_span:
        out["_rt01_process_span"] = process_span
    return out


def instrument_ingest_record(
    record: dict[str, Any],
    *,
    parent_carrier: dict[str, Any] | None = None,
) -> tuple[Any, Any, Any, Any]:
    tracer = get_tracer()
    parent = extract_carrier(record) or extract_carrier(parent_carrier or {})
    norm = tracer.start_span(TraceStage.NORMALIZE, "normalize", parent=parent, input_ref=str(record.get("instrument_id") or ""))
    qual = tracer.start_span(TraceStage.QUALITY, "quality", parent=norm.context if norm else parent)
    state = tracer.start_span(TraceStage.CANONICAL_STATE, "canonical_state", parent=qual.context if qual else parent)
    feature = tracer.start_span(TraceStage.FEATURE, "inline_feature", parent=state.context if state else parent)
    return norm, qual, state, feature


def complete_ingest_spans(
    spans: tuple[Any, Any, Any, Any],
    *,
    admitted: bool,
    envelope_id: str | None = None,
    terminated: bool = False,
) -> None:
    norm, qual, state, feature = spans
    if norm:
        norm.end(output_ref=envelope_id, terminated=not admitted and terminated)
    if qual:
        qual.end(terminated=not admitted and terminated)
    if state and admitted:
        state.end(output_ref=envelope_id)
    elif state and terminated:
        state.end(status=TraceStatus.TERMINATED, terminated=True)
    if feature and admitted:
        feature.end()


def complete_process_span(record: dict[str, Any], *, output_ref: str | None = None) -> None:
    span = record.get("_rt01_process_span")
    if span is not None and hasattr(span, "end"):
        span.end(output_ref=output_ref)


__all__ = [
    "complete_ingest_spans",
    "complete_process_span",
    "complete_provider_receive",
    "instrument_ingest_record",
    "instrument_provider_receive",
    "instrument_queue_dequeue",
    "instrument_queue_enqueue",
]
