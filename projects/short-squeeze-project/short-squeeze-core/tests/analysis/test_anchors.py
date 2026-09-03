import hashlib
import json
from pathlib import Path

from scripts.generate_phase_3c_anchors import ANCHOR_NAMES, generate


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "analysis"
METADATA = FIXTURES / "expected_phase_3c_analysis_metadata.json"


REQUIRED_FILES = {
    "phase_3c_statistics_policy.json",
    "phase_3c_interval_policy.json",
    "phase_3c_sample_size_policy.json",
    "phase_3c_boundary_selection_policy.json",
    "phase_3c_analysis_requests.json",
    "phase_3c_historical_case_boundary_analysis.json",
    "phase_3c_historical_unique_symbol_analysis.json",
    "phase_3c_synthetic_case_analysis.json",
    "phase_3c_all_registered_data_quality_analysis.json",
    "phase_3c_partial_blocked_case_analysis.json",
    "phase_3c_historical_unique_symbol_report.md",
    "phase_3c_rule_prevalence_summary.json",
    "phase_3c_missingness_summary.json",
    "phase_3c_symbol_dependence_summary.json",
    "phase_3c_confusion_matrix_summary.json",
    "expected_phase_3c_analysis_metadata.json",
    "phase_3c_fixture_metadata.json",
}


def _fixture_hashes():
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in FIXTURES.iterdir() if path.is_file()
    }


def test_phase_3c_anchor_manifest_is_complete_and_current():
    expected = json.loads(METADATA.read_text(encoding="utf-8"))
    actual = generate()
    assert set(expected["anchors"]) == set(ANCHOR_NAMES)
    assert actual == expected
    assert REQUIRED_FILES <= {path.name for path in FIXTURES.iterdir()}


def test_phase_3c_anchor_generation_is_repeated_byte_identical():
    generate()
    first = _fixture_hashes()
    generate()
    assert _fixture_hashes() == first


def test_fixture_metadata_keeps_synthetic_and_historical_distinct():
    metadata = json.loads(
        (FIXTURES / "phase_3c_fixture_metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["synthetic_cases_are_historical"] is False
    assert set(metadata["classifications"].values()) <= {
        "SANITIZED_PUBLIC_HISTORICAL_DATA",
        "SANITIZED_LOCAL_ARTIFACT",
        "SYNTHETIC_EDGE_CASE",
        "MIXED_PROVENANCE",
        "DERIVED_DETERMINISTIC_ANALYSIS",
    }
