"""EVIDENCE-01B real-provider integration and operational campaign runtime."""

from .config import (
    build_configuration_snapshot,
    configuration_snapshot_from_dict,
    configuration_snapshot_to_dict,
    derive_configuration_fingerprint,
    is_semantic_config_compatible,
    is_source_sha_compatible,
)
from .continuity import classify_gap, maximum_qualifying_session_gap
from .events import derive_event_id
from .health import assess_campaign_health, assess_heartbeat, format_health_status
from .preflight import PreflightResultV1, run_preflight
from .provider_bridge import (
    FakeProviderAdapter,
    ProviderEventV1,
    build_provider_provenance,
    ingest_runtime_record,
    map_runtime_admission_to_quality,
)
from .runtime import CampaignRuntime
from .service import CampaignRuntimeService
from .settlement_worker import SettlementBatchResult, SettlementWorker
from .store import CampaignRuntimeStore
from .types import (
    CHECKPOINT_INTERVAL_NS,
    CampaignConfigurationSnapshotV1,
    CampaignHealthAssessmentV1,
    CampaignHealthState,
    CampaignMetricsV1,
    ContinuityGapCategory,
    DiagnosticCode,
    FORWARD_CAMPAIGN_RUNTIME_IMPLEMENTATION_VERSION,
    FORWARD_CAMPAIGN_RUNTIME_SCHEMA_VERSION,
    HealthSeverity,
    OperationalEventType,
    OperationalEventV1,
    PreflightDisposition,
    RuntimeHeartbeatState,
    RuntimeHeartbeatV1,
    SettlementWorkerState,
    ShakedownStatus,
)

__all__ = [
    "CHECKPOINT_INTERVAL_NS",
    "CampaignConfigurationSnapshotV1",
    "CampaignHealthAssessmentV1",
    "CampaignHealthState",
    "CampaignMetricsV1",
    "CampaignRuntime",
    "CampaignRuntimeService",
    "CampaignRuntimeStore",
    "ContinuityGapCategory",
    "DiagnosticCode",
    "FakeProviderAdapter",
    "FORWARD_CAMPAIGN_RUNTIME_IMPLEMENTATION_VERSION",
    "FORWARD_CAMPAIGN_RUNTIME_SCHEMA_VERSION",
    "HealthSeverity",
    "OperationalEventType",
    "OperationalEventV1",
    "PreflightDisposition",
    "PreflightResultV1",
    "ProviderEventV1",
    "RuntimeHeartbeatState",
    "RuntimeHeartbeatV1",
    "SettlementBatchResult",
    "SettlementWorker",
    "SettlementWorkerState",
    "ShakedownStatus",
    "assess_campaign_health",
    "assess_heartbeat",
    "build_configuration_snapshot",
    "build_provider_provenance",
    "classify_gap",
    "configuration_snapshot_from_dict",
    "configuration_snapshot_to_dict",
    "derive_configuration_fingerprint",
    "derive_event_id",
    "format_health_status",
    "ingest_runtime_record",
    "is_semantic_config_compatible",
    "is_source_sha_compatible",
    "map_runtime_admission_to_quality",
    "maximum_qualifying_session_gap",
    "run_preflight",
]
