"""RT-01 structural span validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .enums import TraceStage
from .span import TraceSpan


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    span_id: str | None = None


def validate_spans(spans: Iterable[TraceSpan]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    by_id: dict[str, TraceSpan] = {}
    for span in spans:
        if span.span_id in by_id:
            findings.append(
                ValidationFinding("DUPLICATE_SPAN_ID", "duplicate span_id", span.span_id)
            )
        by_id[span.span_id] = span
        if span.parent_span_id == span.span_id:
            findings.append(
                ValidationFinding("SELF_PARENT", "span is its own parent", span.span_id)
            )
        if span.clocks.duration_ns < 0:
            findings.append(
                ValidationFinding("NEGATIVE_DURATION", "negative duration", span.span_id)
            )
        if span.clocks.end_monotonic_ns < span.clocks.start_monotonic_ns:
            findings.append(
                ValidationFinding("END_BEFORE_START", "monotonic end before start", span.span_id)
            )
        if span.clocks.end_wall_time_ns < span.clocks.start_wall_time_ns:
            findings.append(
                ValidationFinding("WALL_END_BEFORE_START", "wall end before start", span.span_id)
            )
    for span in by_id.values():
        if span.parent_span_id is not None and span.parent_span_id not in by_id:
            findings.append(
                ValidationFinding("UNKNOWN_PARENT", "unknown parent span", span.span_id)
            )
        if _has_cycle(span.span_id, by_id):
            findings.append(
                ValidationFinding("CYCLE", "parent cycle detected", span.span_id)
            )
        if span.parent_span_id is not None:
            parent = by_id.get(span.parent_span_id)
            if parent is not None and parent.trace_id != span.trace_id:
                findings.append(
                    ValidationFinding("TRACE_MISMATCH", "parent trace_id mismatch", span.span_id)
                )
    return findings


def _has_cycle(span_id: str, by_id: dict[str, TraceSpan]) -> bool:
    seen: set[str] = set()
    current = span_id
    while True:
        if current in seen:
            return True
        seen.add(current)
        row = by_id.get(current)
        if row is None or row.parent_span_id is None:
            return False
        current = row.parent_span_id


__all__ = ["ValidationFinding", "validate_spans"]
