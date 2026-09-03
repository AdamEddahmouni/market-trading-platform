"""Batch 09: deterministic, non-publishing Phase 3B registry revision preview.

This package answers one question and nothing else: *what would change* in the existing
Phase 3B research registry if the 13 Batch 01 registry-only candidates referenced their
frozen Batch 08 Phase 3A requests and results, while their outcome status stays incomplete.

It is a DRY RUN. It never writes over a canonical Phase 3B artifact, never publishes, never
reads a forward bar, never touches an outcome, and never begins Phase 3E. Every field it
produces is either an identifier, a hash, a status, or a policy version.

The existing Phase 3B contract is reused verbatim: ``CandidateCaseRegistryEntry``,
``phase_3b_research_detection_policy.v1``, ``evaluate_research_detection``,
``run_research_batch``, ``build_research_dataset``, and the existing research serializers.
Nothing in this package re-implements them or assigns a rule outcome, a detection status, an
outcome label, or a research classification.
"""

from .contract import (
    ALLOWED_MUTABLE_FIELDS,
    IMMUTABLE_FIELDS,
    PREVIEW_REGISTRY_VERSION,
    audit_phase3b_contract,
)
from .diff import build_field_change_frequency, build_registry_field_diff
from .models import (
    PREVIEW_POLICY_VERSION,
    CandidateRevisionPreview,
    ContractAuditRecord,
    FieldChange,
    FieldChangeFrequency,
    FieldChangeKind,
    OutcomeStatus,
    PreviewDecision,
    RegistryFieldDiff,
    RegistryRevisionPreview,
    ResearchClassificationStatus,
)
from .preview import build_preview_entry, build_registry_revision_preview
from .publication import DryRunArtifacts, simulate_phase3b_publication

__all__ = [
    "ALLOWED_MUTABLE_FIELDS",
    "IMMUTABLE_FIELDS",
    "PREVIEW_POLICY_VERSION",
    "PREVIEW_REGISTRY_VERSION",
    "CandidateRevisionPreview",
    "ContractAuditRecord",
    "DryRunArtifacts",
    "FieldChange",
    "FieldChangeFrequency",
    "FieldChangeKind",
    "OutcomeStatus",
    "PreviewDecision",
    "RegistryFieldDiff",
    "RegistryRevisionPreview",
    "ResearchClassificationStatus",
    "audit_phase3b_contract",
    "build_field_change_frequency",
    "build_preview_entry",
    "build_registry_field_diff",
    "build_registry_revision_preview",
    "simulate_phase3b_publication",
]
