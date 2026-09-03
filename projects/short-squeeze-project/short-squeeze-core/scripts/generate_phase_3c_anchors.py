"""Generate deterministic Phase 3C analysis fixtures and anchor metadata."""

import hashlib
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from squeeze_core.analysis.intervals import wilson_score_interval  # noqa: E402
from squeeze_core.analysis.models import AnalysisUnit  # noqa: E402
from squeeze_core.analysis.proportions import ProportionContext, build_proportion  # noqa: E402
from squeeze_core.analysis.reports import render_markdown_report  # noqa: E402
from squeeze_core.analysis.runner import (  # noqa: E402
    build_standard_analysis_requests,
    run_research_analysis,
)
from squeeze_core.analysis.sample_size import assess_sample_size  # noqa: E402
from squeeze_core.analysis.serialization import (  # noqa: E402
    serialize_analysis_collection,
    serialize_analysis_model,
)
from squeeze_core.research.models import CandidateCaseRegistry  # noqa: E402
from squeeze_core.research.serialization import deserialize_research_dataset  # noqa: E402
from squeeze_core.serialization import canonical_json_bytes  # noqa: E402


OUT = ROOT / "tests" / "fixtures" / "analysis"
RESEARCH = ROOT / "tests" / "fixtures" / "research"
POLICIES = ROOT / "src" / "squeeze_core" / "analysis" / "policies"

ANCHOR_NAMES = (
    "historical_case_boundary_cohort",
    "historical_unique_symbol_cohort",
    "synthetic_case_cohort",
    "all_registered_case_cohort",
    "partial_blocked_case_cohort",
    "earliest_boundary_selection",
    "biya_symbol_dependence_summary",
    "sample_size_zero",
    "sample_size_one",
    "sample_size_very_small",
    "proportion_zero_of_one",
    "proportion_one_of_one",
    "proportion_one_of_two",
    "proportion_undefined",
    "wilson_zero_success",
    "wilson_all_success",
    "wilson_one_of_two",
    "confusion_matrix_historical_case_boundary",
    "confusion_matrix_historical_unique_symbol",
    "rule_prevalence_historical_case_boundary",
    "rule_prevalence_historical_unique_symbol",
    "rule_prevalence_synthetic",
    "missingness_historical",
    "missingness_all_registered",
    "detection_prevalence_historical",
    "outcome_prevalence_historical",
    "classification_prevalence_historical",
    "biya_case_boundary_analysis",
    "biya_unique_symbol_analysis",
    "historical_case_boundary_report",
    "historical_unique_symbol_report",
    "synthetic_report",
    "all_registered_data_quality_report",
    "partial_blocked_report",
    "phase_3c_cli_output",
    "phase_3c_report_cli_output",
    "mixed_phase_3c_output",
    "serialized_phase_3c_collection",
)


def _sources():
    dataset = deserialize_research_dataset(
        (RESEARCH / "phase_3b_research_dataset.json").read_bytes()
    )
    registry = CandidateCaseRegistry.model_validate_json(
        (RESEARCH / "phase_3b_case_registry.json").read_bytes()
    )
    return dataset, registry


def _standard_results():
    dataset, registry = _sources()
    requests = build_standard_analysis_requests(dataset, registry)
    results = tuple(
        run_research_analysis(
            request,
            dataset=dataset if request.source_dataset_id is not None else None,
            registry=registry if request.source_registry_id is not None else None,
        )
        for request in requests
    )
    # Public standard order is unique historical, boundary historical, synthetic,
    # all registered, and partial/blocked.
    return requests, results


def _context() -> ProportionContext:
    return ProportionContext(
        cohort_id="phase_3c_anchor_cohort",
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        interval_policy_version="phase_3c_interval_policy.v1",
        confidence_level=Decimal("0.95"),
        sample_size_policy_version="phase_3c_sample_size_policy.v1",
    )


def _bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if hasattr(value, "model_dump"):
        return serialize_analysis_model(value)
    return canonical_json_bytes(value)


def _hash(value) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def build_anchor_results():
    _, standard = _standard_results()
    unique, boundary, synthetic, registered, partial = standard
    context = _context()
    results = {
        "historical_case_boundary_cohort": boundary.cohort_membership,
        "historical_unique_symbol_cohort": unique.cohort_membership,
        "synthetic_case_cohort": synthetic.cohort_membership,
        "all_registered_case_cohort": registered.cohort_membership,
        "partial_blocked_case_cohort": partial.cohort_membership,
        "earliest_boundary_selection": unique.boundary_selection,
        "biya_symbol_dependence_summary": boundary.symbol_dependence_summary,
        "sample_size_zero": assess_sample_size(0, 0, AnalysisUnit.CASE_BOUNDARY, "phase_3c_sample_size_policy.v1"),
        "sample_size_one": assess_sample_size(1, 1, AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY, "phase_3c_sample_size_policy.v1"),
        "sample_size_very_small": assess_sample_size(2, 1, AnalysisUnit.CASE_BOUNDARY, "phase_3c_sample_size_policy.v1"),
        "proportion_zero_of_one": build_proportion("anchor", 0, 1, context),
        "proportion_one_of_one": build_proportion("anchor", 1, 1, context),
        "proportion_one_of_two": build_proportion("anchor", 1, 2, context),
        "proportion_undefined": build_proportion("anchor", 0, 0, context),
        "wilson_zero_success": wilson_score_interval(0, 1, context),
        "wilson_all_success": wilson_score_interval(1, 1, context),
        "wilson_one_of_two": wilson_score_interval(1, 2, context),
        "confusion_matrix_historical_case_boundary": boundary.confusion_matrix,
        "confusion_matrix_historical_unique_symbol": unique.confusion_matrix,
        "rule_prevalence_historical_case_boundary": boundary.rule_outcome_prevalence,
        "rule_prevalence_historical_unique_symbol": unique.rule_outcome_prevalence,
        "rule_prevalence_synthetic": synthetic.rule_outcome_prevalence,
        "missingness_historical": unique.domain_missingness_summary,
        "missingness_all_registered": registered.data_quality_summary,
        "detection_prevalence_historical": unique.detection_prevalence,
        "outcome_prevalence_historical": unique.outcome_prevalence,
        "classification_prevalence_historical": unique.classification_prevalence,
        "biya_case_boundary_analysis": boundary,
        "biya_unique_symbol_analysis": unique,
        "historical_case_boundary_report": render_markdown_report(boundary),
        "historical_unique_symbol_report": render_markdown_report(unique),
        "synthetic_report": render_markdown_report(synthetic),
        "all_registered_data_quality_report": render_markdown_report(registered),
        "partial_blocked_report": render_markdown_report(partial),
        "phase_3c_cli_output": serialize_analysis_model(unique),
        "phase_3c_report_cli_output": render_markdown_report(unique),
    }
    results["mixed_phase_3c_output"] = tuple(
        _hash(results[name]) for name in sorted(results)
    )
    results["serialized_phase_3c_collection"] = serialize_analysis_collection(standard)
    assert tuple(results) == ANCHOR_NAMES
    return results


