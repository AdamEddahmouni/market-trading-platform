"""Latency instrumentation v1 — software processing clocks for news→opportunity.

See COVERAGE.md in this package for timestamp definitions, clock domains,
correlation identity, path coverage, and UNAVAILABLE stages.
"""

from .collector import LatencyInstrumentationCollector
from .context import (
    bind_latency_collector,
    current_latency_collector,
    resolve_latency_collector,
)
from .types import (
    EligibilityClockId,
    LatencyStageId,
    LatencyTraceV1,
    StageStamp,
    UNAVAILABLE_OPERATOR_STAGES,
)

__all__ = [
    "EligibilityClockId",
    "LatencyInstrumentationCollector",
    "LatencyStageId",
    "LatencyTraceV1",
    "StageStamp",
    "UNAVAILABLE_OPERATOR_STAGES",
    "bind_latency_collector",
    "current_latency_collector",
    "resolve_latency_collector",
]
