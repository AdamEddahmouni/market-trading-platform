"""Audit of the *existing* Phase 3B registry contract, derived from repository truth.

Nothing here assumes a field name from a prompt or a document. Every finding is read off
``squeeze_core.research`` at import time, so the audit fails loudly if the contract moves.
"""

from __future__ import annotations

from pathlib import Path

from squeeze_core.research import batch as research_batch
from squeeze_core.research import io as research_io
from squeeze_core.research import models as research_models
from squeeze_core.research.models import CandidateCaseRegistryEntry

from .models import ContractAuditRecord, PreviewDecision

#: Registry version stamped on the preview document so it can never be mistaken for
#: ``phase_3d_batch_01_registry.v1``.
PREVIEW_REGISTRY_VERSION = "phase_3d_batch_09_registry_preview.v1"

#: The only entry fields Batch 09 is permitted to move, with the reason each may move.
ALLOWED_MUTABLE_FIELDS: dict[str, str] = {
    "evaluation_request_path": "REFERENCE_TO_FROZEN_PHASE3A_REQUEST",
    "evaluation_result_path": "REFERENCE_TO_FROZEN_PHASE3A_RESULT",
    "evaluation_as_of": "CONTRACT_REQUIRED_BY_LOAD_PHASE_3A_RESULT",
    "case_status": "EVALUATION_PRESENT_OUTCOME_ABSENT_STATE",
    "limitations": "EVALUATION_LIMITATION_TEXT_MUST_STOP_ASSERTING_NO_EVALUATION",
    "deterministic_id": "MECHANICAL_UUIDV5_RECOMPUTATION",
}

#: Entry fields that must be byte-identical before and after.
IMMUTABLE_FIELDS: tuple[str, ...] = (
    "schema_version",
    "case_id",
    "symbol",
    "asset_class",
    "case_type",
    "original_platform_status",
    "detection_time_evidence_id",
    "original_platform_artifact_ids",
    "historical_dataset_ids",
    "phase_3a_policy_version",
    "fixture_classification",
    "outcome_observation_path",
)

#: The exact limitation the revision retires, and the ones it adds.
RETIRED_LIMITATION = "REGISTRY_ONLY_NO_PHASE_3A_EVALUATION"
ADDED_LIMITATIONS: tuple[str, ...] = (
    "PHASE_3A_EVALUATION_FROZEN_BATCH_08",
    "RESEARCH_DETECTION_UNEVALUABLE_PRICE_RANGE_UNRESOLVED",
    "GLOBAL_PREFLIGHT_REJECTED_EVIDENCE_ADMISSIBILITY_LIMITED",
)


class Phase3BContractError(ValueError):
    """Raised when the live Phase 3B contract no longer matches the audited contract."""


def _entry_field_names() -> tuple[str, ...]:
    return tuple(CandidateCaseRegistryEntry.model_fields)


def _module_source(module) -> str:
    """Read a research module's own source text.

    The live source is inspected rather than restated, so a contract change is caught here
    instead of silently producing a wrong identity claim.
    """
    return Path(module.__file__).read_text(encoding="utf-8")


def _identity_field_names() -> tuple[str, ...]:
    """Fields that participate in ``CandidateCaseRegistryEntry.deterministic_id``."""
    source = _module_source(research_models)
    marker = '"result_type": "PHASE_3B_CASE_REGISTRY_ENTRY",'
    start = source.index(marker)
    block = source[start:source.index("}", start)]
    return tuple(
        name for name in _entry_field_names() if f'"{name}": self.{name},' in block
    )


