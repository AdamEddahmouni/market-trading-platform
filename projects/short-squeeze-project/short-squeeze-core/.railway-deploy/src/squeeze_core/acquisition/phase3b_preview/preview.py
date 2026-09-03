"""Build the deterministic Batch 09 preview from frozen inputs.

Inputs are read-only: the committed Batch 01 Phase 3B registry and the private Batch 08
Phase 3A freeze. Nothing is written here; writing is the CLI's job, and only ever to an
isolated dry-run location.

The detection status is *executed* by the existing Phase 3B policy engine on the frozen
Batch 08 results. It is never assigned, never inferred from a substitute rule, and never
overridden.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path

from squeeze_core.evaluation import RuleOutcome
from squeeze_core.evaluation.serialization import deserialize_candidate_evaluation
from squeeze_core.research.detection import evaluate_research_detection
from squeeze_core.research.models import (
    CandidateCaseRegistry,
    CandidateCaseRegistryEntry,
    CandidateCaseStatus,
)
from squeeze_core.research.policies import load_detection_policy

from .contract import (
    ADDED_LIMITATIONS,
    ALLOWED_MUTABLE_FIELDS,
    IMMUTABLE_FIELDS,
    PREVIEW_REGISTRY_VERSION,
    RETIRED_LIMITATION,
    audit_phase3b_contract,
)
from .diff import build_field_change_frequency, build_registry_field_diff
from .models import (
    DETECTION_POLICY_VERSION,
    CandidateRevisionPreview,
    OutcomeStatus,
    PreviewDecision,
    RegistryRevisionPreview,
    ResearchClassificationStatus,
)

#: Batch 01 discovery order. Identity-bearing: never re-sorted.
SOURCE_ORDER: tuple[str, ...] = (
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
    "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
)

SOURCE_CASE_IDS: tuple[str, ...] = tuple(
    f"BATCH01_{symbol}_20260718" for symbol in SOURCE_ORDER
)

#: Relative reference the preview registry declares, resolved by the existing
#: ``research.io.resolve_artifact_path`` against the preview registry's own directory.
_REQUEST_REFERENCE = "../phase3a/batch-08/requests/{case_id}.json"
_RESULT_REFERENCE = "../phase3a/batch-08/results/{case_id}.json"


class PreviewInputError(ValueError):
    """Raised when a frozen input is absent, mismatched, or internally inconsistent."""


def _sha256(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest(), len(payload)


def build_preview_entry(
    entry: CandidateCaseRegistryEntry,
    *,
    evaluation_as_of: datetime,
    request_path: str,
    result_path: str,
) -> CandidateCaseRegistryEntry:
    """Return the previewed entry for one candidate.

    Exactly the six preregistered fields move. Everything else is copied through, and
    ``outcome_observation_path`` stays ``None`` by construction.
    """
    if entry.outcome_observation_path is not None:
        raise PreviewInputError("BATCH09_SOURCE_ENTRY_ALREADY_HAS_OUTCOME")
    if entry.evaluation_request_path is not None or entry.evaluation_result_path is not None:
        raise PreviewInputError("BATCH09_SOURCE_ENTRY_ALREADY_EVALUATED")

    limitations = tuple(
        item for item in entry.limitations if item != RETIRED_LIMITATION
    ) + ADDED_LIMITATIONS

    values = entry.model_dump(mode="python", exclude={"deterministic_id"})
    values.update({
        "evaluation_request_path": request_path,
        "evaluation_result_path": result_path,
        "evaluation_as_of": evaluation_as_of,
        "case_status": CandidateCaseStatus.EVALUATION_ONLY,
        "limitations": limitations,
        # Outcome truth is untouched.
        "outcome_observation_path": None,
    })
    return CandidateCaseRegistryEntry.model_validate(values)


def _detection_for(result_path: Path):
    """Execute the unchanged Phase 3B detection policy on a frozen Batch 08 result."""
    evaluation = deserialize_candidate_evaluation(result_path.read_bytes())
    policy = load_detection_policy(DETECTION_POLICY_VERSION)
    detection = evaluate_research_detection(evaluation, policy)
    by_rule = {item.rule_id: item for item in evaluation.rule_results}
    required = tuple(
        (rule_id, by_rule[rule_id].outcome.value) for rule_id in policy.required_rule_ids
    )
    reasons = tuple(
        f"REQUIRED_RULE_{outcome}:{rule_id}"
        for rule_id, outcome in required
        if outcome != RuleOutcome.PASS.value
    ) or ("ALL_REQUIRED_RULES_PASS",)
    return evaluation, detection, required, reasons


def build_registry_revision_preview(
    *,
    source_registry: CandidateCaseRegistry,
    freeze_root: Path,
    freeze_summary: dict,
) -> tuple[RegistryRevisionPreview, CandidateCaseRegistry]:
    """Build the whole Batch 09 preview plus the preview registry document.

    ``freeze_root`` is the Batch 08 private freeze directory; ``freeze_summary`` is its
    ``batch-summary.json``. Neither is mutated.
    """
    audit = audit_phase3b_contract()

    by_case = {item["case_id"]: item for item in freeze_summary["cases"]}
    missing = tuple(cid for cid in SOURCE_CASE_IDS if cid not in by_case)
    if missing:
        raise PreviewInputError(f"BATCH09_FREEZE_CASE_MISSING:{','.join(missing)}")

    source_by_case = {item.case_id: item for item in source_registry.entries}
    absent = tuple(cid for cid in SOURCE_CASE_IDS if cid not in source_by_case)
    if absent:
        raise PreviewInputError(f"BATCH09_REGISTRY_CASE_MISSING:{','.join(absent)}")

    boundary_time = datetime.fromisoformat(
        str(freeze_summary["boundary_time"]).replace("Z", "+00:00")
    )

    candidates = []
    diffs = []
    preview_entries = []

    for case_id in SOURCE_CASE_IDS:
        record = by_case[case_id]
        entry = source_by_case[case_id]

        request_file = freeze_root / "requests" / f"{case_id}.json"
        result_file = freeze_root / "results" / f"{case_id}.json"
        request_sha, request_len = _sha256(request_file)
        result_sha, result_len = _sha256(result_file)

        declared = record["phase3a_request_artifact"]
        if request_sha != declared["sha256"] or request_len != declared["byte_length"]:
            raise PreviewInputError(f"BATCH09_REQUEST_HASH_MISMATCH:{case_id}")
        declared = record["phase3a_result_artifact"]
        if result_sha != declared["sha256"] or result_len != declared["byte_length"]:
            raise PreviewInputError(f"BATCH09_RESULT_HASH_MISMATCH:{case_id}")

        evaluation, detection, required, reasons = _detection_for(result_file)
        if evaluation.as_of != boundary_time:
            raise PreviewInputError(f"BATCH09_BOUNDARY_MISMATCH:{case_id}")
        if evaluation.symbol != entry.symbol:
            raise PreviewInputError(f"BATCH09_SYMBOL_MISMATCH:{case_id}")

        preview_entry = build_preview_entry(
            entry,
            evaluation_as_of=evaluation.as_of,
            request_path=_REQUEST_REFERENCE.format(case_id=case_id),
            result_path=_RESULT_REFERENCE.format(case_id=case_id),
        )
        preview_entries.append(preview_entry)

        diff = build_registry_field_diff(entry, preview_entry)
        diffs.append(diff)

        changed = tuple(
            item.field_name for item in diff.changes
            if item.change_kind.value in {"ADDED", "CHANGED"}
        )
        unchanged = tuple(
            item.field_name for item in diff.changes
            if item.change_kind.value in {"UNCHANGED", "FORBIDDEN_TO_CHANGE"}
        )

        candidates.append(CandidateRevisionPreview(
            case_id=case_id,
            symbol=entry.symbol,
            current_registry_candidate_id=str(entry.deterministic_id),
            preview_registry_candidate_id=str(preview_entry.deterministic_id),
            candidate_identity_changed=(
                str(entry.deterministic_id) != str(preview_entry.deterministic_id)
            ),
            current_evaluation_reference=None,
            preview_evaluation_request_id=record["phase3a_request_id"],
            preview_evaluation_result_id=record["phase3a_result_id"],
            preview_evaluation_request_sha256=request_sha,
            preview_evaluation_result_sha256=result_sha,
            preview_evaluation_request_path=preview_entry.evaluation_request_path,
            preview_evaluation_result_path=preview_entry.evaluation_result_path,
            frozen_boundary_id=record["boundary_id"],
            frozen_boundary_time=boundary_time,
            discovery_provenance_unchanged=all(
                getattr(entry, name) == getattr(preview_entry, name)
                for name in IMMUTABLE_FIELDS
            ),
            global_preflight_status=record["global_preflight_status"],
            phase3a_freeze_status=record["freeze_status"],
            phase3a_leakage_status=record["leakage_audit_status"],
            research_detection_status=detection.status.value,
            research_detection_reason=reasons,
            required_rule_outcomes=required,
            outcome_status=OutcomeStatus.OUTCOME_INCOMPLETE_NO_VALID_FORWARD_EVIDENCE,
            outcome_path=None,
            research_classification_status=(
                ResearchClassificationStatus.NOT_PRODUCED_OUTCOME_INCOMPLETE
            ),
            changed_fields=changed,
            unchanged_fields=unchanged,
            # Structurally publishable; scientifically still detection- and
            # outcome-incomplete. Those are separate claims.
            compatibility_status=PreviewDecision.PREVIEW_COMPATIBLE_WITH_LIMITATIONS,
            publication_ready_if_approved=True,
        ))

    preview_registry = CandidateCaseRegistry(
        registry_version=PREVIEW_REGISTRY_VERSION,
        entries=tuple(preview_entries),
    )

    def _counts(values) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(values).items()))

    preview = RegistryRevisionPreview(
        source_registry_version=source_registry.registry_version,
        source_registry_id=str(source_registry.deterministic_id),
        preview_registry_version=preview_registry.registry_version,
        preview_registry_id=str(preview_registry.deterministic_id),
        boundary_time=boundary_time,
        contract_audit=audit,
        source_order=SOURCE_CASE_IDS,
        candidates=tuple(candidates),
        diffs=tuple(diffs),
        field_change_frequency=build_field_change_frequency(tuple(diffs)),
        detection_status_counts=_counts(
            item.research_detection_status for item in candidates
        ),
        outcome_status_counts=_counts(item.outcome_status.value for item in candidates),
        classification_status_counts=_counts(
            item.research_classification_status.value for item in candidates
        ),
        compatibility_status_counts=_counts(
            item.compatibility_status.value for item in candidates
        ),
    )
    return preview, preview_registry


__all__ = [
    "ALLOWED_MUTABLE_FIELDS",
    "SOURCE_CASE_IDS",
    "SOURCE_ORDER",
    "PreviewInputError",
    "build_preview_entry",
    "build_registry_revision_preview",
]
