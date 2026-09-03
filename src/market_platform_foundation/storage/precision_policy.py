"""Field-level numeric precision policy (GridIQ float downcast concept)."""

from __future__ import annotations

import struct
from typing import Any

FLOAT32_TOLERANCE = 1e-6


def downcast_float32(value: float) -> float:
    """Round-trip through IEEE float32 to record bounded precision."""
    return struct.unpack("f", struct.pack("f", value))[0]


def apply_precision_policy(value: Any, *, tolerance: float = FLOAT32_TOLERANCE) -> Any:
    if isinstance(value, float):
        return downcast_float32(value)
    if isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return value
        return format(downcast_float32(numeric), "g")
    return value


def values_within_tolerance(
    left: float,
    right: float,
    *,
    tolerance: float = FLOAT32_TOLERANCE,
) -> bool:
    return abs(left - right) <= tolerance
