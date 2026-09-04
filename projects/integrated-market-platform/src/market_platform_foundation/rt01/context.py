"""RT-01 trace context and contextvar propagation."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

from .enums import SamplingMode
from .ids import new_correlation_id, new_span_id, new_trace_id


@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    correlation_id: str | None = None
    sampled: bool = True
    sampling_mode: SamplingMode = SamplingMode.FULL
    run_id: str | None = None
    attempt_id: str | None = None
    capability_id: str | None = None
    workflow_id: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def child(self, *, operation: str | None = None) -> TraceContext:
        attrs = dict(self.attributes)
        if operation:
            attrs["operation"] = operation
        return TraceContext(
            trace_id=self.trace_id,
            span_id=new_span_id(),
            parent_span_id=self.span_id,
            correlation_id=self.correlation_id,
            sampled=self.sampled,
            sampling_mode=self.sampling_mode,
            run_id=self.run_id,
            attempt_id=self.attempt_id,
            capability_id=self.capability_id,
            workflow_id=self.workflow_id,
            attributes=attrs,
        )

    def to_carrier(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "correlation_id": self.correlation_id,
            "sampled": self.sampled,
            "sampling_mode": self.sampling_mode.value,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "capability_id": self.capability_id,
            "workflow_id": self.workflow_id,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_carrier(cls, carrier: dict[str, Any] | None) -> TraceContext | None:
        if not carrier:
            return None
        trace_id = carrier.get("trace_id")
        span_id = carrier.get("span_id")
        if not isinstance(trace_id, str) or not isinstance(span_id, str):
            return None
        mode_raw = carrier.get("sampling_mode", SamplingMode.FULL.value)
        try:
            mode = SamplingMode(str(mode_raw))
        except ValueError:
            mode = SamplingMode.FULL
        attrs = carrier.get("attributes")
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=carrier.get("parent_span_id"),
            correlation_id=carrier.get("correlation_id"),
            sampled=bool(carrier.get("sampled", True)),
            sampling_mode=mode,
            run_id=carrier.get("run_id"),
            attempt_id=carrier.get("attempt_id"),
            capability_id=carrier.get("capability_id"),
            workflow_id=carrier.get("workflow_id"),
            attributes=dict(attrs) if isinstance(attrs, dict) else {},
        )


def new_root_context(
    *,
    correlation_id: str | None = None,
    sampled: bool = True,
    sampling_mode: SamplingMode = SamplingMode.FULL,
    run_id: str | None = None,
    attempt_id: str | None = None,
) -> TraceContext:
    return TraceContext(
        trace_id=new_trace_id(),
        span_id=new_span_id(),
        parent_span_id=None,
        correlation_id=correlation_id or new_correlation_id(),
        sampled=sampled,
        sampling_mode=sampling_mode,
        run_id=run_id,
        attempt_id=attempt_id,
    )


_current_context: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "rt01_trace_context",
    default=None,
)


def current_context() -> TraceContext | None:
    return _current_context.get()


def bind_context(ctx: TraceContext | None) -> contextvars.Token[TraceContext | None]:
    return _current_context.set(ctx)


def reset_context(token: contextvars.Token[TraceContext | None]) -> None:
    _current_context.reset(token)


__all__ = [
    "TraceContext",
    "bind_context",
    "current_context",
    "new_root_context",
    "reset_context",
]
