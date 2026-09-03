from __future__ import annotations

from typing import Any


def trend(values: list[float | int | None], *, field: str) -> dict[str, Any]:
    valid = [float(value) for value in values if value is not None]
    if len(valid) < 2:
        return {
            "state": "INSUFFICIENT_HISTORY",
            "field": field,
            "observation_count": len(valid),
            "first": None if not valid else valid[0],
            "latest": None if not valid else valid[-1],
            "change": None,
        }
    change = valid[-1] - valid[0]
    state = "ASCENDING" if change > 0 else "DESCENDING" if change < 0 else "FLAT"
    return {
        "state": state,
        "field": field,
        "observation_count": len(valid),
        "first": valid[0],
        "latest": valid[-1],
        "change": change,
    }
