import json
from pathlib import Path

from phase_1g_fixture_builders import build_phase_1g_artifacts
from squeeze_core.contracts import EventType, ReplayMode
from squeeze_core.evidence import CoverageDomain
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes


ROOT = Path(__file__).parents[1] / "fixtures"


def test_phase_1g_mixed_fixture_replays_news_with_prior_domains() -> None:
    observations = load_fixture(ROOT / "evidence" / "normalized_phase_1g_point_in_time.jsonl")
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    assert EventType.NEWS_ITEM in {item.event_type for item in replay.observations}
    assert len(replay.observations) > 12


def test_phase_1g_artifacts_match_committed_hashes_and_repeat() -> None:
    first = build_phase_1g_artifacts()
    second = build_phase_1g_artifacts()
    expected = json.loads((ROOT / "evidence" / "expected_phase_1g_bundle_metadata.json").read_text(encoding="utf-8"))
    assert first["metadata"] == expected == second["metadata"]
    assert first["jsonl_bytes"] == second["jsonl_bytes"]
    assert canonical_json_bytes(first["timeline_bundles"]) == canonical_json_bytes(second["timeline_bundles"])


def test_timeline_enforces_availability_receipt_update_and_withdrawal() -> None:
    bundles = build_phase_1g_artifacts()["timeline_bundles"]
    counts = {label: len(bundle.observations) for label, bundle in bundles.items()}
    assert counts == {
        "before_availability": 12,
        "after_availability_before_receipt": 12,
        "after_original_receipt": 13,
        "before_update_receipt": 13,
        "after_update_receipt": 14,
        "after_withdrawal_receipt": 15,
    }
    final = bundles["after_withdrawal_receipt"]
    coverage = next(item for item in final.source_coverage if item.domain is CoverageDomain.NEWS)
    assert len(coverage.observation_ids) == 3


def test_mixed_manifest_has_all_thirty_five_nondirectional_cases() -> None:
    document = json.loads((ROOT / "evidence" / "mixed_phase_1g_cases.json").read_text(encoding="utf-8"))
    assert len(document["cases"]) == 35
    assert not document["contains_credentials"]
    assert not document["contains_account_data"]
    assert not document["contains_real_symbols"]
    assert document["directional_interpretation"] is False
