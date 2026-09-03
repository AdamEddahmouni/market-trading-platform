"""Frozen contracts for the Batch 09 Phase 3B registry revision preview.

Every model here records *what a revision would change*, never a market value and never an
outcome. A structural validator refuses any field whose name suggests a price, a return, a
forward value, an outcome, a score, a rank, or a recommendation, so the preview cannot
accidentally become a trading artifact.

Identity is a UUIDv5 over canonical JSON of frozen pre-outcome inputs only, reusing the
acquisition ``_FrozenAcquisitionModel`` base. The eventual review decision is deliberately
absent from every identity: governance must not retroactively alter scientific identity.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from ..models import _FrozenAcquisitionModel

SCHEMA_VERSION = "1.0.0"

#: Batch 09's own policy version. Bumping it changes every preview identity.
PREVIEW_POLICY_VERSION = "phase_3d_phase3b_registry_preview_policy.v1"

#: The Phase 3B detection policy this batch executes unchanged.
DETECTION_POLICY_VERSION = "phase_3b_research_detection_policy.v1"

#: The unchanged Batch 04 global preflight verdict, echoed into every record.
GLOBAL_PREFLIGHT_VERDICT = "PREFLIGHT_REJECTED"

#: Substrings that may never appear in a preview field name.
_FORBIDDEN_FIELD_SUBSTRINGS = (
    "score", "rank", "recommend", "signal_strength", "target_price", "pnl", "profit",
    "return_value", "ohlcv", "open_price", "high_price", "low_price", "close_price",
    "volume_value", "forward_price", "outcome_value", "outcome_label", "move_percent",
)


class PreviewDecision(StrEnum):
    """Whether a candidate can safely be revised to reference its frozen evaluation.

    ``PREVIEW_COMPATIBLE_WITH_LIMITATIONS`` is an affirmative answer. It says the revision is
    structurally and scientifically safe *and* that a named limitation survives it -- here,
    that research detection stays ``UNEVALUABLE`` and the outcome stays absent. Compatibility
    and detection completeness are separate questions and must not be conflated.
    """

    PREVIEW_COMPATIBLE = "PREVIEW_COMPATIBLE"
    PREVIEW_COMPATIBLE_WITH_LIMITATIONS = "PREVIEW_COMPATIBLE_WITH_LIMITATIONS"
    PREVIEW_BLOCKED_SCHEMA = "PREVIEW_BLOCKED_SCHEMA"
    PREVIEW_BLOCKED_IDENTITY = "PREVIEW_BLOCKED_IDENTITY"
    PREVIEW_BLOCKED_POLICY = "PREVIEW_BLOCKED_POLICY"
    PREVIEW_BLOCKED_INTEGRITY = "PREVIEW_BLOCKED_INTEGRITY"


class OutcomeStatus(StrEnum):
    """Outcome completeness. Batch 09 can only ever record the incomplete member."""

    OUTCOME_INCOMPLETE_NO_VALID_FORWARD_EVIDENCE = (
        "OUTCOME_INCOMPLETE_NO_VALID_FORWARD_EVIDENCE"
    )


class ResearchClassificationStatus(StrEnum):
    """Why no TP/FP/TN/FN was produced. Batch 09 never produces one."""

    NOT_PRODUCED_OUTCOME_INCOMPLETE = "NOT_PRODUCED_OUTCOME_INCOMPLETE"


class FieldChangeKind(StrEnum):
    """How a single registry field behaves across the proposed revision."""

    #: Was null/empty before and carries a value in the preview.
    ADDED = "ADDED"
    #: Had a value before and carries a different value in the preview.
    CHANGED = "CHANGED"
    #: Identical before and after, and permitted to change in principle.
    UNCHANGED = "UNCHANGED"
    #: Identical before and after, and forbidden to change by the preregistered plan.
    FORBIDDEN_TO_CHANGE = "FORBIDDEN_TO_CHANGE"


def _reject_forbidden_field_names(cls) -> None:
    for name in cls.model_fields:
        lowered = name.lower()
        for banned in _FORBIDDEN_FIELD_SUBSTRINGS:
            if banned in lowered:
                raise TypeError(
                    f"forbidden preview field name {name!r} (matches {banned!r})"
                )


class _PreviewModel(_FrozenAcquisitionModel):
    """Frozen preview base with a structural guard on field names."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _reject_forbidden_field_names(cls)


