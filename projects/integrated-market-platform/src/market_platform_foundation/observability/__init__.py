"""Cross-cutting observability sidecars (latency, coverage notes).

New modules live here so frozen intelligence/UI contracts stay untouched.
"""

from .latency_instrumentation_v1 import (
    EligibilityClockId,
    LatencyInstrumentationCollector,
    LatencyStageId,
    LatencyTraceV1,
    UNAVAILABLE_OPERATOR_STAGES,
    bind_latency_collector,
    current_latency_collector,
    resolve_latency_collector,
)

__all__ = [
    "EligibilityClockId",
    "LatencyInstrumentationCollector",
    "LatencyStageId",
    "LatencyTraceV1",
    "UNAVAILABLE_OPERATOR_STAGES",
    "bind_latency_collector",
    "current_latency_collector",
    "resolve_latency_collector",
]
