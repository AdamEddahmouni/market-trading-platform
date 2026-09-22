"""Capture wall + monotonic stamps for latency instrumentation v1."""

from __future__ import annotations

import time

from ...clock import monotonic_wall_ns
from .types import StageStamp


def capture_stage_stamp() -> StageStamp:
    """Real clocks only — never synthesize missing domains."""

    return StageStamp(wall_ns=int(monotonic_wall_ns()), mono_ns=int(time.perf_counter_ns()))


__all__ = ["capture_stage_stamp"]
