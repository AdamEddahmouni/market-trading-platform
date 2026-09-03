"""Phase 3B publication dry run and Phase 3C structural compatibility.

The *existing* Phase 3B pipeline is executed against the preview registry: the same batch
runner, the same dataset builder, the same JSON/JSONL/CSV serializers. No second publication
implementation is written, and no canonical artifact is read for writing or written at all --
the caller supplies an isolated output directory.

The honest expected result is a valid, well-formed, **empty-row** dataset: 13 candidates enter
the batch, 13 are skipped for a missing outcome, 0 rows are produced, and no research
classification exists. That is the structural proof that the revision publishes cleanly while
adding no empirical evidence.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from squeeze_core.analysis.cohorts import build_registry_cohort
from squeeze_core.analysis.models import (
    AnalysisCohortDefinition,
    AnalysisCohortType,
    AnalysisProvenanceClassification,
    AnalysisUnit,
    BoundarySelectionPolicy,
    ResearchAnalysisRequest,
)
from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.dataset import build_research_dataset
from squeeze_core.research.io import load_case_registry
from squeeze_core.research.models import (
    BatchEvaluationRequest,
    CandidateCaseRegistry,
    OrderingPolicy,
)
from squeeze_core.research.policies import DETECTION_POLICY_VERSION, OUTCOME_POLICY_VERSION
from squeeze_core.research.serialization import (
    serialize_research_csv,
    serialize_research_json,
    serialize_research_jsonl,
    serialize_research_model,
)
from squeeze_core.serialization import canonical_json_bytes

from .models import PREVIEW_POLICY_VERSION

PHASE3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
PREVIEW_BATCH_VERSION = "phase_3d_batch_09_dry_run.v1"

#: Registry columns projected into the dry-run CSV. Identifiers and statuses only.
_REGISTRY_COLUMNS = (
    "case_id", "symbol", "asset_class", "case_type", "case_status",
    "original_platform_status", "detection_time_evidence_id", "evaluation_as_of",
    "evaluation_request_path", "evaluation_result_path", "outcome_observation_path",
    "phase_3a_policy_version", "fixture_classification", "limitations",
    "original_platform_artifact_ids", "historical_dataset_ids", "deterministic_id",
)


class DryRunArtifacts(BaseModel):
    """The bytes a dry-run publication produced, plus what the pipeline actually did."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry_json: bytes
    registry_jsonl: bytes
    registry_csv: bytes
    dataset_json: bytes
    dataset_jsonl: bytes
    dataset_csv: bytes
    batch_json: bytes
    case_result_count: int
    skipped_case_count: int
    dataset_row_count: int
    skipped_diagnostic_codes: tuple[str, ...]
    canonical_registry_mutated: bool = False


def _registry_jsonl(registry: CandidateCaseRegistry) -> bytes:
    return b"".join(
        canonical_json_bytes(entry) + b"\n" for entry in registry.entries
    )


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        return canonical_json_bytes(value).decode("utf-8")
    if hasattr(value, "value") and not isinstance(value, str):
        value = value.value
    rendered = canonical_json_bytes(value).decode("utf-8")
    return rendered[1:-1] if rendered.startswith('"') else rendered


def _registry_csv(registry: CandidateCaseRegistry) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(_REGISTRY_COLUMNS)
    for entry in registry.entries:
        writer.writerow(_cell(getattr(entry, column)) for column in _REGISTRY_COLUMNS)
    return stream.getvalue().encode("utf-8")


def simulate_phase3b_publication(
    preview_registry_path: Path,
    case_ids: tuple[str, ...],
) -> DryRunArtifacts:
    """Run the existing Phase 3B publication path against the preview registry.

    ``preview_registry_path`` must point at an isolated dry-run copy. Nothing is written by
    this function; it returns bytes for the caller to place wherever it likes.
    """
    registry = load_case_registry(preview_registry_path)

    request = BatchEvaluationRequest(
        batch_version=PREVIEW_BATCH_VERSION,
        phase_3a_policy_version=PHASE3A_POLICY_VERSION,
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_POLICY_VERSION,
        case_ids=case_ids,
        case_registry_version=registry.registry_version,
        ordering_policy=OrderingPolicy.REQUEST_ORDER,
        # Never fail-fast: the point is to observe the honest skip behaviour.
        fail_fast=False,
    )
    batch = run_research_batch(request, preview_registry_path)
    dataset = build_research_dataset(batch)

    codes = sorted({
        diagnostic.code.value
        for case in batch.skipped_cases
        for diagnostic in case.diagnostics
    })

    return DryRunArtifacts(
        registry_json=serialize_research_model(registry) + b"\n",
        registry_jsonl=_registry_jsonl(registry),
        registry_csv=_registry_csv(registry),
        dataset_json=serialize_research_json(dataset) + b"\n",
        dataset_jsonl=serialize_research_jsonl(dataset),
        dataset_csv=serialize_research_csv(dataset),
        batch_json=serialize_research_model(batch) + b"\n",
        case_result_count=len(batch.case_results),
        skipped_case_count=len(batch.skipped_cases),
        dataset_row_count=len(dataset.rows),
        skipped_diagnostic_codes=tuple(codes),
    )


def check_phase3c_structural_compatibility(
    preview_registry_path: Path,
) -> dict[str, object]:
    """Prove Phase 3C can load evaluation-present / outcome-absent candidates.

    Structural only: the registry loads, the registry cohort resolves, and every entry is
    admitted without assuming an outcome exists. No new empirical or descriptive statistic is
    computed for the real cohort here -- the full analysis path is exercised in the committed
    tests against a synthetic registry instead.
    """
    registry = load_case_registry(preview_registry_path)
    definition = AnalysisCohortDefinition(
        # Registry-sourced cohort that does not require complete cases.
        cohort_type=AnalysisCohortType.ALL_REGISTERED_CASES,
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        boundary_selection_policy_version=BoundarySelectionPolicy.ALL_CASE_BOUNDARIES,
        provenance_classifications=tuple(
            AnalysisProvenanceClassification(value)
            for value in sorted({
                entry.fixture_classification.value for entry in registry.entries
            })
        ),
        required_complete_cases=False,
    )
    request = ResearchAnalysisRequest(
        source_dataset_id=None,
        source_registry_id=str(registry.deterministic_id),
        cohort_definition=definition,
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        boundary_selection_policy_version=BoundarySelectionPolicy.ALL_CASE_BOUNDARIES,
        included_statistics=(),
        excluded_statistics=("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION"),
    )
    membership = build_registry_cohort(request, registry)
    return {
        "preview_policy_version": PREVIEW_POLICY_VERSION,
        "registry_loaded": True,
        "registry_id": str(registry.deterministic_id),
        "cohort_membership_id": str(membership.deterministic_id),
        "entry_count": len(registry.entries),
        "included_case_count": len(membership.included_case_ids),
        "excluded_case_count": len(membership.exclusions),
        "evaluation_present_count": sum(
            1 for entry in registry.entries if entry.evaluation_result_path is not None
        ),
        "outcome_absent_count": sum(
            1 for entry in registry.entries if entry.outcome_observation_path is None
        ),
        "outcome_presence_assumed": False,
        "unknown_interpreted_as_zero": False,
        "unevaluable_interpreted_as_not_detected": False,
        "loader_raised": False,
    }


__all__ = [
    "PHASE3A_POLICY_VERSION",
    "PREVIEW_BATCH_VERSION",
    "DryRunArtifacts",
    "check_phase3c_structural_compatibility",
    "simulate_phase3b_publication",
]
