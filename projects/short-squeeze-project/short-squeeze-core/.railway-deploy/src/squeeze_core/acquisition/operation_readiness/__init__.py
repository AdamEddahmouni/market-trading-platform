"""Batch 07 operation-specific evidence admissibility and Phase 3A readiness audit.

A strictly narrower concept than the Batch 04 global preflight (which stays
PREFLIGHT_REJECTED): it answers whether the frozen Batch 05 detection-context bars can
support a *specific* operation under explicitly stated constraints. Offline, outcome-
blind, and never reads OHLCV or evaluates a Phase 3A rule.
"""

from .admissibility import (
    AdmissibilityContext,
    assess_operation,
    context_from_resolved,
)
from .dependencies import (
    DETECTION_CONTEXT_PRESENT_DOMAINS,
    ENABLED_RULE_IDS,
    PHASE2_OPERATION_DEPENDENCIES,
    PHASE3A_RULE_DEPENDENCIES,
)
from .evidence_inputs import (
    FROZEN_BOUNDARY,
    FROZEN_COHORT,
    OhlcvAccessError,
    boundary_id_for,
    forward_artifact_identity,
    load_detection_context_evidence,
)
from .models import (
    OPERATION_READINESS_POLICY_VERSION,
    SCHEMA_VERSION,
    SEMANTIC_RESOLUTION_POLICY_VERSION,
    TIMESTAMP_UNCERTAINTY_POLICY,
    AdmissibilityStatus,
    ArtifactCoverage,
    CaseOperationReadiness,
    OperationAdmissibility,
    OperationDependency,
    OperationKind,
    OperationReadinessReport,
    Phase3ARequestReadiness,
    Phase3ARuleDependencyRecord,
    ReadinessFrequencySummary,
    ReasonCode,
    SemanticDependency,
    TimestampUncertaintyEnvelope,
)
from .phase3a_readiness import (
    assess_request_readiness,
    build_all_rule_records,
    build_rule_record,
    required_semantic_fields,
)
from .report import build_report
from .serialization import render_markdown, serialize_report
from .timestamp_uncertainty import (
    build_envelope,
    definitely_completed_before,
    definitely_starts_after,
    straddles_boundary,
)

__all__ = [
    "SCHEMA_VERSION",
    "OPERATION_READINESS_POLICY_VERSION",
    "SEMANTIC_RESOLUTION_POLICY_VERSION",
    "TIMESTAMP_UNCERTAINTY_POLICY",
    "AdmissibilityStatus",
    "Phase3ARequestReadiness",
    "OperationKind",
    "ReasonCode",
    "SemanticDependency",
    "OperationDependency",
    "OperationAdmissibility",
    "TimestampUncertaintyEnvelope",
    "ArtifactCoverage",
    "Phase3ARuleDependencyRecord",
    "CaseOperationReadiness",
    "ReadinessFrequencySummary",
    "OperationReadinessReport",
    "AdmissibilityContext",
    "assess_operation",
    "context_from_resolved",
    "PHASE2_OPERATION_DEPENDENCIES",
    "PHASE3A_RULE_DEPENDENCIES",
    "DETECTION_CONTEXT_PRESENT_DOMAINS",
    "ENABLED_RULE_IDS",
    "FROZEN_BOUNDARY",
    "FROZEN_COHORT",
    "OhlcvAccessError",
    "boundary_id_for",
    "forward_artifact_identity",
    "load_detection_context_evidence",
    "assess_request_readiness",
    "build_all_rule_records",
    "build_rule_record",
    "required_semantic_fields",
    "build_report",
    "render_markdown",
    "serialize_report",
    "build_envelope",
    "definitely_completed_before",
    "definitely_starts_after",
    "straddles_boundary",
]
