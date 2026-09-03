"""Replay delivery models and run summaries (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import ContractReference
from ..quality.models import QualityDecision


class ReplayMode(StrEnum):
    OBSERVED_REPLAY = "OBSERVED_REPLAY"
    COUNTERFACTUAL = "COUNTERFACTUAL"


class DeliveryAction(StrEnum):
    DELIVER = "DELIVER"
    DELAY = "DELAY"
    DROP = "DROP"
    THROTTLE_DELAY = "THROTTLE_DELAY"
    DISCONNECT_DROP = "DISCONNECT_DROP"
    ENTITLEMENT_BLOCK = "ENTITLEMENT_BLOCK"


class DisconnectPolicy(StrEnum):
    DROP = "DROP"
    BUFFER = "BUFFER"


class ThrottleOverflowAction(StrEnum):
    DROP = "DROP"
    BUFFER = "BUFFER"


REPLAY_RUNTIME_COMPONENT_ID = "replay-runtime"
REPLAY_RUNTIME_COMPONENT_VERSION = "1"
REPLAY_SCENARIO_FINGERPRINT_VERSION = "replay-scenario-sha256-v1"


@dataclass(frozen=True, slots=True)
class ReplayDeliveryEnvelope:
    """Runtime-only delivery metadata — source EventV1 remains immutable."""

    event_id: str
    recorded_available_time_ns: int
    effective_delivery_time_ns: int
    delivery_action: DeliveryAction
    matched_fault_rules: tuple[str, ...] = ()
    provider_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayTraceSummary:
    delivered_count: int = 0
    dropped_count: int = 0
    delayed_count: int = 0
    undelivered_count: int = 0
    decision_count: int = 0
    provider_disconnect_transitions: int = 0


@dataclass(frozen=True, slots=True)
class ReplayDecisionResult:
    decision_time_ns: int
    snapshot_ref: ContractReference | None = None
    signal_refs: tuple[ContractReference, ...] = ()
    detection_refs: tuple[ContractReference, ...] = ()
    routing_decision_refs: tuple[ContractReference, ...] = ()
    quality_decision: QualityDecision | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayRunResult:
    scenario_fingerprint: str
    run_id: str
    replay_mode: ReplayMode
    start_time_ns: int
    end_time_ns: int
    source_event_count: int
    trace_summary: ReplayTraceSummary
    decision_results: tuple[ReplayDecisionResult, ...] = ()
    final_status: str = "COMPLETED"
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "DeliveryAction",
    "DisconnectPolicy",
    "REPLAY_RUNTIME_COMPONENT_ID",
    "REPLAY_RUNTIME_COMPONENT_VERSION",
    "REPLAY_SCENARIO_FINGERPRINT_VERSION",
    "ReplayDecisionResult",
    "ReplayDeliveryEnvelope",
    "ReplayMode",
    "ReplayRunResult",
    "ReplayTraceSummary",
    "ThrottleOverflowAction",
]
