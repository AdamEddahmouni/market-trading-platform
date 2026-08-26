"""Controlled adaptation and governed research re-entry (BUILD 24)."""

from .engine import AdaptationContext, AdaptationEngine, EvidenceBundle
from .errors import AdaptationError
from .evidence import NormalizedEvidence
from .handoff import register_finding_from_trigger
from .identity import (
    derive_adaptation_assessment_id,
    derive_adaptation_campaign_id,
    derive_adaptation_event_id,
    derive_adaptation_policy_id,
    derive_dedup_key,
    derive_research_trigger_id,
)
from .policy import build_adaptation_policy
from .queries import (
    consumed_evidence_ref_ids,
    query_open_research_dedup_keys,
    query_triggers_by_dedup_key,
)
from .serialization import (
    adaptation_assessment_v1_from_dict,
    adaptation_assessment_v1_to_dict,
    adaptation_campaign_v1_from_dict,
    adaptation_campaign_v1_to_dict,
    adaptation_event_v1_from_dict,
    adaptation_event_v1_to_dict,
    adaptation_policy_v1_from_dict,
    adaptation_policy_v1_to_dict,
    research_trigger_v1_from_dict,
    research_trigger_v1_to_dict,
)
from .service import AdaptationService
from .types import (
    ADAPTATION_IMPLEMENTATION_VERSION,
    AdaptationAction,
    AdaptationAssessmentResult,
    AdaptationAssessmentV1,
    AdaptationCampaignV1,
    AdaptationEventType,
    AdaptationEventV1,
    AdaptationEvidenceClass,
    AdaptationEvidenceType,
    AdaptationPolicyV1,
    AdaptationReasonCode,
    ResearchPriority,
    ResearchTriggerV1,
    SuggestedResearchClass,
)

__all__ = [
    "ADAPTATION_IMPLEMENTATION_VERSION",
    "AdaptationAction",
    "AdaptationAssessmentResult",
    "AdaptationAssessmentV1",
    "AdaptationCampaignV1",
    "AdaptationContext",
    "AdaptationEngine",
    "AdaptationError",
    "AdaptationEventType",
    "AdaptationEventV1",
    "AdaptationEvidenceClass",
    "AdaptationEvidenceType",
    "AdaptationPolicyV1",
    "AdaptationService",
    "AdaptationReasonCode",
    "EvidenceBundle",
    "NormalizedEvidence",
    "ResearchPriority",
    "ResearchTriggerV1",
    "SuggestedResearchClass",
    "adaptation_assessment_v1_from_dict",
    "adaptation_assessment_v1_to_dict",
    "adaptation_campaign_v1_from_dict",
    "adaptation_campaign_v1_to_dict",
    "adaptation_event_v1_from_dict",
    "adaptation_event_v1_to_dict",
    "adaptation_policy_v1_from_dict",
    "adaptation_policy_v1_to_dict",
    "build_adaptation_policy",
    "consumed_evidence_ref_ids",
    "derive_adaptation_assessment_id",
    "derive_adaptation_campaign_id",
    "derive_adaptation_event_id",
    "derive_adaptation_policy_id",
    "derive_dedup_key",
    "derive_research_trigger_id",
    "query_open_research_dedup_keys",
    "query_triggers_by_dedup_key",
    "register_finding_from_trigger",
    "research_trigger_v1_from_dict",
    "research_trigger_v1_to_dict",
]
