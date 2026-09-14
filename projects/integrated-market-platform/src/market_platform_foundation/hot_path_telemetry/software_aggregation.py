"""Aggregate hot-path clock rows into presence and segment latency summaries."""

from __future__ import annotations

from typing import Any

from .clock_row import HotPathClockRow
from .models import HOT_PATH_TIMESTAMP_NAMES
from .stats import empty_presence, latency_summary


def presence_from_clock_rows(rows: tuple[HotPathClockRow, ...] | list[HotPathClockRow]) -> dict[str, dict[str, int]]:
    presence = {name: empty_presence() for name in HOT_PATH_TIMESTAMP_NAMES}
    for row in rows:
        payload = row.as_timestamp_map()
        for name in HOT_PATH_TIMESTAMP_NAMES:
            bucket = presence[name]
            if payload.get(name) is None:
                presence[name] = {
                    "present_count": bucket["present_count"],
                    "missing_count": bucket["missing_count"] + 1,
                }
            else:
                presence[name] = {
                    "present_count": bucket["present_count"] + 1,
                    "missing_count": bucket["missing_count"],
                }
    return presence


def _segment_samples(rows: tuple[HotPathClockRow, ...], left: str, right: str) -> tuple[list[int], int]:
    samples: list[int] = []
    missing = 0
    for row in rows:
        payload = row.as_timestamp_map()
        lval = payload.get(left)
        rval = payload.get(right)
        if lval is None or rval is None:
            missing += 1
            continue
        delta = int(rval) - int(lval)
        if delta >= 0:
            samples.append(delta)
        else:
            missing += 1
    return samples, missing


def aggregate_software_clock_rows(rows: tuple[HotPathClockRow, ...] | list[HotPathClockRow]) -> dict[str, Any]:
    ordered = tuple(rows)
    presence = presence_from_clock_rows(ordered)
    segment_defs = (
        ("imp_receive_to_normalized", "imp_received_at", "normalized_at"),
        ("normalized_to_router_dispatched", "normalized_at", "router_dispatched_at"),
        ("router_dispatched_to_detected", "router_dispatched_at", "detected_at"),
        ("detected_to_opportunity_created", "detected_at", "opportunity_created_at"),
        ("opportunity_created_to_operator_surfaced", "opportunity_created_at", "operator_surfaced_at"),
    )
    segments: dict[str, dict[str, Any]] = {}
    for segment_id, left, right in segment_defs:
        samples, missing = _segment_samples(ordered, left, right)
        segments[segment_id] = latency_summary(samples, missing_pair_count=missing)
    return {
        "row_count": len(ordered),
        "timestamp_presence": presence,
        "latency_segments_ns": segments,
    }


__all__ = ["aggregate_software_clock_rows", "presence_from_clock_rows"]
