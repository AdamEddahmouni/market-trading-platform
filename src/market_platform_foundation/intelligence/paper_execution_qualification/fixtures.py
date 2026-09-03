"""Shared fixture helpers for paper execution qualification (BUILD 27)."""

from __future__ import annotations

from typing import Any


def sample_bars_for_execution(
    *,
    created_time_ns: int,
    high: str = "102.00",
    low: str = "99.00",
    volume: int = 100_000,
    bar_offset_ns: int = 60_000_000_000,
) -> list[dict[str, Any]]:
    """Bars with available_time strictly after created_time for BarConservativeSimulator."""
    bar_time = created_time_ns + bar_offset_ns
    return [
        {
            "available_time": bar_time,
            "normalized_event_id": f"bar-{bar_time}",
            "bar_payload": {
                "high": high,
                "low": low,
                "volume": volume,
            },
        },
    ]