class FieldChange(_PreviewModel):
    """One registry field, before and after, rendered as canonical text."""

    schema_version: str = SCHEMA_VERSION
    field_name: str = Field(min_length=1)
    change_kind: FieldChangeKind
    #: Canonical JSON rendering of the current committed value.
    current_value: str
    #: Canonical JSON rendering of the previewed value.
    preview_value: str
    #: Why the field is allowed to move, or why it is pinned.
    rationale_code: str = Field(min_length=1)
    deterministic_id: str | None = None


class CandidateRevisionPreview(_PreviewModel):
    """The full preview record for one of the 13 registry-only candidates."""

    schema_version: str = SCHEMA_VERSION
    preview_policy_version: str = PREVIEW_POLICY_VERSION
    case_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)

    current_registry_candidate_id: str = Field(min_length=1)
    preview_registry_candidate_id: str = Field(min_length=1)
    candidate_identity_changed: bool

    #: Null before the revision; there is no existing evaluation reference.
    current_evaluation_reference: str | None
    preview_evaluation_request_id: str = Field(min_length=1)
    preview_evaluation_result_id: str = Field(min_length=1)
    preview_evaluation_request_sha256: str = Field(min_length=64, max_length=64)
    preview_evaluation_result_sha256: str = Field(min_length=64, max_length=64)
    preview_evaluation_request_path: str = Field(min_length=1)
    preview_evaluation_result_path: str = Field(min_length=1)

    frozen_boundary_id: str = Field(min_length=1)
    frozen_boundary_time: datetime
    discovery_provenance_unchanged: bool

    global_preflight_status: str = Field(min_length=1)
    phase3a_freeze_status: str = Field(min_length=1)
    phase3a_leakage_status: str = Field(min_length=1)

    research_detection_policy_version: str = DETECTION_POLICY_VERSION
    research_detection_status: str = Field(min_length=1)
    research_detection_reason: tuple[str, ...]
    #: Required-rule outcomes exactly as the existing evaluator produced them.
    required_rule_outcomes: tuple[tuple[str, str], ...]

    outcome_status: OutcomeStatus
    #: Always ``None``. There is no valid frozen forward outcome evidence.
    outcome_path: str | None
    research_classification_status: ResearchClassificationStatus

    changed_fields: tuple[str, ...]
    unchanged_fields: tuple[str, ...]
    compatibility_status: PreviewDecision
    publication_ready_if_approved: bool

    phase3b_published: bool = False
    phase3e_started: bool = False
    forward_ohlcv_accessed: bool = False
    outcome_accessed: bool = False

    deterministic_id: str | None = None

    @field_validator("research_detection_reason", "changed_fields", "unchanged_fields")
    @classmethod
    def sort_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def refuse_outcome_and_publication(self) -> "CandidateRevisionPreview":
        if self.outcome_path is not None:
            raise ValueError("BATCH09_OUTCOME_PATH_FORBIDDEN")
        if self.phase3b_published or self.phase3e_started:
            raise ValueError("BATCH09_PUBLICATION_FORBIDDEN")
        if self.forward_ohlcv_accessed or self.outcome_accessed:
            raise ValueError("BATCH09_FORWARD_OR_OUTCOME_ACCESS_FORBIDDEN")
        return self


