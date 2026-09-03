import json
from pathlib import Path

from squeeze_core.__main__ import main


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "tests" / "fixtures" / "research" / "phase_3b_research_dataset.json"
REGISTRY = ROOT / "tests" / "fixtures" / "research" / "phase_3b_case_registry.json"


def _analysis_args(output, *, cohort="historical-complete", unit="unique-symbol-policy-selected-boundary"):
    return (
        "analyze-research-dataset",
        "--dataset", str(DATASET),
        "--case-registry", str(REGISTRY),
        "--cohort", cohort,
        "--analysis-unit", unit,
        "--boundary-policy", (
            "earliest_detection_boundary_per_symbol.v1"
            if unit == "unique-symbol-policy-selected-boundary"
            else "all_case_boundaries.v1"
        ),
        "--statistics-policy", "phase_3c_descriptive_statistics_policy.v1",
        "--interval-policy", "phase_3c_interval_policy.v1",
        "--confidence-level", "0.95",
        "--sample-size-policy", "phase_3c_sample_size_policy.v1",
        "--output", str(output),
    )


def test_analysis_cli_is_repeated_byte_identical(tmp_path, capsys):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    assert main(_analysis_args(first_path)) == 0
    first_stdout = capsys.readouterr().out
    assert main(_analysis_args(second_path)) == 0
    second_stdout = capsys.readouterr().out
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_stdout == second_stdout
    document = json.loads(first_path.read_bytes())
    assert document["analysis_unit"] == "UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY"
    assert document["case_count"] == 6
    assert document["source_dataset_id"]
    assert document["source_registry_id"]


def test_report_cli_is_repeated_byte_identical(tmp_path, capsys):
    analysis_path = tmp_path / "analysis.json"
    assert main(_analysis_args(analysis_path)) == 0
    capsys.readouterr()
    first_path = tmp_path / "first.md"
    second_path = tmp_path / "second.md"
    args = (
        "render-research-analysis-report",
        "--analysis", str(analysis_path),
        "--format", "markdown",
        "--output", str(first_path),
    )
    assert main(args) == 0
    first_stdout = capsys.readouterr().out
    args = args[:-1] + (str(second_path),)
    assert main(args) == 0
    second_stdout = capsys.readouterr().out
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_stdout == second_stdout
    assert b"## Limitations" in first_path.read_bytes()


def test_registry_cohort_requires_explicit_registry_path(tmp_path, capsys):
    args = list(_analysis_args(
        tmp_path / "registry.json",
        cohort="all-registered",
        unit="case-boundary",
    ))
    index = args.index("--case-registry")
    del args[index:index + 2]
    assert main(tuple(args)) == 1
    error = json.loads(capsys.readouterr().err)
    assert error == {
        "command": "analyze-research-dataset",
        "error": "ANALYSIS_SOURCE_REGISTRY_REQUIRED",
        "valid": False,
    }


def test_unsupported_confidence_level_is_structured_error(tmp_path, capsys):
    args = list(_analysis_args(tmp_path / "invalid.json"))
    args[args.index("--confidence-level") + 1] = "0.90"
    assert main(tuple(args)) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["command"] == "analyze-research-dataset"
    assert "ANALYSIS_INTERVAL_CONFIDENCE_UNSUPPORTED" in error["error"]
    assert error["valid"] is False

