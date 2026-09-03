"""Phase 3C descriptive analysis outputs for Phase 3E Stage 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squeeze_core.analysis.reports import render_markdown_report
from squeeze_core.analysis.runner import build_standard_analysis_requests, run_research_analysis
from squeeze_core.analysis.serialization import serialize_analysis_collection, serialize_analysis_model
from squeeze_core.research.models import CandidateCaseRegistry
from squeeze_core.research.serialization import deserialize_research_dataset

from .constants import PHASE3C_DIR


@dataclass(frozen=True)
class Phase3CBuildResult:
    output_dir: Path
    report_count: int
    collection_path: Path


def build_phase3c_outputs(
    *,
    stage2_root: Path,
    force: bool = False,
) -> Phase3CBuildResult:
    """Run standard descriptive analysis on the Stage 2 Phase 3B dataset."""
    phase3b_dir = stage2_root / "phase3b"
    registry_path = phase3b_dir / "case_registry.json"
    dataset_path = phase3b_dir / "research_dataset.json"
    if not registry_path.is_file() or not dataset_path.is_file():
        raise FileNotFoundError("Phase 3B outputs required before Phase 3C")

    out_dir = stage2_root / "phase3c"
    reports_dir = out_dir / "reports"
    collection_path = out_dir / "analysis_collection.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    if not force and collection_path.is_file() and any(reports_dir.glob("*.md")):
        return Phase3CBuildResult(
            output_dir=out_dir,
            report_count=len(list(reports_dir.glob("*.md"))),
            collection_path=collection_path,
        )

    dataset = deserialize_research_dataset(dataset_path.read_bytes())
    registry = CandidateCaseRegistry.model_validate_json(registry_path.read_bytes())
    requests = build_standard_analysis_requests(dataset, registry)
    results = tuple(
        run_research_analysis(
            request,
            dataset=dataset if request.source_dataset_id is not None else None,
            registry=registry if request.source_registry_id is not None else None,
        )
        for request in requests
    )
    collection_path.write_bytes(serialize_analysis_collection(results))

    report_count = 0
    for result in results:
        slug = (result.deterministic_id or result.request_id).replace("::", "_")
        report_path = reports_dir / f"{slug}.md"
        report_path.write_bytes(render_markdown_report(result))
        report_count += 1
        detail_path = reports_dir / f"{slug}.json"
        detail_path.write_bytes(serialize_analysis_model(result))

    return Phase3CBuildResult(
        output_dir=out_dir,
        report_count=report_count,
        collection_path=collection_path,
    )


__all__ = ["Phase3CBuildResult", "build_phase3c_outputs"]
