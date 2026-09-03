import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "tests" / "fixtures" / "readiness" / "expected_phase_2d_readiness_metadata.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_phase_2d_anchors import (  # noqa: E402
    _HASH_FUNCS,
    _SERIALIZE_FUNCS,
    build_anchor_results,
)
from squeeze_core.serialization import canonical_hash  # noqa: E402


def _recorded_anchors() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))["anchors"]


def test_metadata_file_is_well_formed():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "1.0.0"
    assert len(metadata["anchors"]) == 32


def test_all_required_anchors_present():
    anchors = _recorded_anchors()
    required = {
        "all_domains_present_coverage",
        "missing_domain_coverage",
        "unavailable_domain_coverage",
        "conflicted_domain_coverage",
        "zero_value_present_coverage",
        "age_alignment_equal",
        "age_alignment_spread",
        "reporting_period_alignment_equal",
        "reporting_period_alignment_spread",
        "no_conflict_summary",
        "multi_domain_conflict_summary",
        "missingness_domain_case",
        "missingness_field_case",
        "sufficient_return_inputs",
        "insufficient_return_inputs",
        "sufficient_relative_volume_inputs",
        "insufficient_relative_volume_history",
        "sufficient_days_to_cover_inputs",
        "insufficient_days_to_cover_inputs",
        "sufficient_borrow_fee_inputs",
        "incompatible_borrow_fee_units",
        "readiness_sufficient",
        "readiness_insufficient",
        "readiness_unknown",
        "readiness_conflicted",
        "before_correction_readiness",
        "after_correction_readiness",
        "before_cancellation_readiness",
        "after_cancellation_readiness",
        "mixed_phase_2d_output",
        "phase_2d_cli_output",
        "serialized_phase_2d_collection",
    }
    assert required <= set(anchors)


def test_every_anchor_recomputes_byte_identical():
    recorded = _recorded_anchors()
    results = build_anchor_results()
    for name, result in results.items():
        hash_fn = _HASH_FUNCS[type(result).__name__]
        assert hash_fn(result) == recorded[name], f"anchor mismatch: {name}"


def test_mixed_output_and_serialized_collection_recompute():
    recorded = _recorded_anchors()
    results = build_anchor_results()
    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    assert canonical_hash(list(collection)) == recorded["mixed_phase_2d_output"]

    serialized = b"[" + b",".join(
        _SERIALIZE_FUNCS[type(item).__name__](item) for item in collection
    ) + b"]"
    import hashlib

    assert hashlib.sha256(serialized).hexdigest() == recorded["serialized_phase_2d_collection"]


def test_readiness_states_are_distinct_across_anchors():
    # Semantically different structural states must never collide.
    results = build_anchor_results()
    states = {
        results["readiness_sufficient"].structural_state,
        results["readiness_insufficient"].structural_state,
        results["readiness_unknown"].structural_state,
        results["readiness_conflicted"].structural_state,
    }
    assert len(states) == 4
    hashes = {
        _HASH_FUNCS[type(results[name]).__name__](results[name])
        for name in ("readiness_sufficient", "readiness_insufficient", "readiness_unknown", "readiness_conflicted")
    }
    assert len(hashes) == 4


def test_before_after_correction_anchors_are_distinct():
    results = build_anchor_results()
    before = results["before_correction_readiness"]
    after = results["after_correction_readiness"]
    assert before.deterministic_id != after.deterministic_id


def test_before_after_cancellation_anchors_are_distinct():
    results = build_anchor_results()
    before = results["before_cancellation_readiness"]
    after = results["after_cancellation_readiness"]
    assert before.deterministic_id != after.deterministic_id


def test_no_unexplained_hash_collisions_across_all_anchors():
    # mixed_phase_2d_output (canonical_hash of the sorted result list) and
    # serialized_phase_2d_collection (sha256 of "[" + comma-joined per-item
    # canonical JSON + "]") are EXPECTED to collide: canonical JSON array
    # serialization is exactly "[" + comma-joined compact element bytes + "]" with
    # no list-level transformation, so the two computations are byte-identical by
    # construction. This is not new to Phase 2D -- the pre-existing Phase 2C anchor
    # manifest has the identical property between mixed_phase_2c_metric_output and
    # serialized_phase_2c_metric_collection, confirmed by inspection.
    explained_pairs = {frozenset({"mixed_phase_2d_output", "serialized_phase_2d_collection"})}
    recorded = _recorded_anchors()
    by_hash: dict[str, list[str]] = {}
    for name, value in recorded.items():
        if name == "phase_2d_cli_output":
            continue
        by_hash.setdefault(value, []).append(name)
    for value, names in by_hash.items():
        if len(names) > 1:
            assert frozenset(names) in explained_pairs, f"unexplained collision: {names}"



def test_generator_script_regenerates_byte_identical_metadata_file(tmp_path):
    original_bytes = METADATA_PATH.read_bytes()
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_phase_2d_anchors.py")],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )
    regenerated_bytes = METADATA_PATH.read_bytes()
    assert regenerated_bytes == original_bytes
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_phase_2d_anchors.py")],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )
    assert METADATA_PATH.read_bytes() == original_bytes


def test_cli_output_deterministic_across_two_runs():
    cli_input = REPO_ROOT / "tests" / "fixtures" / "readiness" / "phase_2d_cli_demo_observations.jsonl"
    args = [
        sys.executable, "-m", "squeeze_core", "build-evidence-readiness",
        "--input", str(cli_input), "--symbol", "TESTD", "--as-of", "2026-03-01T12:00:00Z",
        "--operation", "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
    ]
    first = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    second = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    import hashlib

    recorded = _recorded_anchors()
    assert hashlib.sha256(first.stdout.encode("utf-8")).hexdigest() == recorded["phase_2d_cli_output"]