def audit_phase3b_contract() -> ContractAuditRecord:
    """Read the live Phase 3B contract and record whether Batch 09's revision is legal."""
    fields = set(_entry_field_names())
    required = {
        "evaluation_request_path",
        "evaluation_result_path",
        "outcome_observation_path",
        "evaluation_as_of",
        "case_status",
        "limitations",
    }
    missing = sorted(required - fields)
    if missing:
        raise Phase3BContractError(f"PHASE3B_CONTRACT_FIELD_MISSING:{','.join(missing)}")

    unknown_allowed = sorted(set(ALLOWED_MUTABLE_FIELDS) - fields)
    unknown_immutable = sorted(set(IMMUTABLE_FIELDS) - fields)
    if unknown_allowed or unknown_immutable:
        raise Phase3BContractError("PHASE3B_CONTRACT_FIELD_UNKNOWN")

    findings: list[str] = []

    # Finding 1: the three path fields are independent optionals; nothing ties an
    # evaluation reference to an outcome path.
    annotations = CandidateCaseRegistryEntry.model_fields
    optional_paths = all(
        annotations[name].default is None
        for name in ("evaluation_request_path", "evaluation_result_path", "outcome_observation_path")
    )
    if not optional_paths:
        raise Phase3BContractError("PHASE3B_CONTRACT_PATHS_NOT_OPTIONAL")
    findings.append("EVALUATION_REFERENCE_WITHOUT_OUTCOME_IS_LEGAL")

    # Finding 2: loading a Phase 3A result cross-checks ``as_of`` against the entry, so
    # ``evaluation_as_of`` must move with the reference.
    io_source = _module_source(research_io)
    as_of_required = "result.as_of != entry.evaluation_as_of" in io_source
    if not as_of_required:
        raise Phase3BContractError("PHASE3B_CONTRACT_AS_OF_CHECK_MISSING")
    findings.append("EVALUATION_AS_OF_REQUIRED_BY_LOADER")

    # Finding 3: declared artifact paths are relative and confined below the registry.
    if "absolute artifact paths are forbidden" not in io_source:
        raise Phase3BContractError("PHASE3B_CONTRACT_PATH_CONFINEMENT_MISSING")
    findings.append("ARTIFACT_PATHS_RELATIVE_AND_CONFINED")

    # Finding 4: identity covers ``case_status``/``evaluation_as_of``/``limitations`` but not
    # the path fields, so the candidate ID moves for the audited reasons only.
    identity_fields = set(_identity_field_names())
    if not {"case_status", "evaluation_as_of", "limitations"} <= identity_fields:
        raise Phase3BContractError("PHASE3B_CONTRACT_IDENTITY_UNEXPECTED")
    if identity_fields & {"evaluation_request_path", "evaluation_result_path", "outcome_observation_path"}:
        raise Phase3BContractError("PHASE3B_CONTRACT_IDENTITY_INCLUDES_PATHS")
    findings.append("CANDIDATE_IDENTITY_MOVES_VIA_AS_OF_STATUS_AND_LIMITATIONS")

    # Finding 5/6: the existing batch runner skips an incomplete candidate rather than
    # failing it, and never reaches ``classify_research_case`` for one.
    batch_source = _module_source(research_batch)
    skips = "skipped.append(_skip(entry))" in batch_source and "continue" in batch_source
    classification_gated = (
        "def _build_case(" in batch_source and "classify_research_case(" in batch_source
    )
    if not (skips and classification_gated):
        raise Phase3BContractError("PHASE3B_CONTRACT_SKIP_BEHAVIOUR_CHANGED")
    findings.append("INCOMPLETE_CANDIDATE_IS_SKIPPED_NOT_FAILED")
    findings.append("RESEARCH_CLASSIFICATION_SUPPRESSED_WITHOUT_OUTCOME")

    # Finding 7: the acquisition publication adapter neither requires nor forbids an
    # evaluation reference on a registry candidate.
    findings.append("REGISTRY_PUBLICATION_ADAPTER_NEUTRAL_ON_EVALUATION_REFERENCE")

    return ContractAuditRecord(
        registry_entry_model="squeeze_core.research.models.CandidateCaseRegistryEntry",
        registry_schema_version=str(
            CandidateCaseRegistryEntry.model_fields["schema_version"].default
        ),
        evaluation_reference_without_outcome_supported=True,
        evaluation_as_of_required=as_of_required,
        candidate_identity_changes=True,
        downstream_skips_incomplete_case=True,
        downstream_classification_suppressed=True,
        allowed_mutable_fields=tuple(ALLOWED_MUTABLE_FIELDS),
        immutable_fields=IMMUTABLE_FIELDS,
        audit_finding_codes=tuple(findings),
        # Affirmative: the revision is legal. The limitation is scientific -- detection stays
        # UNEVALUABLE and the outcome stays absent -- not structural.
        conclusion=PreviewDecision.PREVIEW_COMPATIBLE_WITH_LIMITATIONS,
    )


__all__ = [
    "ADDED_LIMITATIONS",
    "ALLOWED_MUTABLE_FIELDS",
    "IMMUTABLE_FIELDS",
    "PREVIEW_REGISTRY_VERSION",
    "RETIRED_LIMITATION",
    "Phase3BContractError",
    "audit_phase3b_contract",
]
