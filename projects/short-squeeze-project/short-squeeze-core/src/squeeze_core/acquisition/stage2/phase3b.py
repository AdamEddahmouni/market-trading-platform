"""Phase 3B research evaluation outputs for Phase 3E Stage 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squeeze_core.contracts import AssetClass
from squeeze_core.evaluation.serialization import deserialize_candidate_evaluation
from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.models import (
    BatchEvaluationRequest,
    CandidateCaseRegistry,
    CandidateCaseRegistryEntry,
    CandidateCaseStatus,
    CandidateCaseType,
    FixtureClassification,
    OrderingPolicy,
    OriginalPlatformStatus,
)
from squeeze_core.research.registry import build_case_registry
from squeeze_core.research.serialization import serialize_research_json, serialize_research_model
from squeeze_core.research.summaries import (
    build_category_frequency_summary,
    build_missingness_summary,
    build_outcome_conditioned_rule_summary,
    build_rule_frequency_summary,
)
from squeeze_core.research.dataset import build_research_dataset

from .constants import (
    BATCH_VERSION,
    DETECTION_POLICY_VERSION,
    OUTCOME_LABEL_POLICY_VERSION,
    PHASE3B_DIR,
    PHASE_3A_POLICY_VERSION,
    REGISTRY_VERSION,
)


@dataclass(frozen=True)
class Phase3BBuildResult:
    registry_path: Path
    batch_path: Path
    dataset_path: Path
    case_count: int
    leakage_passed_case_ids: tuple[str, ...]


def _registry_entry(
    *,
    symbol: str,
    case_id: str,
    evaluation_as_of,
) -> CandidateCaseRegistryEntry:
    return CandidateCaseRegistryEntry(
        case_id=case_id,
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        case_type=CandidateCaseType.ORIGINAL_PLATFORM_STATUS_UNKNOWN,
        case_status=CandidateCaseStatus.COMPLETE,
        original_platform_status=OriginalPlatformStatus.UNKNOWN,
        detection_time_evidence_id=case_id,
        evaluation_as_of=evaluation_as_of,
        evaluation_result_path=f"../phase3a-freeze/{symbol}/frozen_result.json",
        outcome_observation_path=f"../outcomes/{symbol}/outcome-observation.json",
        original_platform_artifact_ids=("archived-app-log",),
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        limitations=(
            "outcome movement does not establish short-squeeze causation",
            "published short interest evidence is unavailable",
            "historical borrow evidence remains unavailable",
            "Phase 3E Stage 2 pipeline artifact",
        ),
        fixture_classification=FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
    )


def build_phase3b_outputs(
    *,
    stage2_root: Path,
    passed_cases: tuple[tuple[str, str], ...],
    freeze_root: Path,
    force: bool = False,
) -> Phase3BBuildResult:
    """Build registry, batch result, and dataset under ``stage2_root/phase3b``."""
    out_dir = stage2_root / "phase3b"
    out_dir.mkdir(parents=True, exist_ok=True)
    registry_path = out_dir / "case_registry.json"
    batch_path = out_dir / "research_batch.json"
    dataset_path = out_dir / "research_dataset.json"

    if (
        not force
        and registry_path.is_file()
        and batch_path.is_file()
        and dataset_path.is_file()
    ):
        registry = CandidateCaseRegistry.model_validate_json(registry_path.read_bytes())
        return Phase3BBuildResult(
            registry_path=registry_path,
            batch_path=batch_path,
            dataset_path=dataset_path,
            case_count=len(registry.entries),
            leakage_passed_case_ids=tuple(item.case_id for item in registry.entries),
        )

    entries: list[CandidateCaseRegistryEntry] = []
    for symbol, case_id in passed_cases:
        result_path = stage2_root / "phase3a-freeze" / symbol / "frozen_result.json"
        if not result_path.is_file():
            source = freeze_root / "results" / f"{case_id}.json"
            if not source.is_file():
                continue
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_bytes(source.read_bytes())
        evaluation = deserialize_candidate_evaluation(result_path.read_bytes())
        entries.append(
            _registry_entry(
                symbol=symbol,
                case_id=case_id,
                evaluation_as_of=evaluation.as_of,
            )
        )

    if not entries:
        raise ValueError("no leakage-passing cases available for Phase 3B")

    registry = build_case_registry(REGISTRY_VERSION, tuple(entries))
    registry_path.write_bytes(serialize_research_model(registry))

    case_ids = tuple(item.case_id for item in entries)
    request = BatchEvaluationRequest(
        batch_version=BATCH_VERSION,
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_LABEL_POLICY_VERSION,
        case_ids=case_ids,
        case_registry_version=REGISTRY_VERSION,
        ordering_policy=OrderingPolicy.CANONICAL_CASE_ID,
    )
    batch = run_research_batch(request, registry_path)
    dataset = build_research_dataset(batch)
    batch_path.write_bytes(serialize_research_model(batch))
    dataset_path.write_bytes(serialize_research_json(dataset))

    summaries_dir = out_dir / "summaries"
    summaries_dir.mkdir(exist_ok=True)
    (summaries_dir / "rule_frequency.json").write_bytes(
        serialize_research_model(build_rule_frequency_summary(batch))
    )
    (summaries_dir / "outcome_conditioned_rules.json").write_bytes(
        serialize_research_model(build_outcome_conditioned_rule_summary(batch))
    )
    (summaries_dir / "category_frequency.json").write_bytes(
        serialize_research_model(build_category_frequency_summary(batch))
    )
    (summaries_dir / "missingness.json").write_bytes(
        serialize_research_model(build_missingness_summary(batch))
    )

    return Phase3BBuildResult(
        registry_path=registry_path,
        batch_path=batch_path,
        dataset_path=dataset_path,
        case_count=len(entries),
        leakage_passed_case_ids=case_ids,
    )


__all__ = ["Phase3BBuildResult", "build_phase3b_outputs"]
