import hashlib
import json
from pathlib import Path

from squeeze_core.contracts import EventType, ReplayMode
from squeeze_core.evidence import CoverageDomain, build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes

from phase_1d_fixture_builders import build_phase_1d_artifacts


FIXTURES = Path(__file__).parents[1] / "fixtures"
EVIDENCE = FIXTURES / "evidence"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_builder_matches_committed_phase_1d_artifacts_and_is_repeatable() -> None:
    first = build_phase_1d_artifacts()
    second = build_phase_1d_artifacts()
    metadata = json.loads(
        (EVIDENCE / "expected_phase_1d_bundle_metadata.json").read_text(encoding="utf-8")
    )

    assert first == second
    assert first["jsonl_bytes"] == (EVIDENCE / "normalized_phase_1d_point_in_time.jsonl").read_bytes()
    assert first["metadata"] == metadata


def test_mixed_phase_1d_fixture_passes_strict_replay_with_four_independent_domains() -> None:
    observations = load_fixture(EVIDENCE / "normalized_phase_1d_point_in_time.jsonl")
    result = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)

    assert len(result.observations) == 5
    assert [item.event_type for item in result.observations] == [
        EventType.MARKET_SNAPSHOT,
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
        EventType.PUBLISHED_SHORT_INTEREST,
        EventType.PUBLISHED_SHORT_INTEREST,
    ]
    assert result.result_hash == json.loads(
        (EVIDENCE / "expected_phase_1d_bundle_metadata.json").read_text()
    )["strict_replay_sha256"]


def test_replayed_publication_timeline_has_stable_historical_membership() -> None:
    artifacts = build_phase_1d_artifacts()
    timeline = artifacts["timeline_bundles"]

    assert all(
        item.event_type is not EventType.PUBLISHED_SHORT_INTEREST
        for item in timeline["before_publication"].observations
    )
    assert len(timeline["after_publication_before_receipt"].observations) == 3
    assert len(timeline["after_original_receipt"].observations) == 4
    assert len(timeline["before_correction_receipt"].observations) == 4
    assert len(timeline["after_correction_receipt"].observations) == 5
    assert len(timeline["after_correction_receipt"].revision_relationships) == 1

    rebuilt = build_point_in_time_evidence(
        "TESTA",
        reversed(artifacts["observations"]),
        artifacts["policies"]["after_original_receipt"],
    )
    assert canonical_json_bytes(rebuilt) == canonical_json_bytes(
        timeline["after_original_receipt"]
    )


def test_existing_phase_hashes_remain_unchanged() -> None:
    expected = json.loads((EVIDENCE / "expected_bundle_metadata.json").read_text())

    assert sha256(FIXTURES / "minimal_session.jsonl") == expected["phase_1a_minimal_sha256"]
    assert sha256(FIXTURES / "quality_edge_cases.jsonl") == expected["phase_1a_quality_sha256"]
    assert sha256(FIXTURES / "out_of_order_session.jsonl") == expected["phase_1a_out_of_order_sha256"]
    assert sha256(FIXTURES / "providers" / "ibkr" / "normalized_session.jsonl") == expected["phase_1b_ibkr_jsonl_sha256"]
    assert sha256(EVIDENCE / "normalized_point_in_time.jsonl") == expected["mixed_jsonl_sha256"]


def test_mixed_case_manifest_covers_required_phase_1d_scenarios_without_strategy_output() -> None:
    manifest = json.loads(
        (EVIDENCE / "mixed_finviz_ibkr_finra_cases.json").read_text(encoding="utf-8")
    )
    assert len(manifest["cases"]) == 12
    assert {case["case_id"] for case in manifest["cases"]} == {
        f"mixed-phase-1d-{index:02d}" for index in range(1, 13)
    }
    rendered = json.dumps(manifest).lower()
    for forbidden in ("score", "rank", "recommendation", "entry", "exit", "signal"):
        assert forbidden not in rendered


def test_metadata_records_all_required_hash_families() -> None:
    metadata = json.loads(
        (EVIDENCE / "expected_phase_1d_bundle_metadata.json").read_text()
    )
    required = {
        "finra_complete_raw_sha256",
        "finra_original_observation_sha256",
        "finra_correction_observation_sha256",
        "mixed_jsonl_sha256",
        "strict_replay_sha256",
        "before_publication_bundle_sha256",
        "after_publication_before_receipt_bundle_sha256",
        "after_original_receipt_bundle_sha256",
        "before_correction_receipt_bundle_sha256",
        "after_correction_receipt_bundle_sha256",
        "after_correction_serialized_sha256",
    }
    assert required <= set(metadata)
    assert all(len(metadata[key]) == 64 for key in required)
