"""Cross-lane normalized evidence publishing and consumption."""

from .evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    apply_evidence_lag_rules,
    inference_kind_for_provenance,
    lane_evidence_from_dict,
    lane_evidence_to_dict,
    observation_clock_key,
    observed_at_presence,
    validate_evidence_dag,
)
from .fusion import (
    FUSION_METHOD,
    OPPORTUNITY_VERSION,
    build_opportunity_snapshot,
    fuse_opportunity_v1,
    load_opportunity_fixture,
)
from .opportunity import (
    CostInput,
    FusedOpportunity,
    LiquidityInput,
    OpportunityQualityFlag,
    PayoffInput,
    ProbabilityInput,
    SQUEEZE_ALIGNED_TEMPLATES,
)

__all__ = [
    "CostInput",
    "EvidenceProvenanceClass",
    "EvidenceSignal",
    "FUSION_METHOD",
    "FusedOpportunity",
    "LaneId",
    "LiquidityInput",
    "NormalizedLaneEvidence",
    "OPPORTUNITY_VERSION",
    "OpportunityQualityFlag",
    "PayoffInput",
    "ProbabilityInput",
    "SQUEEZE_ALIGNED_TEMPLATES",
    "apply_evidence_lag_rules",
    "build_opportunity_snapshot",
    "fuse_opportunity_v1",
    "inference_kind_for_provenance",
    "lane_evidence_from_dict",
    "lane_evidence_to_dict",
    "load_opportunity_fixture",
    "observation_clock_key",
    "observed_at_presence",
    "validate_evidence_dag",
]
