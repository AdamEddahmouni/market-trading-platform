"""BUILD 12 expert council and evidence blackboard."""

from __future__ import annotations

from .barrier import BlindExecutionBarrier
from .blackboard import BlackboardSnapshot, publish_blackboard_snapshot
from .comparison import DEFAULT_COMPARISON_REGISTRY, ComparisonAdapterRegistry
from .deliberation import DeliberationGate
from .errors import (
    BlackboardNotReadyError,
    CouncilConfigurationError,
    CouncilError,
    CouncilIntegrityError,
    CouncilStateError,
    ProvenanceResolutionError,
)
from .identity import (
    derive_blackboard_id,
    derive_council_id,
    derive_deliberation_request_id,
    derive_relation_report_id,
    derive_source_signature_id,
)
from .models import (
    BlackboardPhase,
    ComparableEvidenceView,
    CouncilDeliberationRequest,
    CouncilDiagnostic,
    CouncilDiagnosticCode,
    CouncilExecutionPhase,
    CouncilParticipant,
    CouncilPhase,
    CouncilResult,
    DeliberationContext,
    DeliberationDecision,
    DeliberationReasonCode,
    EvidenceRelation,
    EvidenceRelationReport,
    EvidenceRelationType,
    ParticipantOutcome,
    ProvenanceGroup,
    SourceIndependence,
    SourceOverlap,
    SourceSignature,
)
from .orchestrator import BlindCouncilOrchestrator, create_council_orchestrator
from .plan import CouncilPlan, canonicalize_participants
from .policy import DEFAULT_COUNCIL_POLICY, CouncilPolicy
from .provenance import EvidenceProvenanceResolver
from .registry import DEFAULT_SPECIALIST_REGISTRY, DeliberatingSpecialist, SpecialistRegistry
from .relations import EvidenceRelationAnalyzer

__all__ = [
    "BlackboardNotReadyError",
    "BlackboardPhase",
    "BlackboardSnapshot",
    "BlindCouncilOrchestrator",
    "BlindExecutionBarrier",
    "ComparableEvidenceView",
    "ComparisonAdapterRegistry",
    "CouncilConfigurationError",
    "CouncilDeliberationRequest",
    "CouncilDiagnostic",
    "CouncilDiagnosticCode",
    "CouncilError",
    "CouncilExecutionPhase",
    "CouncilIntegrityError",
    "CouncilParticipant",
    "CouncilPhase",
    "CouncilPlan",
    "CouncilPolicy",
    "CouncilResult",
    "CouncilStateError",
    "DEFAULT_COMPARISON_REGISTRY",
    "DEFAULT_COUNCIL_POLICY",
    "DEFAULT_SPECIALIST_REGISTRY",
    "DeliberatingSpecialist",
    "DeliberationContext",
    "DeliberationDecision",
    "DeliberationGate",
    "DeliberationReasonCode",
    "EvidenceProvenanceResolver",
    "EvidenceRelation",
    "EvidenceRelationAnalyzer",
    "EvidenceRelationReport",
    "EvidenceRelationType",
    "ParticipantOutcome",
    "ProvenanceGroup",
    "ProvenanceResolutionError",
    "SourceIndependence",
    "SourceOverlap",
    "SourceSignature",
    "SpecialistRegistry",
    "canonicalize_participants",
    "create_council_orchestrator",
    "derive_blackboard_id",
    "derive_council_id",
    "derive_deliberation_request_id",
    "derive_relation_report_id",
    "derive_source_signature_id",
    "publish_blackboard_snapshot",
]
