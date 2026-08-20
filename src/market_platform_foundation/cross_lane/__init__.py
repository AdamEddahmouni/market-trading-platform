"""Cross-lane normalized evidence publishing and consumption."""

from .evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    apply_evidence_lag_rules,
    lane_evidence_to_dict,
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
    "lane_evidence_to_dict",
    "load_opportunity_fixture",
    "validate_evidence_dag",
]
