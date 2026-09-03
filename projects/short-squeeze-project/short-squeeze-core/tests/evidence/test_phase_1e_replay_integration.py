import json
from pathlib import Path

from squeeze_core.contracts import EventType
from squeeze_core.replay import ReplayEngine
from squeeze_core.contracts import ReplayMode
from squeeze_core.serialization import canonical_json_bytes

from phase_1e_fixture_builders import build_phase_1e_artifacts


ROOT = Path(__file__).parents[1] / "fixtures" / "evidence"


def test_phase_1e_mixed_fixture_strict_replays_with_all_domains() -> None:
    artifacts = build_phase_1e_artifacts()
    assert len(artifacts["observations"]) == 7
    assert {item.event_type for item in artifacts["observations"]} == {
        EventType.MARKET_SNAPSHOT,
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
        EventType.PUBLISHED_SHORT_INTEREST,
        EventType.SEC_FILING,
    }
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(artifacts["observations"])
    assert replay.observations == artifacts["observations"]


def test_phase_1e_timeline_is_hindsight_resistant_and_deterministic() -> None:
    first = build_phase_1e_artifacts()
    second = build_phase_1e_artifacts()
    assert first["jsonl_bytes"] == second["jsonl_bytes"]
    assert first["metadata"] == second["metadata"]
    assert canonical_json_bytes(first["timeline_bundles"]["before_acceptance"]) == canonical_json_bytes(second["timeline_bundles"]["before_acceptance"])
    assert len(first["timeline_bundles"]["before_acceptance"].observations) == 3
    assert len(first["timeline_bundles"]["after_original_receipt"].observations) == 5
    assert len(first["timeline_bundles"]["after_amendment_receipt"].observations) == 7
    assert len(first["timeline_bundles"]["after_amendment_receipt"].revision_relationships) == 2


def test_phase_1e_committed_artifacts_match_builder() -> None:
    artifacts = build_phase_1e_artifacts()
    expected = json.loads((ROOT / "expected_phase_1e_bundle_metadata.json").read_text(encoding="utf-8"))
    assert artifacts["metadata"] == expected
    assert (ROOT / "normalized_phase_1e_point_in_time.jsonl").read_bytes() == artifacts["jsonl_bytes"]


def test_phase_1d_compatibility_hashes_are_preserved() -> None:
    artifacts = build_phase_1e_artifacts()
    assert artifacts["metadata"]["phase_1d_mixed_jsonl_sha256"] == "de24c62a4d964e4ff9a555a4357b9fc0a212430c2c5336f676cc61c0fe6fb5f0"
    assert artifacts["metadata"]["phase_1d_strict_replay_sha256"] == "2532dc3171da766e4fc9a631fd69a0fa8142462f3cd02e1b9f416073730380ff"
    assert artifacts["metadata"]["phase_1c_bundle_sha256"] == "d633447eb59cc8cdb059429e53498ca8a49f3895da0800fb56c1ff43729f2455"
