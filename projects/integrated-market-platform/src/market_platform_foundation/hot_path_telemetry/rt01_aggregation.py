"""Aggregate hot-path timestamps from RT-01 trace spans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market_platform_foundation.rt01.enums import TraceStage, TraceStatus
from market_platform_foundation.rt01.span import TraceSpan

from .models import HOT_PATH_TIMESTAMP_NAMES
from .stats import empty_presence, latency_summary


@dataclass(frozen=True, slots=True)
class TraceTimestampRow:
    source_event_at: int | None = None
    provider_received_at: int | None = None
    imp_received_at: int | None = None
    normalized_at: int | None = None


def rows_from_spans(spans: list[TraceSpan]) -> list[TraceTimestampRow]:
    receive_spans = sorted(
        [span for span in spans if span.stage == TraceStage.PROVIDER_RECEIVE],
        key=lambda row: row.clocks.start_monotonic_ns,
    )
    normalize_spans = sorted(
        [span for span in spans if span.stage == TraceStage.NORMALIZE],
        key=lambda row: row.clocks.start_monotonic_ns,
    )
    rows: list[TraceTimestampRow] = []
    for index, receive in enumerate(receive_spans):
        normalize = normalize_spans[index] if index < len(normalize_spans) else None
        rows.append(
            TraceTimestampRow(
                source_event_at=receive.provider_event_time_ns,
                provider_received_at=receive.provider_received_time_ns,
                imp_received_at=receive.clocks.end_monotonic_ns,
                normalized_at=normalize.clocks.end_monotonic_ns if normalize is not None else None,
            )
        )
    return rows


def trace_timestamp_row(spans: list[TraceSpan]) -> TraceTimestampRow:
    rows = rows_from_spans(spans)
    if not rows:
        return TraceTimestampRow()
    return rows[0]


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
                presence[name] = {
                    "present_count": bucket["present_count"],
                    "missing_count": bucket["missing_count"] + 1,
                }
            else:
                presence[name] = {
                    "present_count": bucket["present_count"] + 1,
                    "missing_count": bucket["missing_count"],
                }
    for name in ("router_dispatched_at", "detected_at", "opportunity_created_at", "operator_surfaced_at"):
        presence[name] = empty_presence()
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
    rows = rows_from_spans(spans)
    presence = _presence_for_rows(rows)

    segments: dict[str, dict[str, Any]] = {}
    segment_defs = (
        ("imp_receive_to_normalized", "imp_received_at", "normalized_at"),
    )
    for segment_id, left, right in segment_defs:
        samples, missing = _segment_samples(rows, left, right)
        segments[segment_id] = latency_summary(samples, missing_pair_count=missing)

    normalized_ok = sum(
        1 for span in spans if span.stage == TraceStage.NORMALIZE and span.status == TraceStatus.OK
    )

    return {
        "trace_count": len(rows),
        "timestamp_presence": presence,
        "latency_segments_ns": segments,
        "normalized_span_ok_count": normalized_ok,
    }


__all__ = ["aggregate_rt01_spans", "rows_from_spans", "trace_timestamp_row", "TraceTimestampRow"]