def _self_describing_component(result, field_name: str):
    return {
        "schema_version": "1.0.0",
        "analysis_version": result.analysis_version,
        "source_dataset_id": result.source_dataset_id,
        "source_registry_id": result.source_registry_id,
        "cohort_definition": result.cohort_membership.cohort_definition,
        "analysis_unit": result.analysis_unit,
        "boundary_selection_policy_version": result.boundary_selection_policy_version,
        "statistics_policy_version": result.statistics_policy_version,
        "interval_policy_version": result.interval_policy_version,
        "confidence_level": result.confidence_level,
        "sample_size_policy_version": result.sample_size_policy_version,
        "provenance_classifications": result.provenance_classifications,
        field_name: getattr(result, field_name),
    }


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    requests, standard = _standard_results()
    unique, boundary, synthetic, registered, partial = standard
    results = build_anchor_results()

    for source, target in (
        ("phase_3c_statistics_policy_v1.json", "phase_3c_statistics_policy.json"),
        ("phase_3c_interval_policy_v1.json", "phase_3c_interval_policy.json"),
        ("phase_3c_sample_size_policy_v1.json", "phase_3c_sample_size_policy.json"),
        ("phase_3c_boundary_selection_policy_v1.json", "phase_3c_boundary_selection_policy.json"),
    ):
        shutil.copyfile(POLICIES / source, OUT / target)

    (OUT / "phase_3c_analysis_requests.json").write_bytes(canonical_json_bytes(requests))
    for result, filename in (
        (boundary, "phase_3c_historical_case_boundary_analysis.json"),
        (unique, "phase_3c_historical_unique_symbol_analysis.json"),
        (synthetic, "phase_3c_synthetic_case_analysis.json"),
        (registered, "phase_3c_all_registered_data_quality_analysis.json"),
        (partial, "phase_3c_partial_blocked_case_analysis.json"),
    ):
        (OUT / filename).write_bytes(serialize_analysis_model(result))
    (OUT / "phase_3c_historical_unique_symbol_report.md").write_bytes(
        render_markdown_report(unique)
    )
    for result, field, filename in (
        (unique, "rule_outcome_prevalence", "phase_3c_rule_prevalence_summary.json"),
        (unique, "domain_missingness_summary", "phase_3c_missingness_summary.json"),
        (boundary, "symbol_dependence_summary", "phase_3c_symbol_dependence_summary.json"),
        (unique, "confusion_matrix", "phase_3c_confusion_matrix_summary.json"),
    ):
        (OUT / filename).write_bytes(
            canonical_json_bytes(_self_describing_component(result, field))
        )

    metadata = {
        "schema_version": "1.0.0",
        "analysis_version": "phase_3c_analysis.v1",
        "statistics_policy_version": "phase_3c_descriptive_statistics_policy.v1",
        "interval_policy_version": "phase_3c_interval_policy.v1",
        "sample_size_policy_version": "phase_3c_sample_size_policy.v1",
        "hash_algorithm": "sha256-phase-3c-canonical-or-raw-bytes",
        "anchors": {name: _hash(results[name]) for name in ANCHOR_NAMES},
    }
    (OUT / "expected_phase_3c_analysis_metadata.json").write_bytes(
        canonical_json_bytes(metadata)
    )
    files = tuple(sorted(path.name for path in OUT.iterdir() if path.is_file()))
    classifications = {
        name: (
            "SANITIZED_PUBLIC_HISTORICAL_DATA"
            if "historical" in name or "biya" in name
            else "SYNTHETIC_EDGE_CASE"
            if "synthetic" in name
            else "MIXED_PROVENANCE"
            if "all_registered" in name or "requests" in name
            else "SANITIZED_LOCAL_ARTIFACT"
            if "policy" in name or "metadata" in name
            else "DERIVED_DETERMINISTIC_ANALYSIS"
        )
        for name in files
    }
    fixture_metadata = {
        "schema_version": "1.0.0",
        "files": files,
        "classifications": classifications,
        "synthetic_cases_are_historical": False,
        "source_dataset_path": "../research/phase_3b_research_dataset.json",
        "source_registry_path": "../research/phase_3b_case_registry.json",
    }
    (OUT / "phase_3c_fixture_metadata.json").write_bytes(
        canonical_json_bytes(fixture_metadata)
    )
    return metadata


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True, separators=(",", ":")))
