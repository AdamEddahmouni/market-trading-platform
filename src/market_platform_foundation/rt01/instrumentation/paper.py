"""RT-01 instrumentation helpers for the Paper execution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..context import TraceContext
from ..enums import TraceStage, TraceStatus
from ..tracer import SpanHandle, Tracer, get_tracer

_MAX_ATTRIBUTE_LENGTH = 64
_MAX_ATTRIBUTES = 32
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "payload",
    "raw",
    "secret",
    "token",
)


def trace_refs(**values: Any) -> dict[str, str]:
    """Return bounded, safe scalar references for span attributes."""
    refs: dict[str, str] = {}
    for key, value in sorted(values.items()):
        name = str(key)
        if not name or any(part in name.lower() for part in _SENSITIVE_KEY_PARTS):
            continue
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if not text:
            continue
        refs[name] = text[:_MAX_ATTRIBUTE_LENGTH]
        if len(refs) >= _MAX_ATTRIBUTES:
            break
    return refs


@dataclass(slots=True)
class PaperTrace:
    """A safe wrapper around an optional RT-01 root span."""

    tracer: Tracer
    root: SpanHandle | None

    @property
    def context(self) -> TraceContext | None:
        return self.root.context if self.root is not None else None

    def child(
        self,
        stage: TraceStage,
        operation: str,
        **refs: Any,
    ) -> SpanHandle | None:
        if self.root is None:
            return None
        handle = self.tracer.start_span(
            stage,
            operation,
            parent=self.root.context,
            input_ref=trace_refs(**refs).get("input_ref"),
        )
        if handle is not None:
            handle.context.attributes.update(trace_refs(**refs))
        return handle

    def finish(
        self,
        *,
        status: TraceStatus = TraceStatus.OK,
        output_ref: str | None = None,
        error_code: str | None = None,
        terminated: bool = False,
    ):
        if self.root is None:
            return None
        return self.root.end(
            status=status,
            output_ref=output_ref,
            error_code=error_code,
            terminated=terminated,
        )


def start_paper_trace(
    operation: str,
    *,
    correlation_id: str,
    run_id: str | None = None,
    attempt_id: str | None = None,
    stable_sample_key: str | None = None,
    tracer: Tracer | None = None,
) -> PaperTrace:
    active_tracer = tracer or get_tracer()
    root = active_tracer.start_root(
        operation,
        correlation_id=correlation_id,
        stable_sample_key=stable_sample_key,
        run_id=run_id,
        attempt_id=attempt_id,
    )
    return PaperTrace(tracer=active_tracer, root=root)


__all__ = ["PaperTrace", "start_paper_trace", "trace_refs"]
