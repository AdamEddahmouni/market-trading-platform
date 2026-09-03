import json
from pathlib import Path

from squeeze_core.__main__ import main


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "research"


def batch_args(output):
    return [
        "build-research-evaluation-batch",
        "--case-registry", str(FIXTURES / "phase_3b_case_registry.json"),
        "--case-id", "BIYA_EARLIEST_BOUNDARY",
        "--case-id", "SYN_FALSE_POSITIVE",
        "--phase-3a-policy", "phase_3a_transparent_candidate_policy.v1",
        "--detection-policy", "phase_3b_research_detection_policy.v1",
        "--outcome-policy", "phase_3b_outcome_label_policy.v1",
        "--output", str(output),
    ]


def test_batch_cli_is_offline_deterministic_and_canonical(tmp_path, capsys):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    assert main(batch_args(first)) == 0
    capsys.readouterr()
    assert main(batch_args(second)) == 0
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
    document = json.loads(first.read_text(encoding="utf-8"))
    assert [item["case_id"] for item in document["case_results"]] == [
        "BIYA_EARLIEST_BOUNDARY", "SYN_FALSE_POSITIVE"
    ]


def test_export_cli_writes_stable_json_jsonl_and_csv(tmp_path, capsys):
    batch = tmp_path / "batch.json"
    assert main(batch_args(batch)) == 0
    capsys.readouterr()
    outputs = {}
    for format_name in ("json", "jsonl", "csv"):
        first = tmp_path / f"first.{format_name}"
        second = tmp_path / f"second.{format_name}"
        args = [
            "export-research-dataset", "--batch", str(batch),
            "--format", format_name, "--output", str(first),
        ]
        assert main(args) == 0
        capsys.readouterr()
        args[-1] = str(second)
        assert main(args) == 0
        capsys.readouterr()
        assert first.read_bytes() == second.read_bytes()
        outputs[format_name] = first.read_bytes()
    assert outputs["jsonl"].endswith(b"\n")
    assert b"\r\n" not in outputs["csv"]


def test_batch_cli_returns_structured_nonzero_error(tmp_path, capsys):
    args = batch_args(tmp_path / "invalid.json")
    case_index = args.index("BIYA_EARLIEST_BOUNDARY")
    args[case_index] = "UNKNOWN-CASE"
    assert main(args) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["command"] == "build-research-evaluation-batch"
    assert error["valid"] is False
