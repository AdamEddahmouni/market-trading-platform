"""Phase 3C descriptive analysis over the batch 01 registry candidates.

Offline and deterministic: the analyzer is run over the committed batch registry
fixture and must yield registry-only, descriptive-only results with no complete
cases, no confusion matrix, and no predictive-validation claim.
"""

import json
from pathlib import Path

from squeeze_core.__main__ import main


ROOT = Path(__file__).resolve().parents[2]
BATCH_REGISTRY = (
    ROOT / "tests" / "fixtures" / "acquisition" / "batch01"
    / "phase3b-registry-candidates.json"
)


def _analyze(output: Path) -> int:
    return main([
        "analyze-research-dataset",
        "--case-registry", str(BATCH_REGISTRY),
        "--cohort", "all-registered",
        "--analysis-unit", "unique-symbol",
        "--boundary-policy", "earliest_detection_boundary_per_symbol.v1",
        "--statistics-policy", "phase_3c_descriptive_statistics_policy.v1",
        "--interval-policy", "phase_3c_interval_policy.v1",
        "--sample-size-policy", "phase_3c_sample_size_policy.v1",
        "--confidence-level", "0.95",
        "--output", str(output),
    ])


def test_batch01_descriptive_analysis_is_registry_only_and_deterministic(tmp_path, capsys):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    assert _analyze(first) == 0
    capsys.readouterr()
    assert _analyze(second) == 0
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()

    result = json.loads(first.read_text(encoding="utf-8"))
    assert result["case_count"] == 13
    assert result["unique_symbol_count"] == 13
    assert result["boundary_count"] == 0
    assert result["confusion_matrix"] is None
    dq = result["data_quality_summary"]
    assert dq["registered_case_count"] == 13
    assert dq["complete_case_count"] == 0
    assert dq["partial_case_count"] == 13
    codes = {d["code"] for d in result["diagnostics"]}
    assert "ANALYSIS_DESCRIPTIVE_ONLY" in codes
    assert "ANALYSIS_NO_PREDICTIVE_VALIDATION" in codes
    for assessment in result["sample_size_assessments"]:
        assert "PREDICTIVE_VALIDATION" in assessment["forbidden_interpretation"]


def test_batch01_partial_blocked_cohort_runs(tmp_path, capsys):
    output = tmp_path / "pb.json"
    assert main([
        "analyze-research-dataset",
        "--case-registry", str(BATCH_REGISTRY),
        "--cohort", "partial-blocked",
        "--analysis-unit", "unique-symbol",
        "--boundary-policy", "earliest_detection_boundary_per_symbol.v1",
        "--statistics-policy", "phase_3c_descriptive_statistics_policy.v1",
        "--interval-policy", "phase_3c_interval_policy.v1",
        "--sample-size-policy", "phase_3c_sample_size_policy.v1",
        "--confidence-level", "0.95",
        "--output", str(output),
    ]) == 0
    capsys.readouterr()
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["case_count"] == 13
    assert result["confusion_matrix"] is None
