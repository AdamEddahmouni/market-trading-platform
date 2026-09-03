import json
from pathlib import Path

from scripts.generate_phase_3b_anchors import (
    ANCHOR_NAMES,
    anchor_hash,
    build_anchor_results,
    generate,
)


ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / "tests" / "fixtures" / "research" / "expected_phase_3b_research_metadata.json"


def test_required_anchor_inventory_is_complete():
    required = {
        "detection_policy_detected", "detection_policy_not_detected",
        "detection_policy_unevaluable_unknown", "detection_policy_unevaluable_conflicted",
        "detection_policy_unevaluable_insufficient", "outcome_substantial_upward",
        "outcome_no_substantial_upward", "outcome_unknown", "outcome_insufficient",
        "research_true_positive", "research_false_positive", "research_true_negative",
        "research_false_negative", "research_unevaluable", "biya_earliest_research_case",
        "biya_latest_research_case", "historical_case_registry", "synthetic_case_registry",
        "complete_case_registry", "single_case_batch", "multi_case_batch",
        "rule_outcome_matrix", "rule_frequency_summary", "outcome_conditioned_rule_summary",
        "category_frequency_summary", "missingness_summary", "true_positive_dataset",
        "false_positive_dataset", "true_negative_dataset", "false_negative_dataset",
        "unevaluable_dataset", "research_dataset_json", "research_dataset_jsonl",
        "research_dataset_csv", "phase_3b_cli_output", "phase_3b_export_cli_output",
        "mixed_phase_3b_output", "serialized_phase_3b_collection",
    }
    assert required <= set(ANCHOR_NAMES)


def test_named_anchors_regenerate_deterministically_and_match_metadata():
    expected = json.loads(METADATA.read_text(encoding="utf-8"))["anchors"]
    first = build_anchor_results()
    second = build_anchor_results()
    assert first.keys() == second.keys() == expected.keys()
    for name in first:
        assert anchor_hash(first[name]) == anchor_hash(second[name]) == expected[name]


def test_generator_repeated_run_returns_same_metadata():
    assert generate() == generate()


def test_fixture_metadata_distinguishes_synthetic_historical_and_mixed_files():
    metadata = json.loads(
        (METADATA.parent / "phase_3b_fixture_metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["classifications"]["phase_3b_synthetic_cases.json"] == (
        "SYNTHETIC_EDGE_CASE"
    )
    assert metadata["classifications"]["biya_earliest_outcome_observation.json"] == (
        "SANITIZED_PUBLIC_HISTORICAL_DATA"
    )
    assert metadata["classifications"]["phase_3b_case_registry.json"] == "MIXED_PROVENANCE"
    assert metadata["synthetic_cases_are_historical"] is False
