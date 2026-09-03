import json

from squeeze_core.__main__ import main
from squeeze_core.evaluation.policies import DEFAULT_POLICY_PATH
from squeeze_core.serialization import canonical_json_bytes

from .helpers import AS_OF, bar


def _evidence(path):
    path.write_bytes(canonical_json_bytes({
        "record_type": "observation",
        "data": bar(close="8").model_dump(mode="json"),
    }) + b"\n")


def _args(evidence, output, *extra):
    return [
        "build-candidate-evaluation",
        "--policy", str(DEFAULT_POLICY_PATH),
        "--evidence", str(evidence),
        "--symbol", "TESTA",
        "--as-of", AS_OF.isoformat(),
        "--provider", "provider-a",
        "--output", str(output),
        *extra,
    ]


def test_candidate_evaluation_cli_is_offline_deterministic_and_writes_canonical_json(tmp_path):
    evidence = tmp_path / "evidence.jsonl"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _evidence(evidence)
    assert main(_args(evidence, first, "--rule", "PRICE_RANGE")) == 0
    assert main(_args(evidence, second, "--rule", "PRICE_RANGE")) == 0
    assert first.read_bytes() == second.read_bytes()
    result = json.loads(first.read_text(encoding="utf-8"))
    assert result["symbol"] == "TESTA"
    assert result["policy_version"] == "phase_3a_transparent_candidate_policy.v1"
    assert result["rule_results"][0]["rule_id"] == "PRICE_RANGE"
    assert "deterministic_id" in result
    assert "score" not in result
    assert "rank" not in result
    assert "recommendation" not in result


def test_candidate_evaluation_cli_returns_structured_nonzero_error(tmp_path, capsys):
    evidence = tmp_path / "evidence.jsonl"
    _evidence(evidence)
    assert main(_args(evidence, tmp_path / "unused.json", "--rule", "NO_SUCH_RULE")) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["valid"] is False
    assert "EVALUATION_UNKNOWN_RULE" in error["error"]

