import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2a_metric_metadata.json"
CLI_BARS = REPO_ROOT / "tests" / "fixtures" / "metrics" / "cli_demo_bars.jsonl"
CLI_SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2a_metric_cases.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_phase_2a_anchors import build_anchor_results  # noqa: E402
from squeeze_core.metrics import metric_result_hash, serialize_metric_result  # noqa: E402
from squeeze_core.serialization import canonical_hash  # noqa: E402


def _recorded_anchors() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))["anchors"]


def test_metadata_file_is_well_formed():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "1.0.0"
    assert len(metadata["anchors"]) == 16


def test_all_sixteen_required_anchors_are_present():
    anchors = _recorded_anchors()
    required = {
        "positive_absolute_return",
        "positive_percentage_return",
        "negative_percentage_return",
        "positive_absolute_gap",
        "positive_percentage_gap",
        "absolute_range",
        "percentage_range",
        "three_sample_volume_baseline",
        "five_sample_volume_baseline",
        "before_correction_metric_result",
        "after_correction_metric_result",
        "before_cancellation_metric_result",
        "after_cancellation_metric_result",
        "mixed_phase_2a_metric_output_sha256",
        "cli_output_sha256",
        "serialized_final_metric_collection_sha256",
    }
    assert required <= set(anchors)


def test_regenerating_named_results_twice_is_byte_identical():
    first = build_anchor_results()
    second = build_anchor_results()
    for name in first:
        assert metric_result_hash(first[name]) == metric_result_hash(second[name]), name


def test_regenerated_named_results_match_recorded_anchors():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    for name, result in results.items():
        assert metric_result_hash(result) == anchors[name], name


def test_regenerated_composite_anchors_match_recorded_values():
    anchors = _recorded_anchors()
    results = build_anchor_results()
    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]

    assert canonical_hash(list(collection)) == anchors["mixed_phase_2a_metric_output_sha256"]

    serialized = hashlib.sha256(
        b"[" + b",".join(serialize_metric_result(item) for item in collection) + b"]"
    ).hexdigest()
    assert serialized == anchors["serialized_final_metric_collection_sha256"]


def test_cli_output_hash_matches_recorded_anchor_and_is_stable():
    anchors = _recorded_anchors()

    def run():
        completed = subprocess.run(
            [
                sys.executable, "-m", "squeeze_core", "build-market-metrics",
                "--input", str(CLI_BARS), "--symbol", "TESTA", "--as-of", "2026-01-20T22:00:00Z",
                "--spec", str(CLI_SPEC),
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()

    first = run()
    second = run()
    assert first == second
    assert first == anchors["cli_output_sha256"]
