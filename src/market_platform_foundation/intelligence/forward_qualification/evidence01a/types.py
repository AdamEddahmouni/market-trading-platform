"""EVIDENCE-01A real forward observation campaign contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION = "1"
FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION = "evidence01a-v1"

MIN_QUALIFYING_SESSION_DURATION_NS = 5 * 60 * 1_000_000_000
MIN_QUALIFYING_ELIGIBLE_PER_SESSION = 1


class CampaignEvidenceOrigin(StrEnum):
    LIVE_FORWARD = "LIVE_FORWARD"
    FIXTURE = "FIXTURE"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class ForwardObservationCampaignState(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    AWAITING_SETTLEMENT = "AWAITING_SETTLEMENT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    QUALIFIED = "QUALIFIED"
    FINALIZED = "FINALIZED"
    ABORTED = "ABORTED"
    INVALIDATED = "INVALIDATED"


class SessionTerminationReason(StrEnum):
    OPERATOR_STOP = "OPERATOR_STOP"
    CLEAN_SHUTDOWN = "CLEAN_SHUTDOWN"
    PROVIDER_DISCONNECT = "PROVIDER_DISCONNECT"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    ABORT = "ABORT"
    CRASH_RECOVERY = "CRASH_RECOVERY"


@dataclass(frozen=True)
class ForwardObservationCampaignSpecV1:
    campaign_id: str
    schema_version: str
    campaign_name: str
    policy_id: str
    source_commit_sha: str
    runtime_version: str
    provider_id: str
    instrument_universe: tuple[str, ...]
    observation_mode: str
    evidence_origin: CampaignEvidenceOrigin
    execution_mode: str
    execution_authority: str
    persistence_backend: str
    checkpoint_cadence: str
    settlement_cadence: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardObservationCampaignSessionV1:
    session_id: str
    schema_version: str
    campaign_id: str
    source_commit_sha: str
    policy_id: str
    started_at_ns: int
    ended_at_ns: int | None
    termination_reason: str | None
    provider_id: str
    provider_connected: bool
    instrument_universe: tuple[str, ...]
    evidence_origin: CampaignEvidenceOrigin
    prediction_count: int
    eligible_prediction_count: int
    quality_exclusions: dict[str, int]
    orders_submitted: int
    reconnect_count: int
    maximum_continuity_gap_ns: int
    runtime_errors: tuple[str, ...]
    clean_shutdown: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignObservationRefV1:
    observation_ref_id: str
    campaign_id: str
    session_id: str
    forecast_id: str
    ledger_entry_id: str
    receipt_id: str
    evidence_origin: CampaignEvidenceOrigin
    provider_id: str
    quality_state: str
    decision_time_ns: int
    source_commit_sha: str
    policy_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardObservationCampaignCheckpointV1:
    checkpoint_id: str
    schema_version: str
    campaign_id: str
    policy_id: str
    assessment_id: str
    observation_cutoff_ns: int
    settlement_cutoff_ns: int
    campaign_state: ForwardObservationCampaignState
    qualification_disposition: str
    remaining_requirements: tuple[str, ...]
    progress: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardObservationCampaignReportV1:
    report_id: str
    schema_version: str
    campaign_id: str
    policy_id: str
    final_assessment_id: str
    campaign_state: ForwardObservationCampaignState
    qualification_disposition: str
    limitation_status: str
    observation_cutoff_ns: int
    settlement_cutoff_ns: int
    progress: dict[str, Any]
    remaining_requirements: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
