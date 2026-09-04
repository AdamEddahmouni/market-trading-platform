"""RT-01 tracer — span lifecycle and collector integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clock import monotonic_process_ns, span_clocks, wall_time_ns
from .collector import InMemoryTraceCollector
from .context import (
    TraceContext,
    bind_context,
    current_context,
    new_root_context,
    reset_context,
)
from .enums import SamplingMode, TraceStage, TraceStatus
from .sampling import sampling_decision
from .span import TraceSpan


@dataclass
class SpanHandle:
    tracer: "Tracer"
    context: TraceContext
    stage: TraceStage
    operation: str
    start_wall_ns: int
    start_mono_ns: int
    input_ref: str | None = None
    provider_event_time_ns: int | None = None
    provider_received_time_ns: int | None = None
    queue_enqueue_mono_ns: int | None = None
    queue_dequeue_mono_ns: int | None = None
    _token: Any = field(default=None, repr=False)
    _ended: bool = field(default=False, repr=False)

    def end(
        self,
        *,
        status: TraceStatus = TraceStatus.OK,
        output_ref: str | None = None,
        error_class: str | None = None,
        error_code: str | None = None,
        terminated: bool = False,
    ) -> TraceSpan | None:
        if self._ended:
            return None
        self._ended = True
        if self._token is not None:
            reset_context(self._token)
        if not self.context.sampled or self.tracer.mode == SamplingMode.OFF:
            return None
        end_wall = wall_time_ns()
        end_mono = monotonic_process_ns()
        final_status = TraceStatus.TERMINATED if terminated else status
        span = TraceSpan(
            trace_id=self.context.trace_id,
            span_id=self.context.span_id,
            parent_span_id=self.context.parent_span_id,
            stage=self.stage,
            operation=self.operation,
            clocks=span_clocks(self.start_wall_ns, self.start_mono_ns, end_wall, end_mono),
            status=final_status,
            correlation_id=self.context.correlation_id,
            run_id=self.context.run_id,
            attempt_id=self.context.attempt_id,
            input_ref=self.input_ref,
            output_ref=output_ref,
            error_class=error_class,
            error_code=error_code,
            provider_event_time_ns=self.provider_event_time_ns,
            provider_received_time_ns=self.provider_received_time_ns,
            queue_enqueue_mono_ns=self.queue_enqueue_mono_ns,
            queue_dequeue_mono_ns=self.queue_dequeue_mono_ns,
            attributes=dict(self.context.attributes),
        )
        self.tracer.collector.record(span)
        return span


class Tracer:
    def __init__(
        self,
        *,
        mode: SamplingMode = SamplingMode.FULL,
        collector: InMemoryTraceCollector | None = None,
        sample_rate: int = 100,
    ) -> None:
        self.mode = mode
        self.sample_rate = sample_rate
        self.collector = collector or InMemoryTraceCollector()

    def start_span(
        self,
        stage: TraceStage,
        operation: str,
        *,
        parent: TraceContext | None = None,
        input_ref: str | None = None,
        stable_sample_key: str | None = None,
        correlation_id: str | None = None,
        run_id: str | None = None,
        attempt_id: str | None = None,
        provider_event_time_ns: int | None = None,
        provider_received_time_ns: int | None = None,
        queue_enqueue_mono_ns: int | None = None,
        queue_dequeue_mono_ns: int | None = None,
        bind: bool = True,
        force_root: bool = False,
    ) -> SpanHandle | None:
        if self.mode == SamplingMode.OFF:
            return None
        base = parent if parent is not None else (None if force_root else current_context())
        if base is None:
            sampled = sampling_decision(
                mode=self.mode,
                stable_key=stable_sample_key or operation,
                rate=self.sample_rate,
            )
            ctx = new_root_context(
                correlation_id=correlation_id,
                sampled=sampled,
                sampling_mode=self.mode,
                run_id=run_id,
                attempt_id=attempt_id,
            )
        else:
            ctx = base.child(operation=operation)
            if self.mode == SamplingMode.DETERMINISTIC_SAMPLE and not base.sampled:
                ctx.sampled = False
        token = None
        if bind:
            token = bind_context(ctx)
        return SpanHandle(
            tracer=self,
            context=ctx,
            stage=stage,
            operation=operation,
            start_wall_ns=wall_time_ns(),
            start_mono_ns=monotonic_process_ns(),
            input_ref=input_ref,
            provider_event_time_ns=provider_event_time_ns,
            provider_received_time_ns=provider_received_time_ns,
            queue_enqueue_mono_ns=queue_enqueue_mono_ns,
            queue_dequeue_mono_ns=queue_dequeue_mono_ns,
            _token=token,
        )

    def start_root(
        self,
        operation: str = "root",
        *,
        correlation_id: str | None = None,
        stable_sample_key: str | None = None,
        run_id: str | None = None,
        attempt_id: str | None = None,
    ) -> SpanHandle | None:
        return self.start_span(
            TraceStage.TRACE_ROOT,
            operation,
            parent=None,
            correlation_id=correlation_id,
            stable_sample_key=stable_sample_key,
            run_id=run_id,
            attempt_id=attempt_id,
            force_root=True,
        )


_GLOBAL: Tracer | None = None


def get_tracer() -> Tracer:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = Tracer()
    return _GLOBAL


def configure_tracer(tracer: Tracer) -> None:
    global _GLOBAL
    _GLOBAL = tracer


__all__ = ["SpanHandle", "Tracer", "configure_tracer", "get_tracer"]
