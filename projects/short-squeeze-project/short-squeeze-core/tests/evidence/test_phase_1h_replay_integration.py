import json
from pathlib import Path

from phase_1h_fixture_builders import build_phase_1h_artifacts
from squeeze_core.contracts import EventType, ReplayMode
from squeeze_core.evidence import CoverageDomain
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes


ROOT = Path(__file__).parents[1] / "fixtures"


def test_phase_1h_mixed_fixture_replays_bars_with_all_prior_domains():
    observations = load_fixture(ROOT / "evidence" / "normalized_phase_1h_point_in_time.jsonl")
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    event_types = {item.event_type for item in replay.observations}
    assert {
        EventType.MARKET_SNAPSHOT,
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
        EventType.PUBLISHED_SHORT_INTEREST,
        EventType.SEC_FILING,
        EventType.TRADING_HALT,
        EventType.NEWS_ITEM,
        EventType.BAR,
    } <= event_types


def test_phase_1h_artifacts_match_committed_hashes_and_repeat():
    first = build_phase_1h_artifacts()
    second = build_phase_1h_artifacts()
    expected = json.loads(
        (ROOT / "evidence" / "expected_phase_1h_bundle_metadata.json").read_text(encoding="utf-8")
    )
    assert first["metadata"] == expected == second["metadata"]
    assert first["jsonl_bytes"] == second["jsonl_bytes"]
    assert canonical_json_bytes(first["timeline_bundles"]) == canonical_json_bytes(second["timeline_bundles"])
    assert first["bar_series"] == second["bar_series"]
    assert expected["cancelled_bar_raw_record_sha256"]
    assert expected["cancelled_bar_observation_sha256"]


def test_timeline_preserves_partial_completed_and_corrected_records():
    bundles = build_phase_1h_artifacts()["timeline_bundles"]
    expected_ids = {
        "before_partial_publication": [],
        "after_partial_receipt": ["phase1h-partial"],
        "before_completed_receipt": ["phase1h-partial"],
        "after_completed_receipt": ["phase1h-partial", "phase1h-complete"],
        "before_correction_receipt": ["phase1h-partial", "phase1h-complete"],
        "after_correction_receipt": ["phase1h-partial", "phase1h-complete", "phase1h-corrected"],
    }
    for label, expected in expected_ids.items():
        bars = [item.source_record_id for item in bundles[label].observations if item.event_type is EventType.BAR]
        assert bars == expected
    final = bundles["after_correction_receipt"]
    coverage = next(item for item in final.source_coverage if item.domain is CoverageDomain.MARKET_BARS)
    assert len(coverage.observation_ids) == 3


def test_mixed_case_manifest_is_strategy_neutral():
    document = json.loads((ROOT / "evidence" / "mixed_phase_1h_cases.json").read_text(encoding="utf-8"))
    assert len(document["cases"]) == 15
    assert document["contains_credentials"] is False
    assert document["contains_account_data"] is False
    assert document["contains_real_symbols"] is False
    assert document["calculates_indicators"] is False
    assert document["calculates_relative_volume"] is False
    assert document["strategy_interpretation"] is False


def test_phase_1g_compatibility_anchors_are_embedded_unchanged():
    phase_1h = build_phase_1h_artifacts()["metadata"]
    phase_1g = json.loads((ROOT / "evidence" / "expected_phase_1g_bundle_metadata.json").read_text(encoding="utf-8"))
    assert phase_1h["phase_1g_mixed_jsonl_sha256"] == phase_1g["mixed_jsonl_sha256"]
    assert phase_1h["phase_1g_strict_replay_sha256"] == phase_1g["strict_replay_sha256"]
    assert phase_1h["phase_1g_final_bundle_sha256"] == phase_1g["final_bundle_sha256"]
    assert phase_1h["phase_1g_serialized_final_bundle_sha256"] == phase_1g["serialized_final_bundle_sha256"]