class RegistryFieldDiff(_PreviewModel):
    """The canonical before/after diff for one candidate."""

    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    changes: tuple[FieldChange, ...]
    deterministic_id: str | None = None

    @field_validator("changes")
    @classmethod
    def sort_changes(cls, value: tuple[FieldChange, ...]) -> tuple[FieldChange, ...]:
        return tuple(sorted(value, key=lambda item: item.field_name))


class FieldChangeFrequency(_PreviewModel):
    """How often one field changes across the previewed cohort."""

    schema_version: str = SCHEMA_VERSION
    field_name: str = Field(min_length=1)
    change_kind: FieldChangeKind
    case_count: int = Field(ge=0)
    deterministic_id: str | None = None


class ContractAuditRecord(_PreviewModel):
    """The recorded answer to 'can Phase 3B legally reference this evaluation?'."""

    schema_version: str = SCHEMA_VERSION
    preview_policy_version: str = PREVIEW_POLICY_VERSION
    registry_entry_model: str = Field(min_length=1)
    registry_schema_version: str = Field(min_length=1)
    #: True when an evaluation reference is legal with a null outcome path.
    evaluation_reference_without_outcome_supported: bool
    #: True when ``evaluation_as_of`` must be set alongside the evaluation reference.
    evaluation_as_of_required: bool
    #: True when the entry identity moves as a result of the allowed changes.
    candidate_identity_changes: bool
    #: True when the existing batch runner skips rather than fails such a candidate.
    downstream_skips_incomplete_case: bool
    #: True when no research classification is produced for such a candidate.
    downstream_classification_suppressed: bool
    allowed_mutable_fields: tuple[str, ...]
    immutable_fields: tuple[str, ...]
    audit_finding_codes: tuple[str, ...]
    conclusion: PreviewDecision
    deterministic_id: str | None = None

    @field_validator("allowed_mutable_fields", "immutable_fields", "audit_finding_codes")
    @classmethod
    def sort_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))


class RegistryRevisionPreview(_PreviewModel):
    """The whole Batch 09 preview: 13 candidates, their diffs, and the contract audit."""

    schema_version: str = SCHEMA_VERSION
    preview_policy_version: str = PREVIEW_POLICY_VERSION
    source_registry_version: str = Field(min_length=1)
    source_registry_id: str = Field(min_length=1)
    preview_registry_version: str = Field(min_length=1)
    preview_registry_id: str = Field(min_length=1)
    boundary_time: datetime
    contract_audit: ContractAuditRecord
    #: Source order is preserved exactly as Batch 01 discovered the cases.
    source_order: tuple[str, ...]
    candidates: tuple[CandidateRevisionPreview, ...]
    diffs: tuple[RegistryFieldDiff, ...]
    field_change_frequency: tuple[FieldChangeFrequency, ...]
    detection_status_counts: tuple[tuple[str, int], ...]
    outcome_status_counts: tuple[tuple[str, int], ...]
    classification_status_counts: tuple[tuple[str, int], ...]
    compatibility_status_counts: tuple[tuple[str, int], ...]
    phase3b_published: bool = False
    phase3e_started: bool = False
    deterministic_id: str | None = None

    @model_validator(mode="after")
    def refuse_publication(self) -> "RegistryRevisionPreview":
        if self.phase3b_published or self.phase3e_started:
            raise ValueError("BATCH09_PUBLICATION_FORBIDDEN")
        if len(self.candidates) != len(self.source_order):
            raise ValueError("BATCH09_COHORT_SIZE_MISMATCH")
        return self


__all__ = [
    "DETECTION_POLICY_VERSION",
    "GLOBAL_PREFLIGHT_VERDICT",
    "PREVIEW_POLICY_VERSION",
    "SCHEMA_VERSION",
    "CandidateRevisionPreview",
    "ContractAuditRecord",
    "FieldChange",
    "FieldChangeFrequency",
    "FieldChangeKind",
    "OutcomeStatus",
    "PreviewDecision",
    "RegistryFieldDiff",
    "RegistryRevisionPreview",
    "ResearchClassificationStatus",
]
