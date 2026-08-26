"""EVIDENCE-01B operational runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

FORWARD_CAMPAIGN_RUNTIME_IMPLEMENTATION_VERSION = "evidence01b-v1"
FORWARD_CAMPAIGN_RUNTIME_SCHEMA_VERSION = "1"

STALE_HEARTBEAT_NS = 5 * 60 * 1_000_000_000
SETTLEMENT_RETRY_INTERVAL_NS = 60 * 1_000_000_000
MAX_SETTLEMENT_RETRIES = 5
CHECKPOINT_INTERVAL_NS = 30 * 60 * 1_000_000_000


class CampaignHealthState(StrEnum):
    HEALTHY_AND_ACCUMULATING = "HEALTHY_AND_ACCUMULATING"
    WAITING_FOR_MARKET = "WAITING_FOR_MARKET"
    NO_ELIGIBLE_PREDICTIONS = "NO_ELIGIBLE_PREDICTIONS"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    SETTLEMENT_BACKLOG = "SETTLEMENT_BACKLOG"
    CONTINUITY_AT_RISK = "CONTINUITY_AT_RISK"
    CLOCK_INTEGRITY_FAILURE = "CLOCK_INTEGRITY_FAILURE"
    PERSISTENCE_DEGRADED = "PERSISTENCE_DEGRADED"
    PAUSED = "PAUSED"
    INVALIDATED = "INVALIDATED"


class HealthSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    BLOCKING = "BLOCKING"


class RuntimeHeartbeatState(StrEnum):
    ACTIVE_AND_HEALTHY = "ACTIVE_AND_HEALTHY"
    ACTIVE_BUT_STALE = "ACTIVE_BUT_STALE"
    PROCESS_STOPPED = "PROCESS_STOPPED"
    PROVIDER_IDLE = "PROVIDER_IDLE"
    MARKET_CLOSED = "MARKET_CLOSED"


class ContinuityGapCategory(StrEnum):
    EXPECTED_MARKET_CLOSURE = "EXPECTED_MARKET_CLOSURE"
    PLANNED_SESSION_BOUNDARY = "PLANNED_SESSION_BOUNDARY"
    PROVIDER_DISCONNECT = "PROVIDER_DISCONNECT"
    RUNTIME_DOWN = "RUNTIME_DOWN"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    NO_ELIGIBLE_CANDIDATES = "NO_ELIGIBLE_CANDIDATES"
    UNKNOWN = "UNKNOWN"


class SettlementWorkerState(StrEnum):
    AWAITING_MATURITY = "AWAITING_MATURITY"
    MATURE_UNSETTLED = "MATURE_UNSETTLED"
    SETTLED = "SETTLED"
    UNLABELABLE = "UNLABELABLE"
    TRANSIENT_DATA_UNAVAILABLE = "TRANSIENT_DATA_UNAVAILABLE"
    INVALID = "INVALID"


class ShakedownStatus(StrEnum):
    SHAKEDOWN_NOT_STARTED = "SHAKEDOWN_NOT_STARTED"
    SHAKEDOWN_READY = "SHAKEDOWN_READY"
    SHAKEDOWN_ACTIVE = "SHAKEDOWN_ACTIVE"
    SHAKEDOWN_PASSED = "SHAKEDOWN_PASSED"
    SHAKEDOWN_FAILED = "SHAKEDOWN_FAILED"


class PreflightDisposition(StrEnum):
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    NOT_READY = "NOT_READY"


class OperationalEventType(StrEnum):
    CAMPAIGN_STARTED = "CAMPAIGN_STARTED"
    SESSION_STARTED = "SESSION_STARTED"
    PROVIDER_CONNECTED = "PROVIDER_CONNECTED"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    PROVIDER_RECONNECTED = "PROVIDER_RECONNECTED"
    SESSION_PAUSED = "SESSION_PAUSED"
    SESSION_RESUMED = "SESSION_RESUMED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    SETTLEMENT_BATCH_COMPLETED = "SETTLEMENT_BATCH_COMPLETED"
    HEALTH_DEGRADED = "HEALTH_DEGRADED"
    HEALTH_RECOVERED = "HEALTH_RECOVERED"
    CAMPAIGN_INVALIDATED = "CAMPAIGN_INVALIDATED"
    CAMPAIGN_ABORTED = "CAMPAIGN_ABORTED"
    SESSION_FINALIZED = "SESSION_FINALIZED"
    RUNTIME_STARTED = "RUNTIME_STARTED"
    RUNTIME_STOPPED = "RUNTIME_STOPPED"
    SHAKEDOWN_STARTED = "SHAKEDOWN_STARTED"
    SHAKEDOWN_COMPLETED = "SHAKEDOWN_COMPLETED"


class DiagnosticCode(StrEnum):
    NO_PROVIDER_EVENTS = "NO_PROVIDER_EVENTS"
    NO_VALID_CANDIDATES = "NO_VALID_CANDIDATES"
    ALL_EVENTS_EXCLUDED_BY_QUALITY = "ALL_EVENTS_EXCLUDED_BY_QUALITY"
    PREDICTOR_ABSTAINING = "PREDICTOR_ABSTAINING"
    PREDICTIONS_AWAITING_MATURITY = "PREDICTIONS_AWAITING_MATURITY"
    SETTLEMENT_BACKLOG = "SETTLEMENT_BACKLOG"
    MARKET_CLOSED = "MARKET_CLOSED"
    SOURCE_SHA_MISMATCH = "SOURCE_SHA_MISMATCH"
    CONFIG_FINGERPRINT_MISMATCH = "CONFIG_FINGERPRINT_MISMATCH"


@dataclass(frozen=True)
class CampaignConfigurationSnapshotV1:
    campaign_id: str
    policy_id: str
    source_sha: str
    provider_id: str
    provider_config_id: str
    universe_definition: tuple[str, ...]
    candidate_selection_id: str
    predictor_id: str
    settlement_policy_id: str
    quality_policy_id: str
    market_calendar_id: str
    continuity_policy_id: str
    persistence_backend: str
    observation_mode: str
    execution_authority: str
    campaign_configuration_fingerprint: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationalEventV1:
    event_id: str
    event_type: OperationalEventType
    campaign_id: str
    session_id: str | None
    recorded_at_ns: int
    severity: HealthSeverity
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignMetricsV1:
    provider_events_received: int = 0
    provider_events_accepted: int = 0
    provider_events_excluded: int = 0
    predictions_emitted: int = 0
    eligible_predictions: int = 0
    mature_predictions: int = 0
    settled_predictions: int = 0
    unlabelable_predictions: int = 0
    settlement_failures: int = 0
    settlement_backlog: int = 0
    duplicate_events: int = 0
    reconnects: int = 0
    runtime_restarts: int = 0
    clock_drift_exclusions: int = 0
    continuity_gaps: int = 0
    checkpoints_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_events_received": self.provider_events_received,
            "provider_events_accepted": self.provider_events_accepted,
            "provider_events_excluded": self.provider_events_excluded,
            "predictions_emitted": self.predictions_emitted,
            "eligible_predictions": self.eligible_predictions,
            "mature_predictions": self.mature_predictions,
            "settled_predictions": self.settled_predictions,
            "unlabelable_predictions": self.unlabelable_predictions,
            "settlement_failures": self.settlement_failures,
            "settlement_backlog": self.settlement_backlog,
            "duplicate_events": self.duplicate_events,
            "reconnects": self.reconnects,
            "runtime_restarts": self.runtime_restarts,
            "clock_drift_exclusions": self.clock_drift_exclusions,
            "continuity_gaps": self.continuity_gaps,
            "checkpoints_created": self.checkpoints_created,
        }


@dataclass
class RuntimeHeartbeatV1:
    state: RuntimeHeartbeatState
    last_heartbeat_ns: int
    last_provider_event_ns: int | None = None
    last_accepted_observation_ns: int | None = None
    process_started_at_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignHealthAssessmentV1:
    health_state: CampaignHealthState
    severity: HealthSeverity
    diagnostics: tuple[str, ...]
    diagnostic_codes: tuple[DiagnosticCode, ...]
    provider_state: str
    settlement_backlog: int
    qualifying_continuity_gap_ns: int
    metadata: dict[str, Any] = field(default_factory=dict)
