import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2c_metric_metadata.json"
PHASE_2A_METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2a_metric_metadata.json"
PHASE_2B_METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2b_metric_metadata.json"
CLI_INPUT = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_cli_demo_observations.jsonl"
CLI_SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_metric_cases.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_phase_2c_anchors import build_anchor_results  # noqa: E402
from squeeze_core.metrics import (  # noqa: E402
    days_to_cover_components_hash,
    pressure_metric_result_hash,
    serialize_days_to_cover_components,
    serialize_pressure_metric_result,
)
from squeeze_core.metrics.pressure_models import DaysToCoverComponents  # noqa: E402
from squeeze_core.serialization import canonical_hash  # noqa: E402


def _recorded_anchors() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))["anchors"]


def _hash(result) -> str:
    return days_to_cover_components_hash(result) if isinstance(result, DaysToCoverComponents) else pressure_metric_result_hash(result)


def _serialize(result) -> bytes:
    return serialize_days_to_cover_components(result) if isinstance(result, DaysToCoverComponents) else serialize_pressure_metric_result(result)


def test_metadata_file_is_well_formed():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "1.0.0"
    assert len(metadata["anchors"]) == 26


def test_all_required_anchors_are_present():
    anchors = _recorded_anchors()
    required = {
        "positive_short_interest_absolute_change",
        "negative_short_interest_absolute_change",
        "positive_short_interest_percentage_change",
        "negative_short_interest_percentage_change",
        "positive_short_interest_revision_delta",
        "negative_short_interest_revision_delta",
        "three_sample_days_to_cover",
        "five_sample_days_to_cover",
        "days_to_cover_components",
        "positive_borrow_fee_absolute_change",
        "negative_borrow_fee_absolute_change",
        "positive_borrow_fee_relative_change",
        "negative_borrow_fee_relative_change",
        "positive_borrow_availability_absolute_change",
        "negative_borrow_availability_absolute_change",
        "positive_borrow_availability_percentage_change",
        "negative_borrow_availability_percentage_change",
        "before_short_interest_revision_result",
        "after_short_interest_revision_result",
        "before_short_interest_cancellation_result",
        "after_short_interest_cancellation_result",
        "before_borrow_update_result",
        "after_borrow_update_result",
        "mixed_phase_2c_metric_output",
        "phase_2c_cli_output",
        "serialized_phase_2c_metric_collection",
    }
    assert required <= set(anchors)


def test_regenerating_named_results_twice_is_byte_identical():
    first = build_anchor_results()
    second = build_anchor_results()
    for name in first:
        assert _hash(first[name]) == _hash(second[name]), name


def test_regenerated_named_results_match_recorded_anchors():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    for name, result in results.items():
        assert _hash(result) == anchors[name], name


def test_regenerated_composite_anchors_match_recorded_values():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]

    assert canonical_hash(list(collection)) == anchors["mixed_phase_2c_metric_output"]

    serialized = __import__("hashlib").sha256(
        b"[" + b",".join(_serialize(item) for item in collection) + b"]"
    ).hexdigest()
    assert serialized == anchors["serialized_phase_2c_metric_collection"]


def test_cli_output_hash_matches_recorded_anchor_and_is_stable():
    anchors = _recorded_anchors()

    def run():
        completed = subprocess.run(
            [
                sys.executable, "-m", "squeeze_core", "build-market-metrics",
                "--input", str(CLI_INPUT), "--symbol", "TESTC", "--as-of", "2026-03-15T12:00:00Z",
                "--spec", str(CLI_SPEC),
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return __import__("hashlib").sha256(completed.stdout.encode("utf-8")).hexdigest()

    first = run()
    second = run()
    assert first == second
    assert first == anchors["phase_2c_cli_output"]


def test_no_unexplained_anchor_collisions():
    phase_2a_anchors = json.loads(PHASE_2A_METADATA_PATH.read_text(encoding="utf-8"))["anchors"]
    phase_2b_anchors = json.loads(PHASE_2B_METADATA_PATH.read_text(encoding="utf-8"))["anchors"]
    phase_2c_anchors = _recorded_anchors()

    assert not (set(phase_2a_anchors.values()) & set(phase_2c_anchors.values()))
    assert not (set(phase_2b_anchors.values()) & set(phase_2c_anchors.values()))

    expected_linked_pair = {
        phase_2c_anchors["mixed_phase_2c_metric_output"],
        phase_2c_anchors["serialized_phase_2c_metric_collection"],
    }
    assert len(expected_linked_pair) == 1

    remaining = {k: v for k, v in phase_2c_anchors.items() if k != "serialized_phase_2c_metric_collection"}
    values = list(remaining.values())
    assert len(values) == len(set(values)), "unexplained duplicate anchor hash within Phase 2C"


def test_phase_2c_metadata_file_is_separate_from_prior_phases():
    phase_1_manifest = REPO_ROOT / "tests" / "fixtures" / "compatibility" / "phase_1_anchor_manifest.json"
    phase_1_content = json.loads(phase_1_manifest.read_text(encoding="utf-8"))
    phase_2a_content = json.loads(PHASE_2A_METADATA_PATH.read_text(encoding="utf-8"))
    phase_2b_content = json.loads(PHASE_2B_METADATA_PATH.read_text(encoding="utf-8"))
    phase_2c_content = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert "positive_short_interest_absolute_change" not in json.dumps(phase_1_content)
    assert "positive_short_interest_absolute_change" not in json.dumps(phase_2a_content)
    assert "positive_short_interest_absolute_change" not in json.dumps(phase_2b_content)
    assert "relative_volume_above_baseline" not in phase_2c_content["anchors"]
