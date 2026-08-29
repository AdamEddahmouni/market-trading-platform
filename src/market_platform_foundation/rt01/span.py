"""RT-01 trace span contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import TraceStage, TraceStatus
from .clock import SpanClocks


@dataclass(frozen=True, slots=True)
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    stage: TraceStage
    operation: str
    clocks: SpanClocks
    status: TraceStatus
    correlation_id: str | None = None
    run_id: str | None = None
    attempt_id: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    error_class: str | None = None
    error_code: str | None = None
    provider_event_time_ns: int | None = None
    provider_received_time_ns: int | None = None
    queue_enqueue_mono_ns: int | None = None
    queue_dequeue_mono_ns: int | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "stage": self.stage.value,
            "operation": self.operation,
            "start_wall_time_ns": self.clocks.start_wall_time_ns,
            "end_wall_time_ns": self.clocks.end_wall_time_ns,
            "start_monotonic_ns": self.clocks.start_monotonic_ns,
            "end_monotonic_ns": self.clocks.end_monotonic_ns,
            "duration_ns": self.clocks.duration_ns,
            "status": self.status.value,
        }
        if self.correlation_id is not None:
            row["correlation_id"] = self.correlation_id
        if self.run_id is not None:
            row["run_id"] = self.run_id
        if self.attempt_id is not None:
            row["attempt_id"] = self.attempt_id
        if self.input_ref is not None:
            row["input_ref"] = self.input_ref
        if self.output_ref is not None:
            row["output_ref"] = self.output_ref
        if self.error_class is not None:
            row["error_class"] = self.error_class
        if self.error_code is not None:
            row["error_code"] = self.error_code
        if self.provider_event_time_ns is not None:
            row["provider_event_time_ns"] = self.provider_event_time_ns
        if self.provider_received_time_ns is not None:
            row["provider_received_time_ns"] = self.provider_received_time_ns
        if self.queue_enqueue_mono_ns is not None:
            row["queue_enqueue_mono_ns"] = self.queue_enqueue_mono_ns
        if self.queue_dequeue_mono_ns is not None:
            row["queue_dequeue_mono_ns"] = self.queue_dequeue_mono_ns
        if self.attributes:
            row["attributes"] = dict(self.attributes)
        return row

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> TraceSpan:
        clocks = SpanClocks(
            start_wall_time_ns=int(row["start_wall_time_ns"]),
            end_wall_time_ns=int(row["end_wall_time_ns"]),
            start_monotonic_ns=int(row["start_monotonic_ns"]),
            end_monotonic_ns=int(row["end_monotonic_ns"]),
        )
        attrs = row.get("attributes")
        return cls(
            trace_id=str(row["trace_id"]),
            span_id=str(row["span_id"]),
            parent_span_id=row.get("parent_span_id"),
            stage=TraceStage(str(row["stage"])),
            operation=str(row["operation"]),
            clocks=clocks,
            status=TraceStatus(str(row["status"])),
            correlation_id=row.get("correlation_id"),
            run_id=row.get("run_id"),
            attempt_id=row.get("attempt_id"),
            input_ref=row.get("input_ref"),
            output_ref=row.get("output_ref"),
            error_class=row.get("error_class"),
            error_code=row.get("error_code"),
            provider_event_time_ns=row.get("provider_event_time_ns"),
            provider_received_time_ns=row.get("provider_received_time_ns"),
            queue_enqueue_mono_ns=row.get("queue_enqueue_mono_ns"),
            queue_dequeue_mono_ns=row.get("queue_dequeue_mono_ns"),
            attributes=dict(attrs) if isinstance(attrs, dict) else {},
        )


__all__ = ["TraceSpan"]
