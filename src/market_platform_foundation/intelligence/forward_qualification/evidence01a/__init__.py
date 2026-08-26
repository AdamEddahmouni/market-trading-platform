"""EVIDENCE-01A real forward observation campaign (extends EVIDENCE-01)."""

from .observations import (
    build_observation_inputs,
    load_campaign_repository,
    origin_qualifies_for_real_evidence,
    persist_forecast,
    persist_ledger_entry,
    persist_outcome,
)
from .progress import build_progress_summary, default_policy, format_progress_text
from .service import CampaignConfigurationError, CampaignService, DEFAULT_INSTRUMENT_UNIVERSE
from .store import CampaignRuntimeState, CampaignStore, CampaignStoreError
from .types import (
    CampaignEvidenceOrigin,
    CampaignObservationRefV1,
    ForwardObservationCampaignCheckpointV1,
    ForwardObservationCampaignReportV1,
    ForwardObservationCampaignSessionV1,
    ForwardObservationCampaignSpecV1,
    ForwardObservationCampaignState,
    FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
    FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
    MIN_QUALIFYING_ELIGIBLE_PER_SESSION,
    MIN_QUALIFYING_SESSION_DURATION_NS,
    SessionTerminationReason,
)

__all__ = [
    "CampaignConfigurationError",
    "CampaignEvidenceOrigin",
    "CampaignObservationRefV1",
    "CampaignRuntimeState",
    "CampaignService",
    "CampaignStore",
    "CampaignStoreError",
    "DEFAULT_INSTRUMENT_UNIVERSE",
    "FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION",
    "FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION",
    "ForwardObservationCampaignCheckpointV1",
    "ForwardObservationCampaignReportV1",
    "ForwardObservationCampaignSessionV1",
    "ForwardObservationCampaignSpecV1",
    "ForwardObservationCampaignState",
    "MIN_QUALIFYING_ELIGIBLE_PER_SESSION",
    "MIN_QUALIFYING_SESSION_DURATION_NS",
    "SessionTerminationReason",
    "build_observation_inputs",
    "build_progress_summary",
    "default_policy",
    "format_progress_text",
    "load_campaign_repository",
    "origin_qualifies_for_real_evidence",
    "persist_forecast",
    "persist_ledger_entry",
    "persist_outcome",
]
