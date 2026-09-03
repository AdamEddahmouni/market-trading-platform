"""Phase 3D Batch 08 — deterministic Phase 3A request and result freeze.

Constructs canonical Phase 3A requests for the 13 frozen Batch 01 cases using only
evidence Batch 07 declared operation-specifically admissible, executes the *existing*
Phase 3A evaluator, and freezes both bytes deterministically.

This package never publishes Phase 3B, never opens a forward-window or outcome artifact,
never fetches data, never imports ``ibapi``, and never assigns a rule outcome itself.
"""

from .evidence_adapter import (
    EvidenceAccessLog,
    ForwardArtifactAccessError,
    NonDetectionContextArtifactError,
    OutcomeArtifactAccessError,
    load_detection_context_bars,
)
from .freeze import (
    CaseFreezeOutputs,
    batch07_readiness,
    freeze_case,
    freeze_cohort,
    load_phase3a_policy,
)
from .metric_adapter import build_percentage_return, metric_window
from .models import (
    ADMISSIBLE_METRIC_NAME,
    FREEZE_POLICY_VERSION,
    GLOBAL_PREFLIGHT_VERDICT,
    PHASE3A_EVALUATION_VERSION,
    PHASE3A_POLICY_VERSION,
    SCHEMA_VERSION,
    BlockingReasonCode,
    CaseFreezeRecord,
    EvidenceAssociation,
    FreezeReport,
    FreezeStatus,
    FrozenArtifactRef,
    OutcomeCount,
    PublicationReadinessPreview,
    ReceiptModelingPolicy,
    RuleOutcomeMatrixRow,
    RuleOutcomeRecord,
    SensitivitySummary,
    TemporalSelection,
    TimestampInterpretation,
)
from .readiness_adapter import build_readiness_records, requested_domains
from .report import build_freeze_report, render_markdown, rule_matrix, sensitivity_summary
from .request_builder import FROZEN_PROVIDER_SCOPE, build_request
from .result_runner import rule_outcome_records, run_evaluation
from .serialization import artifact_ref, freeze_id, request_identity, result_identity, serialize

__all__ = [
    "ADMISSIBLE_METRIC_NAME",
    "FREEZE_POLICY_VERSION",
    "FROZEN_PROVIDER_SCOPE",
    "GLOBAL_PREFLIGHT_VERDICT",
    "PHASE3A_EVALUATION_VERSION",
    "PHASE3A_POLICY_VERSION",
    "SCHEMA_VERSION",
    "BlockingReasonCode",
    "CaseFreezeOutputs",
    "CaseFreezeRecord",
    "EvidenceAccessLog",
    "EvidenceAssociation",
    "ForwardArtifactAccessError",
    "FreezeReport",
    "FreezeStatus",
    "FrozenArtifactRef",
    "NonDetectionContextArtifactError",
    "OutcomeArtifactAccessError",
    "OutcomeCount",
    "PublicationReadinessPreview",
    "ReceiptModelingPolicy",
    "RuleOutcomeMatrixRow",
    "RuleOutcomeRecord",
    "SensitivitySummary",
    "TemporalSelection",
    "TimestampInterpretation",
    "artifact_ref",
    "batch07_readiness",
    "build_freeze_report",
    "build_percentage_return",
    "build_readiness_records",
    "build_request",
    "freeze_case",
    "freeze_cohort",
    "freeze_id",
    "load_detection_context_bars",
    "load_phase3a_policy",
    "metric_window",
    "render_markdown",
    "request_identity",
    "requested_domains",
    "result_identity",
    "rule_matrix",
    "rule_outcome_records",
    "run_evaluation",
    "sensitivity_summary",
    "serialize",
]
