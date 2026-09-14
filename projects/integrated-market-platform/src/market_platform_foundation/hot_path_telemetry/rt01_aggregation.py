"""Aggregate hot-path timestamps from RT-01 trace spans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market_platform_foundation.rt01.enums import TraceStage, TraceStatus
from market_platform_foundation.rt01.span import TraceSpan

from .models import HOT_PATH_TIMESTAMP_NAMES
from .stats import empty_presence, latency_summary, merge_presence


@dataclass(frozen=True, slots=True)
class TraceTimestampRow:
    source_event_at: int | None = None
    provider_received_at: int | None = None
    imp_received_at: int | None = None
    normalized_at: int | None = None


def _span_by_stage(spans: list[TraceSpan], stage: TraceStage) -> TraceSpan | None:
    matches = [span for span in spans if span.stage == stage]
    if not matches:
        return None
    return min(matches, key=lambda row: row.clocks.start_monotonic_ns)


def trace_timestamp_row(spans: list[TraceSpan]) -> TraceTimestampRow:
    receive = _span_by_stage(spans, TraceStage.PROVIDER_RECEIVE)
    normalize = _span_by_stage(spans, TraceStage.NORMALIZE)
    source_event = receive.provider_event_time_ns if receive else None
    provider_received = receive.provider_received_time_ns if receive else None
    imp_received: int | None = None
    if receive is not None:
        imp_received = receive.clocks.end_monotonic_ns
    normalized: int | None = None
    if normalize is not None:
        normalized = normalize.clocks.end_monotonic_ns
    return TraceTimestampRow(
        source_event_at=source_event,
        provider_received_at=provider_received,
        imp_received_at=imp_received,
        normalized_at=normalized,
    )


def _presence_for_rows(rows: list[TraceTimestampRow]) -> dict[str, dict[str, int]]:
    presence = {name: empty_presence() for name in HOT_PATH_TIMESTAMP_NAMES}
    field_map = {
        "source_event_at": "source_event_at",
        "provider_received_at": "provider_received_at",
        "imp_received_at": "imp_received_at",
        "normalized_at": "normalized_at",
    }
    for row in rows:
        for name, attr in field_map.items():
            value = getattr(row, attr)
            bucket = presence[name]
            if value is None:
                presence[name] = {"present_count": bucket["present_count"], "missing_count": bucket["missing_count"] + 1}
            else:
                presence[name] = {"present_count": bucket["present_count"] + 1, "missing_count": bucket["missing_count"]}
    for name in ("router_dispatched_at", "detected_at", "opportunity_created_at", "operator_surfaced_at"):
        presence[name] = {"present_count": 0, "missing_count": len(rows)}
    return presence


def _segment_samples(rows: list[TraceTimestampRow], left: str, right: str) -> tuple[list[int], int]:
    samples: list[int] = []
    missing = 0
    for row in rows:
        lval = getattr(row, left)
        rval = getattr(row, right)
        if lval is None or rval is None:
            missing += 1
            continue
        delta = int(rval) - int(lval)
        if delta >= 0:
            samples.append(delta)
        else:
            missing += 1
    return samples, missing


def aggregate_rt01_spans(spans: list[TraceSpan]) -> dict[str, Any]:
    by_trace: dict[str, list[TraceSpan]] = {}
    for span in spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    rows = [trace_timestamp_row(trace_spans) for trace_spans in by_trace.values()]
    presence = _presence_for_rows(rows)

    segments: dict[str, dict[str, Any]] = {}
    segment_defs = (
        ("imp_receive_to_normalized", "imp_received_at", "normalized_at"),
    )
    for segment_id, left, right in segment_defs:
        samples, missing = _segment_samples(rows, left, right)
        segments[segment_id] = latency_summary(samples, missing_pair_count=missing)

    normalized_ok = sum(
        1
        for trace_spans in by_trace.values()
        for span in trace_spans
        if span.stage == TraceStage.NORMALIZE and span.status == TraceStatus.OK
    )

    return {
        "trace_count": len(rows),
        "timestamp_presence": presence,
        "latency_segments_ns": segments,
        "normalized_span_ok_count": normalized_ok,
    }


__all__ = ["aggregate_rt01_spans", "trace_timestamp_row", "TraceTimestampRow"]
