import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "validation"
METADATA_PATH = FIXTURES / "expected_phase_2v_validation_metadata.json"
CASE_SPEC = FIXTURES / "biya_validation_case.json"
DEMO_DATA = REPO_ROOT / "apps" / "biya-validation-demo" / "data" / "biya-case.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_phase_2v_anchors import (  # noqa: E402
    _HASH_FUNCS,
    _SERIALIZE_FUNCS,
    build_anchor_results,
)

from squeeze_core.serialization import canonical_hash  # noqa: E402

REQUIRED_ANCHORS = {
    "detection_time_exact_case",
    "detection_time_bounded_case",
    "detection_time_unknown_case",
    "biya_artifact_inventory",
    "biya_original_candidate_snapshot",
    "biya_earliest_as_of_replay",
    "biya_latest_as_of_replay",
    "biya_field_comparison",
    "biya_rule_validation_collection",
    "biya_days_to_cover_comparison",
    "biya_news_timing_comparison",
    "biya_outcome_observation",
    "biya_methodology_conclusion",
    "biya_complete_validation_case",
    "comparison_case_manifest",
    "public_biya_case_export",
    "mixed_phase_2v_output",
    "phase_2v_cli_output",
    "phase_2v_demo_data_output",
    "serialized_phase_2v_collection",
}


def _recorded() -> dict:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))["anchors"]


def test_metadata_file_is_well_formed():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "1.0.0"
    assert len(metadata["anchors"]) == 20


def test_all_required_anchors_present():
    assert REQUIRED_ANCHORS <= set(_recorded())


def test_every_result_anchor_recomputes_byte_identical():
    recorded = _recorded()
    for name, result in build_anchor_results().items():
        hash_fn = _HASH_FUNCS[type(result).__name__]
        assert hash_fn(result) == recorded[name], f"anchor mismatch: {name}"


def test_mixed_output_and_serialized_collection_recompute():
    recorded = _recorded()
    results = build_anchor_results()
    collection = [results[name] for name in sorted(results)]
    assert canonical_hash(list(collection)) == recorded["mixed_phase_2v_output"]
    serialized = (
        b"[" + b",".join(_SERIALIZE_FUNCS[type(item).__name__](item) for item in collection) + b"]"
    )
    assert hashlib.sha256(serialized).hexdigest() == recorded["serialized_phase_2v_collection"]


def test_no_unexplained_hash_collisions():
    """mixed_phase_2v_output and serialized_phase_2v_collection are EXPECTED to collide:
    canonical JSON array serialization is exactly "[" + comma-joined compact element
    bytes + "]" with no list-level transformation, so the two computations are
    byte-identical by construction. Phase 2C and Phase 2D record the same property for
    their own manifests. Any other collision is unexplained and fails here."""

    explained = {frozenset({"mixed_phase_2v_output", "serialized_phase_2v_collection"})}
    by_hash: dict[str, list[str]] = {}
    for name, value in _recorded().items():
        by_hash.setdefault(value, []).append(name)
    for names in by_hash.values():
        if len(names) > 1:
            assert frozenset(names) in explained, f"unexplained collision: {names}"


def test_semantically_different_detection_states_have_different_hashes():
    results = build_anchor_results()
    hashes = {
        _HASH_FUNCS[type(results[name]).__name__](results[name])
        for name in (
            "detection_time_exact_case",
            "detection_time_bounded_case",
            "detection_time_unknown_case",
        )
    }
    assert len(hashes) == 3


def test_the_two_window_edge_replays_are_distinct():
    results = build_anchor_results()
    earliest = results["biya_earliest_as_of_replay"]
    latest = results["biya_latest_as_of_replay"]
    assert earliest.deterministic_id != latest.deterministic_id
    assert earliest.as_of < latest.as_of


def test_unknown_results_still_carry_enough_identity_to_differ():
    """An UNKNOWN detection time for two different symbols must not share an id."""

    from squeeze_core.validation import build_detection_time_evidence

    first = build_detection_time_evidence("AAAA", ())
    second = build_detection_time_evidence("BBBB", ())
    assert first.deterministic_id != second.deterministic_id


def test_generator_regenerates_byte_identical_outputs(tmp_path):
    before_metadata = METADATA_PATH.read_bytes()
    before_demo = DEMO_DATA.read_bytes()
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "generate_phase_2v_anchors.py")],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        assert METADATA_PATH.read_bytes() == before_metadata
        assert DEMO_DATA.read_bytes() == before_demo


def test_cli_output_is_deterministic_across_two_runs():
    args = [
        sys.executable, "-m", "squeeze_core", "build-candidate-validation",
        "--case-spec", str(CASE_SPEC),
    ]
    first = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    second = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    assert (
        hashlib.sha256(first.stdout.encode("utf-8")).hexdigest()
        == _recorded()["phase_2v_cli_output"]
    )


def test_demo_payload_matches_its_anchor():
    assert (
        hashlib.sha256(DEMO_DATA.read_bytes()).hexdigest()
        == _recorded()["phase_2v_demo_data_output"]
    )


def test_no_anchor_input_leaks_a_local_path_or_credential():
    """Sensitive local paths must never reach canonical bytes, so they can never reach
    a hash either."""

    results = build_anchor_results()
    for name, result in results.items():
        rendered = _SERIALIZE_FUNCS[type(result).__name__](result).decode("utf-8")
        assert "C:\\" not in rendered, name
        assert "/Users/" not in rendered, name
        assert "auth=" not in rendered, name
        assert "49dafaaa" not in rendered, name
