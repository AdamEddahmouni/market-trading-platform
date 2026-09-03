"""RT-01 trace enumerations."""

from __future__ import annotations

from enum import StrEnum


class TraceStage(StrEnum):
    PROVIDER_EVENT = "provider_event"
    PROVIDER_RECEIVE = "provider_receive"
    QUEUE = "queue"
    NORMALIZE = "normalize"
    QUALITY = "quality"
    CANONICAL_STATE = "canonical_state"
    FEATURE = "feature"
    SIGNAL = "signal"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    ORDER_READY = "order_ready"
    BROKER = "broker"
    RECONCILIATION = "reconciliation"
    REPLAY_DECISION = "replay_decision"
    TRACE_ROOT = "trace_root"


class TraceStatus(StrEnum):
    OK = "OK"
    ERROR = "ERROR"
    TERMINATED = "TERMINATED"


class TraceCompleteness(StrEnum):
    COMPLETE_FOR_OBSERVED_PATH = "COMPLETE_FOR_OBSERVED_PATH"
    PARTIAL_CONTEXT_LOSS = "PARTIAL_CONTEXT_LOSS"
    PARTIAL_SAMPLED = "PARTIAL_SAMPLED"
    TERMINATED_BY_DOMAIN_DECISION = "TERMINATED_BY_DOMAIN_DECISION"
    TERMINATED_BY_ERROR = "TERMINATED_BY_ERROR"


class SamplingMode(StrEnum):
    OFF = "OFF"
    FULL = "FULL"
    DETERMINISTIC_SAMPLE = "DETERMINISTIC_SAMPLE"


class CollectorOutcome(StrEnum):
    ACCEPTED = "accepted"
    WRITTEN = "written"
    DROPPED = "dropped"
    FAILED = "failed"


__all__ = [
    "CollectorOutcome",
    "SamplingMode",
    "TraceCompleteness",
    "TraceStage",
    "TraceStatus",
]
