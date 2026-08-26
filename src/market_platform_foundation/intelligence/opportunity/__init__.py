"""Governed opportunity engine (BUILD 21)."""

from .engine import OpportunityEngine, forecast_expiry_ns, forecast_matches_champion
from .errors import OpportunityError
from .identity import (
    context_identity_payload,
    derive_opportunity_assessment_id,
    derive_opportunity_id,
    derive_opportunity_policy_id,
    opportunity_policy_identity_payload,
)
from .policy import build_opportunity_policy
from .serialization import (
    opportunity_assessment_v1_from_dict,
    opportunity_assessment_v1_to_dict,
    opportunity_context_from_dict,
    opportunity_context_to_dict,
    opportunity_policy_v1_from_dict,
    opportunity_policy_v1_to_dict,
)
from .types import (
    OPPORTUNITY_IMPLEMENTATION_VERSION,
    AssessmentAction,
    AssessmentReasonCode,
    EconomicValueStatus,
    OpportunityAssessmentResult,
    OpportunityAssessmentV1,
    OpportunityContext,
    OpportunityPolicyV1,
)

__all__ = [
    "OPPORTUNITY_IMPLEMENTATION_VERSION",
    "AssessmentAction",
    "AssessmentReasonCode",
    "EconomicValueStatus",
    "OpportunityAssessmentResult",
    "OpportunityAssessmentV1",
    "OpportunityContext",
    "OpportunityEngine",
    "OpportunityError",
    "OpportunityPolicyV1",
    "build_opportunity_policy",
    "context_identity_payload",
    "derive_opportunity_assessment_id",
    "derive_opportunity_id",
    "derive_opportunity_policy_id",
    "forecast_expiry_ns",
    "forecast_matches_champion",
    "opportunity_assessment_v1_from_dict",
    "opportunity_assessment_v1_to_dict",
    "opportunity_context_from_dict",
    "opportunity_context_to_dict",
    "opportunity_policy_identity_payload",
    "opportunity_policy_v1_from_dict",
    "opportunity_policy_v1_to_dict",
]
