from pathlib import Path

import pytest

from squeeze_core.evaluation import serialize_candidate_evaluation
from squeeze_core.research.io import (
    ResearchArtifactError,
    load_case_registry,
    load_phase_3a_result,
    resolve_artifact_path,
)
from squeeze_core.serialization import canonical_json_bytes

from .helpers import BASE_EVALUATION
from .test_models import entry


def test_registry_and_phase_3a_result_load_from_explicit_local_paths(tmp_path):
    evaluation_path = tmp_path / "evaluation.json"
    evaluation_path.write_bytes(serialize_candidate_evaluation(BASE_EVALUATION))
    registry_path = tmp_path / "registry.json"
    registry_path.write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0",
        "registry_version": "phase_3b_case_registry.v1",
        "entries": [entry(evaluation_result_path="evaluation.json").model_dump(mode="json")],
    }))
    registry = load_case_registry(registry_path)
    loaded = load_phase_3a_result(registry.entries[0], registry_path)
    assert serialize_candidate_evaluation(loaded) == serialize_candidate_evaluation(BASE_EVALUATION)


def test_artifact_paths_must_be_relative_and_within_project(tmp_path):
    registry = tmp_path / "fixtures" / "registry.json"
    registry.parent.mkdir()
    with pytest.raises(ResearchArtifactError, match="absolute artifact paths"):
        resolve_artifact_path(registry, str(Path.cwd().resolve() / "outside.json"))
    with pytest.raises(ResearchArtifactError, match="escapes project root"):
        resolve_artifact_path(registry, "../../outside.json")


def test_phase_3a_request_artifact_invokes_existing_evaluator(tmp_path):
    fixture_root = tmp_path / "fixtures"
    research_root = fixture_root / "research"
    evaluation_root = fixture_root / "evaluation"
    research_root.mkdir(parents=True)
    evaluation_root.mkdir()
    source_root = Path(__file__).resolve().parents[1] / "fixtures" / "evaluation"
    (evaluation_root / "policy.json").write_bytes(
        (source_root / "phase_3a_default_policy.json").read_bytes()
    )
    (evaluation_root / "evidence.jsonl").write_bytes(
        (source_root / "biya_earliest_evidence.jsonl").read_bytes()
    )
    request_path = research_root / "request.json"
    request_path.write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0",
        "symbol": BASE_EVALUATION.symbol,
        "asset_class": BASE_EVALUATION.asset_class,
        "as_of": BASE_EVALUATION.as_of,
        "policy_version": BASE_EVALUATION.policy_version,
        "enabled_rule_ids": tuple(item.rule_id for item in BASE_EVALUATION.rule_results),
        "policy_path": "../evaluation/policy.json",
        "evidence_path": "../evaluation/evidence.jsonl",
        "provider_scope": ("yahoo-chart", "yahoo-search"),
    }))
    registry_path = research_root / "registry.json"
    registry_path.write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0",
        "registry_version": "phase_3b_case_registry.v1",
        "entries": [entry(
            evaluation_request_path="request.json", evaluation_result_path=None
        ).model_dump(mode="json")],
    }))

    registry = load_case_registry(registry_path)
    loaded = load_phase_3a_result(registry.entries[0], registry_path)
    assert loaded.symbol == BASE_EVALUATION.symbol
    assert loaded.as_of == BASE_EVALUATION.as_of
    assert tuple(item.rule_id for item in loaded.rule_results) == tuple(
        item.rule_id for item in BASE_EVALUATION.rule_results
    )
