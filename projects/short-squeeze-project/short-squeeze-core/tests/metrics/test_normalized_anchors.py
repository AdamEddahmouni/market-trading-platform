import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2b_metric_metadata.json"
PHASE_2A_METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2a_metric_metadata.json"
CLI_BARS = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_cli_demo_bars.jsonl"
CLI_SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_normalized_metric_cases.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_phase_2b_anchors import build_anchor_results  # noqa: E402
from squeeze_core.metrics import normalized_metric_result_hash, serialize_normalized_metric_result  # noqa: E402
from squeeze_core.serialization import canonical_hash  # noqa: E402


def _recorded_anchors() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))["anchors"]


def test_metadata_file_is_well_formed():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "1.0.0"
    assert len(metadata["anchors"]) == 21


def test_all_required_anchors_are_present():
    anchors = _recorded_anchors()
    required = {
        "relative_volume_above_baseline",
        "relative_volume_below_baseline",
        "relative_volume_equal_baseline",
        "zero_target_relative_volume",
        "positive_volume_percent_deviation",
        "negative_volume_percent_deviation",
        "positive_volume_z_score",
        "negative_volume_z_score",
        "zero_volume_z_score",
        "mean_percentage_return_baseline",
        "percentage_return_standard_deviation_baseline",
        "positive_percentage_return_z_score",
        "negative_percentage_return_z_score",
        "zero_percentage_return_z_score",
        "before_correction_normalized_result",
        "after_correction_normalized_result",
        "before_cancellation_normalized_result",
        "after_cancellation_normalized_result",
        "mixed_phase_2b_metric_output",
        "phase_2b_cli_output",
        "serialized_phase_2b_metric_collection",
    }
    assert required <= set(anchors)


def test_regenerating_named_results_twice_is_byte_identical():
    first = build_anchor_results()
    second = build_anchor_results()
    for name in first:
        assert normalized_metric_result_hash(first[name]) == normalized_metric_result_hash(second[name]), name


def test_regenerated_named_results_match_recorded_anchors():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    for name, result in results.items():
        assert normalized_metric_result_hash(result) == anchors[name], name


def test_regenerated_composite_anchors_match_recorded_values():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]

    assert canonical_hash(list(collection)) == anchors["mixed_phase_2b_metric_output"]

    serialized = hashlib.sha256(
        b"[" + b",".join(serialize_normalized_metric_result(item) for item in collection) + b"]"
    ).hexdigest()
    assert serialized == anchors["serialized_phase_2b_metric_collection"]


def test_cli_output_hash_matches_recorded_anchor_and_is_stable():
    anchors = _recorded_anchors()

    def run():
        completed = subprocess.run(
            [
                sys.executable, "-m", "squeeze_core", "build-market-metrics",
                "--input", str(CLI_BARS), "--symbol", "TESTB", "--as-of", "2026-02-01T22:00:00Z",
                "--spec", str(CLI_SPEC),
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()

    first = run()
    second = run()
    assert first == second
    assert first == anchors["phase_2b_cli_output"]


def test_no_unexplained_anchor_collisions():
    phase_2a_anchors = json.loads(PHASE_2A_METADATA_PATH.read_text(encoding="utf-8"))["anchors"]
    phase_2b_anchors = _recorded_anchors()
    cross_phase_overlap = set(phase_2a_anchors.values()) & set(phase_2b_anchors.values())
    assert not cross_phase_overlap

    # The one expected within-phase coincidence: mixed_phase_2b_metric_output and
    # serialized_phase_2b_metric_collection are, by construction, sha256 of the identical byte
    # sequence (canonical_json_bytes of a list IS "[" + comma-joined items + "]"), exactly
    # mirroring Phase 2A's own explained mixed_...==serialized_... coincidence.
    expected_linked_pair = {
        phase_2b_anchors["mixed_phase_2b_metric_output"],
        phase_2b_anchors["serialized_phase_2b_metric_collection"],
    }
    assert len(expected_linked_pair) == 1

    remaining = {k: v for k, v in phase_2b_anchors.items() if k != "serialized_phase_2b_metric_collection"}
    values = list(remaining.values())
    assert len(values) == len(set(values)), "unexplained duplicate anchor hash within Phase 2B"


def test_phase_2b_metadata_file_is_separate_from_phase_1_and_phase_2a():
    phase_1_manifest = REPO_ROOT / "tests" / "fixtures" / "compatibility" / "phase_1_anchor_manifest.json"
    phase_1_content = json.loads(phase_1_manifest.read_text(encoding="utf-8"))
    phase_2a_content = json.loads(PHASE_2A_METADATA_PATH.read_text(encoding="utf-8"))
    phase_2b_content = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert "relative_volume_above_baseline" not in json.dumps(phase_1_content)
    assert "relative_volume_above_baseline" not in json.dumps(phase_2a_content)
    assert "positive_absolute_return" not in phase_2b_content["anchors"]
